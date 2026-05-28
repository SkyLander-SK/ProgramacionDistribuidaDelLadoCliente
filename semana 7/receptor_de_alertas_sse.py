import asyncio
import logging
import sys
from datetime import datetime
import httpx

# Configuración del Logger para producción
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EcoMarketSSE")

# Configuración básica del cliente
URL_SSE = "http://127.0.0.1:8000/api/v1/alertas"
TOKEN = "eyJ0eXAiO..."


class ReceptorAlertas:
    """
    Cliente SSE manual altamente resiliente desarrollado para EcoMarket.
    Implementa el parsing manual de tramas y control de reconexión.
    """
    def __init__(self, target_url: str, token: str):
        self.target_url = target_url
        self.token = token
        self.last_event_id = None
        self.retry_ms = 3000  # Valor por defecto (3 segundos)
        self.ejecutando = False
        self.reintentos_consecutivos = 0
        self.max_reintentos = 5

    async def iniciar(self):
        """
        Inicia el ciclo persistente de conexión y lectura del stream.
        """
        self.ejecutando = True
        self.reintentos_consecutivos = 0

        # --- TRADE-OFFS ETAPA 1 (CONEXIÓN Y TIMEOUTS) ---
        # 1. Timeout de conexión vs. Timeout de lectura:
        #    Configuramos un Timeout de conexión estricto de 10s para evitar hilos suspendidos,
        #    pero deshabilitamos el timeout de lectura (read=None). En SSE, los servidores
        #    pueden pasar minutos en silencio absoluto sin enviar datos. Si dejáramos el 
        #    timeout de lectura por defecto (usualmente 5s en httpx), el socket se caería
        #    constantemente de manera artificial.
        # 2. Cliente persistente vs. Cliente efímero:
        #    Para SSE es mandatorio usar la API de streaming ('client.stream') manteniendo la
        #    conexión viva a nivel TCP (keep-alive) en lugar de realizar llamadas GET secuenciales.
        timeout_config = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)
        
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            while self.ejecutando:
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                }
                
                if self.last_event_id:
                    headers["Last-Event-ID"] = str(self.last_event_id)

                try:
                    logger.info(f"Conectando a {self.target_url}...")
                    logger.info(f"Headers enviados: Accept={headers['Accept']}, Last-Event-ID={headers.get('Last-Event-ID', 'Ninguno')}")
                    
                    async with client.stream("GET", self.target_url, headers=headers) as response:
                        
                        # --- TRADE-OFFS ETAPA 3 (GESTIÓN DE RESPUESTAS HTTP) ---
                        # Si el servidor responde con 204 (No Content), significa que no hay más eventos
                        # que transmitir. Intentar reconectarse en este escenario generaría un bucle 
                        # infinito de peticiones inútiles (DoS involuntario al servidor).
                        if response.status_code == 204:
                            logger.info("Servidor respondió con HTTP 204 (No Content). Deteniendo el cliente de forma limpia.")
                            self.ejecutando = False
                            break

                        if response.status_code != 200:
                            logger.error(f"Error en respuesta del servidor. Código HTTP: {response.status_code}")
                            raise httpx.HTTPStatusError("Respuesta no exitosa", request=response.request, response=response)

                        # Conexión exitosa, reiniciamos el contador de backoff exponencial
                        self.reintentos_consecutivos = 0
                        logger.info("Conexión SSE establecida con éxito.")

                        # --- PARSER MANUAL (ETAPA 2) ---
                        buffer_lineas = []
                        
                        # Iteramos el cuerpo línea por línea asíncronamente
                        async for linea_cruda in response.aiter_lines():
                            if not self.ejecutando:
                                break

                            # Imprimir línea cruda con timestamp para depuración
                            timestamp_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            # Mostramos la línea tal cual viaja en los bytes de red
                            logger.debug(f"[RAW {timestamp_actual}] {repr(linea_cruda)}")

                            # Una línea vacía indica el fin de un bloque de evento SSE (\n\n)
                            if not linea_cruda.strip():
                                if buffer_lineas:
                                    await self._procesar_bloque_evento(buffer_lineas)
                                    buffer_lineas = []  # Reseteo estricto del buffer de mensaje
                                continue

                            buffer_lineas.append(linea_cruda)

                except (httpx.HTTPError, Exception) as err:
                    if not self.ejecutando:
                        break
                    
                    logger.error(f"Fallo de conexión o lectura: {err}")
                    self.reintentos_consecutivos += 1
                    
                    if self.reintentos_consecutivos > self.max_reintentos:
                        logger.critical("Se alcanzó el límite de 5 reintentos consecutivos. Cancelando operación.")
                        self.ejecutando = False
                        break
                    
                    # --- TRADE-OFFS ETAPA 3 (POLÍTICA DE RECONEXIÓN) ---
                    # Backoff exponencial para evitar saturación de red tras cortes de energía generalizados:
                    # Fórmula: retry_delay = (retry_ms / 1000) * (2 ** intento)
                    delay = (self.retry_ms / 1000.0) * (2 ** (self.reintentos_consecutivos - 1))
                    logger.warning(f"Reintento {self.reintentos_consecutivos}/{self.max_reintentos} en {delay:.2s} segundos...")
                    await asyncio.sleep(delay)

        logger.info("Ciclo de ReceptorAlertas finalizado.")

    async def _procesar_bloque_evento(self, lineas: list):
        """
        --- TRADE-OFFS ETAPA 2 (PARSER MANUAL DE CAMPOS) ---
        El estándar SSE permite que existan múltiples líneas 'data:' para un solo evento,
        las cuales deben ser concatenadas usando saltos de línea (\n). Además, el orden de las
        líneas (id, event, data) dentro del bloque puede variar según la implementación del backend.
        Por ello, acumulamos los campos en variables locales y solo enrutamos al final del bloque.
        """
        evento_tipo = None
        data_acumulada = []
        event_id = None

        for linea in lineas:
            # Ignorar comentarios (líneas de keep-alive que comienzan con ':')
            if linea.startswith(":"):
                logger.info(f"[Keep-Alive] Comentario del servidor: {line[1:].strip()}")
                continue

            if ":" in linea:
                campo, valor = linea.split(":", 1)
                campo = campo.strip()
                valor = valor.strip()

                if campo == "id":
                    event_id = valor
                    self.last_event_id = valor  # Persistencia en memoria
                elif campo == "event":
                    evento_tipo = valor
                elif campo == "data":
                    data_acumulada.append(valor)
                elif campo == "retry":
                    try:
                        self.retry_ms = int(valor)
                        logger.info(f"Intervalo de reconexión (retry) actualizado por el servidor a {self.retry_ms}ms")
                    except ValueError:
                        pass

        if data_acumulada:
            mensaje_completo = "\n".join(data_acumulada)
            await self._enrutar_evento(evento_tipo, mensaje_completo)

    async def _enrutar_evento(self, tipo: str, raw_data: str):
        """
        Analiza el tipo de evento y lo distribuye al pipeline correspondiente.
        """
        # Evento por defecto si no viene explícito en el stream
        tipo = tipo or "message"

        try:
            data_json = json.loads(raw_data)
        except json.JSONDecodeError:
            data_json = {"raw_text": raw_data}

        # Enrutamiento semántico
        if tipo == "precio-actualizado":
            producto = data_json.get("producto", "Desconocido")
            precio = data_json.get("precio", 0)
            print(f"📈 [TABLA PRECIOS] Actualización en tiempo real -> {producto}: ${precio:.2f}")
            
        elif tipo == "stack-critico":
            producto = data_json.get("producto", "Desconocido")
            stock = data_json.get("stock", 0)
            print(f"⚠️ [ALERTA STOCK] ¡CRÍTICO! El producto '{producto}' cuenta con stock mínimo de: {stock} unidades.")
            
        else:
            # Eventos desconocidos: se ignoran de forma silenciosa para el usuario final,
            # pero se registra un log técnico de advertencia para el administrador del sistema.
            logger.warning(f"Evento ignorado silenciosamente [Tipo: {tipo}] -> Contenido: {raw_data}")

    def detener_limpio(self):
        """
        Inicia un apagado suave previniendo tareas asíncronas huérfanas.
        """
        logger.info("Iniciando detención controlada del cliente...")
        self.ejecutando = False


# ==========================================================
# PUNTO DE ENTRADA SIMULADO PARA CONTROL DE PRUEBAS
# ==========================================================
async def main():
    receptor = ReceptorAlertas(URL_SSE, TOKEN)
    
    # Manejo del cierre por teclado (SIGINT)
    loop = asyncio.get_running_loop()
    
    try:
        await receptor.iniciar()
    except KeyboardInterrupt:
        receptor.detener_limpio()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrograma finalizado de manera limpia.")