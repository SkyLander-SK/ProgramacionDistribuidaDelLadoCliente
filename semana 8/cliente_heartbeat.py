import asyncio
import httpx
import json
import logging
import time

"""
ECOMARKET - RESUMEN DE COMPORTAMIENTO (RETO 3 - CONCLUSION)

1. El problema del Timeout HTTP simple:
Si el servidor de EcoMarket se congela por un error interno, el socket de red se queda abierto 
pero sin mandar nada. El Timeout de HTTP no se da cuenta de esto porque la conexion no se ha 
cortado fisicamente, dejando la aplicacion del usuario congelada en un estado zombi.

2. La solucion con Heartbeat Watchdog:
Al mandar un pulso (heartbeat) desde el servidor cada 10s, el cliente sabe que el sistema sigue 
vivo. Si pasan mas de 35s sin recibir absolutamente nada, el guardian asincrono del cliente detecta 
el silencio, declara la conexion como muerta y la aborta a la fuerza.

3. Sinergia total:
El Timeout HTTP frena las caidas fisicas de la red, mientras que el Heartbeat Watchdog frena los 
congelamientos logicos del software. Juntos aseguran que el cliente siempre se reconecte de 
forma automatica usando el Backoff Exponencial.
"""

# Configuracion del sistema de rastreo de eventos
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EcoMarketHeartbeat")

# CONSTANTES DE DISEÑO REQUERIDAS
BASE_URL = "https://api.ecomarket.com/eventos"
TIMEOUT_LECTURA = 30.0   # Segundos maximos de espera por linea
TOLERANCIA_PULSO = 35.0  # TIMEOUT + 5s de margen de gracia para el Watchdog
MAX_REINTENTOS = 5
ESPERA_INICIAL = 1.0

# Variable global o de modulo para registrar de forma sincrona el ultimo pulso de datos
ultimo_pulso_activo = time.time()

class ClienteSSEHeartbeat:
    """Cliente SSE especializado en el monitoreo activo de Heartbeats y resiliencia."""
    
    def __init__(self, modulos: list):
        self.modulos = modulos
        self.estado = "DESCONECTADO"
        self.reintentos = 0
        self._parar = False

    def construir_url(self) -> str:
        return f"{BASE_URL}?modulos={','.join(self.modulos)}"

    async def _monitorear_heartbeat(self):
        """Watchdog Task: Corre concurrentemente vigilando la inactividad del socket."""
        global ultimo_pulso_activo
        while self.estado == "CONECTADO" and not self._parar:
            await asyncio.sleep(5.0)  # Frecuencia de muestreo del guardian
            
            tiempo_inactivo = time.time() - ultimo_pulso_activo
            if tiempo_inactivo > TOLERANCIA_PULSO:
                logger.error(
                    f" [HEARTBEAT DETECTADO MUERTO] El servidor se colgo en silencio. "
                    f"Inactividad: {tiempo_inactivo:.1f}s (Limite: {TOLERANCIA_PULSO}s)."
                )
                # Forzar cambio de estado para romper el iterador de lineas
                self.estado = "DESCONECTADO"
                break

    async def _leer_stream(self, respuesta_http):
        """Itera el flujo de bytes entrantes y actualiza los marcadores de vida del canal."""
        global ultimo_pulso_activo
        ultimo_pulso_activo = time.time()
        
        # Lanzamiento del guardian asincrono en segundo plano
        tarea_guardian = asyncio.create_task(self._monitorear_heartbeat())

        try:
            async for linea_bytes in respuesta_http.aiter_lines():
                if self._parar or self.estado == "DESCONECTADO":
                    break
                
                # CUALQUIER linea recibida (datos, eventos o lineas vacias) refresca el temporizador
                ultimo_pulso_activo = time.time()
                
                linea = linea_bytes.strip()
                if linea:
                    logger.debug(f"Payload crudo recibido: {linea}")
                    
        finally:
            # Garantizar la destruccion de la subtarea al salir del stream
            tarea_guardian.cancel()
            try:
                await tarea_guardian
            except asyncio.CancelledError:
                pass

    async def _conectar(self):
        """Efectua el handshake HTTP persistente."""
        url = self.construir_url()
        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
        
        timeout_config = httpx.Timeout(30.0, read=TIMEOUT_LECTURA)
        
        async with httpx.AsyncClient(timeout=timeout_config) as cliente_http:
            async with cliente_http.stream("GET", url, headers=headers) as respuesta:
                if respuesta.status_code == 200:
                    self.estado = "CONECTADO"
                    self.reintentos = 0
                    logger.info("Handshake SSE Exitoso. Canal de comunicacion establecido.")
                    await self._leer_stream(respuesta)
                else:
                    self.estado = "DESCONECTADO"

    async def iniciar(self):
        """Ciclo de vida principal con control de fallas por Backoff Exponencial."""
        if self.estado != "DESCONECTADO":
            raise RuntimeError(f"No se puede inicializar en estado: {self.estado}")
            
        self._parar = False
        espera_actual = ESPERA_INICIAL

        while not self._parar and self.reintentos < MAX_REINTENTOS:
            try:
                self.estado = "CONECTANDO"
                await self._conectar()
                
                # Si el guardian tumbo la conexion, disparamos el flujo de excepcion de reintento
                if self.estado == "DESCONECTADO" and not self._parar:
                    raise httpx.RequestError("Desconexion forzada por perdida de Heartbeat.")
                    
            except (httpx.RequestError, httpx.HTTPStatusError) as ex:
                self.estado = "DESCONECTADO"
                self.reintentos += 1
                logger.warning(f"Incidente de red detectado: {ex}. Reintento {self.reintentos}/{MAX_REINTENTOS}")
                
                if self.reintentos >= MAX_REINTENTOS:
                    logger.critical("Estrategia de mitigacion agotada. Deteniendo de forma permanente.")
                    break
                    
                await asyncio.sleep(espera_actual)
                espera_actual = min(60.0, espera_actual * 2.0)

        self.estado = "DESCONECTADO"

    def detener(self):
        """Cierre controlado por software."""
        self._parar = True
        self.estado = "DESCONECTADO"