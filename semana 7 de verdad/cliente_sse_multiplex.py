# ==========================================
# PARTE 1: IMPORTACIONES Y CONSTANTES
# ==========================================
import asyncio
import httpx
import json
import logging
import time
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EcoMarket")

BASE_URL = "https://api.ecomarket.com/eventos"
TIMEOUT  = httpx.Timeout(30.0, read=30.0)
MAX_REINTENTOS = 5
ESPERA_INICIAL = 1.0


# ==========================================
# PARTE 2: LAS CLASES (EventRouter y Cliente)
# ==========================================
class EventRouter:
    def __init__(self):
        self.handlers = {}

    def registrar(self, tipo, fn):
        if tipo not in self.handlers:
            self.handlers[tipo] = []
        self.handlers[tipo].append(fn)

    def desregistrar(self, tipo, fn):
        if tipo in self.handlers and fn in self.handlers[tipo]:
            self.handlers[tipo].remove(fn)

    def despachar(self, tipo, datos):
        if tipo not in self.handlers:
            return
        for fn in self.handlers[tipo]:
            try:
                fn(datos)
            except Exception as e:
                logger.error(f"Handler para '{tipo}' falló: {e}")
                continue


class ClienteSSEMultiplex:
    def __init__(self, modulos: list):
        self.modulos = modulos          
        self.router  = EventRouter()    
        self.estado  = "DESCONECTADO"   
        self.reintentos = 0             
        self.ultimo_id  = None          
        self._parar     = False         

    def suscribir(self, tipo_evento, handler_fn):
        self.router.registrar(tipo_evento, handler_fn)

    def construir_url(self):
        query_param = ",".join(self.modulos)
        return f"{BASE_URL}?modulos={query_param}"

    def _parsear_linea(self, linea: str, evento_parcial: dict) -> dict:
        linea = linea.strip()
        if not linea or linea.startswith(":"):
            return evento_parcial

        if ":" in linea:
            campo, valor = linea.split(":", 1)
            campo = campo.strip()
            valor = valor.lstrip()
            
            if campo == "event":
                evento_parcial["event"] = valor
            elif campo == "data":
                evento_parcial["data"] = evento_parcial.get("data", "") + valor
            elif campo == "id":
                evento_parcial["id"] = valor
        return evento_parcial

    def _procesar_evento(self, evento_parcial: dict) -> dict:
        if not evento_parcial:
            return {}

        if "id" in evento_parcial:
            self.ultimo_id = evento_parcial["id"]

        tipo = evento_parcial.get("event", "message")
        raw_data = evento_parcial.get("data", "")

        datos = {}
        if raw_data:
            try:
                datos = json.loads(raw_data)
            except json.JSONDecodeError:
                datos = {"raw": raw_data}

        self.router.despachar(tipo, datos)
        return {}

    async def _leer_stream(self, respuesta_http):
        evento_parcial = {}
        async for linea_bytes in respuesta_http.aiter_lines():
            if self._parar:
                break
            linea = linea_bytes.strip()
            if not linea:
                evento_parcial = self._procesar_evento(evento_parcial)
            else:
                evento_parcial = self._parsear_linea(linea_bytes, evento_parcial)

    async def _conectar(self):
        url = self.construir_url()
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
        if self.ultimo_id is not None:
            headers["Last-Event-ID"] = str(self.ultimo_id)

        async with httpx.AsyncClient(timeout=TIMEOUT) as cliente_http:
            async with cliente_http.stream("GET", url, headers=headers) as respuesta:
                if respuesta.status_code == 200:
                    self.estado = "CONECTADO"
                    self.reintentos = 0
                    logger.info(f"Conexión SSE establecida con éxito. Estado: {self.estado}")
                    await self._leer_stream(respuesta)
                else:
                    raise httpx.HTTPStatusError(f"Error HTTP: {respuesta.status_code}", request=respuesta.request, response=respuesta)

    async def iniciar(self):
        if self.estado != "DESCONECTADO":
            raise RuntimeError(f"Falla de Invariante: No se puede iniciar en estado {self.estado}")

        self._parar = False
        espera_actual = ESPERA_INICIAL

        while not self._parar and self.reintentos < MAX_REINTENTOS:
            try:
                self.estado = "CONECTANDO"
                logger.info(f"Intento de conexión {self.reintentos + 1}/{MAX_REINTENTOS}...")
                await self._conectar()
            except (httpx.RequestError, httpx.HTTPStatusError) as ex:
                self.estado = "DESCONECTADO"
                self.reintentos += 1
                logger.warning(f"Error de transporte: {ex}")
                
                if self.reintentos >= MAX_REINTENTOS:
                    logger.critical("Límite alcanzado. Deteniendo.")
                    break

                await asyncio.sleep(espera_actual)
                espera_actual = min(60.0, espera_actual * 2.0)
        self.estado = "DESCONECTADO"

    def detener(self):
        self._parar = True
        self.estado = "DESCONECTADO"


# ==========================================
# PARTE 3: AQUÍ VAN LOS HANDLERS DE NEGOCIO
# ==========================================
def handler_precio_actualizado(datos: dict):
    producto = datos.get("producto", "Desconocido")
    precio_anterior = datos.get("precio_anterior", 0.0)
    precio_nuevo = datos.get("precio_nuevo", 0.0)
    if precio_anterior > 0:
        porcentaje_cambio = abs((precio_nuevo - precio_anterior) / precio_anterior) * 100
        if porcentaje_cambio > 5.0:
            print(f"\n⚠️  [ALERTA CRÍTICA - PRECIOS] {producto} cambió {porcentaje_cambio:.2f}% (${precio_anterior} -> ${precio_nuevo})")

def handler_stock_critico(datos: dict):
    item = datos.get("item", "Producto indeterminado")
    stock_actual = datos.get("stock_actual", 0)
    if stock_actual <= 5:
        print(f"\n🔥 [ALERTA INVENTARIO CRÍTICO] Ítem: '{item}' | Stock: {stock_actual} unidades")

def handler_pedido_nuevo(datos: dict):
    pedido_id = datos.get("pedido_id", "N/A")
    total = datos.get("total", 0.0)
    if total > 500.0:
        print(f"\n💰 [ALERTA - PEDIDO MAYORISTA] ID: {pedido_id} | Total: ${total:.2f}")

def handler_heartbeat(datos: dict):
    handler_heartbeat.ultimo_pulso_activo = datos.get("timestamp", time.time())

handler_heartbeat.ultimo_pulso_activo = time.time()


# ==========================================
# PARTE 4: PUNTO DE ARRANQUE (MAIN LOOP)
# ==========================================
async def main():
    # 1. Instanciar el cliente con los módulos requeridos
    cliente = ClienteSSEMultiplex(modulos=["precios", "inventario", "pedidos"])

    # 2. Suscribir los Handlers que acabamos de poner arriba
    cliente.suscribir("precio_actualizado", handler_precio_actualizado)
    cliente.suscribir("stock_critico", handler_stock_critico)
    cliente.suscribir("pedido_nuevo", handler_pedido_nuevo)
    cliente.suscribir("heartbeat", handler_heartbeat)

    # 3. Arrancar el cliente asíncrono
    await cliente.initiate()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCliente detenido manualmente por el usuario.")