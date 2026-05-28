import asyncio, httpx
from datetime import datetime

# =========================================================================================================
#  TRAZA SSE: t=0s -> GET /api/v1/alertas + Accept: text/event-stream -> Servidor responde 200 OK (chunked)
# ---------------------------------------------------------------------------------------------------------
# t=2s   | Servidor -> [id: 1, event: precio-actualizado, data: {"producto":"Mili","precio":47}] -> ID local = 1
# t=10s  | Servidor -> [id: 2, event: stack-critico, data: {"producto":"M01","stock":1}]       -> ID local = 2
# t=15s  | Servidor -> [: ping (Comentario Keep-Alive para mantener socket TCP activo)]           -> ID local = 2
# t=22s  | Servidor -> [id: 3, event: precio-actualizado, data: {"producto":"Mili","precio":45}] -> ID local = 3
# t=25s  | [¡CAIDA DE RED!] -> Conexion se rompe de golpe. Cliente retiene en memoria: Last-Event-ID = "3"
# t=28s  | [RECONEXION AUTOMATICA] -> Cliente espera 3s (retry) e intenta reconectar enviando:
#        | Header -> Last-Event-ID: 3
# =========================================================================================================
# POR QUE SSE REDUCE PETICIONES VACIAS COMPARADO CON POLLING:
# 1. Abre un unico canal TCP persistente en lugar de iniciar handshakes (SYN-ACK) y transferir headers HTTP repetitivamente en cada intervalo de consulta.
# 2. El servidor solo transmite bytes cuando realmente ocurre una actualizacion de inventario o un ping de mantenimiento, evitando responder con códigos 304 vacíos.
# =========================================================================================================

"""
RECEPTOR ALERTAS ECOMARKET – Decisiones de arquitectura (cliente)

SSE elegido sobre polling porque:
- Escenario A (Precios): SSE usa 1 conexión TCP persistente por cliente vs polling que genera 300k peticiones/min globales (a intervalo de 2s). El 99.9% serían respuestas HTTP 304 vacías, agotando la batería y datos móviles por renegociación de cabeceras. 
- Cómo falla el rechazado (Polling): Si el cliente procesa ráfagas de respuestas vacías, se genera un desperdicio crítico de CPU/batería en hilos de UI por operaciones i/o repetitivas. Con SSE, la latencia es mínima (<100ms) e instantánea.

Polling obligatorio sobre SSE/WebSockets porque:
- Escenario B (Inventario): El servidor legacy no soporta streaming (solo REST clásico). Se implementa Polling a 1s controlando la concurrencia con timeouts estrictos para abortar peticiones previas e inyectando Jitter (+/-150ms).
- Cómo falla el rechazado (SSE/WS o Polling sin control): Si el servidor antiguo tarda más de 1.0s por petición, un polling ingenuo acumula peticiones en paralelo (Request Piling), congelando el hilo principal de renderizado en el navegador del cliente al procesar ráfagas de datos desfasados empalmados.

Polling adaptativo elegido sobre SSE porque:
- Escenario C (Red inestable): Microcortes cada 20-30s rompen la conexión persistente de SSE. El Polling con Backoff Exponencial en el cliente detecta las fallas (ConnectionError) y duplica el intervalo de espera (2s, 4s, 8s...).
- Cómo falla el rechazado (SSE nativo): SSE reintenta reconectarse inmediatamente en bucle infinito. En redes inestables, esto obliga al módem del cliente a negociar handshakes TLS/TCP pesados continuamente, provocando sobrecalentamiento térmico y muerte de la batería en minutos.

SSE + HTTP POST elegido sobre WebSocket porque:
- Escenario D (Bidireccional): WebSockets introduce complejidad innecesaria de infraestructura (Sticky Sessions y proxies duplex). Una arquitectura híbrida mantiene SSE nativo para recibir alertas y envía filtros mediante POST estándar sobre HTTP/2.
- Cómo falla el rechazado (WebSockets): Los firewalls corporativos o escolares bloquean agresivamente el protocolo 'ws://' por inactividad. El cliente arrojaría un 'Connection timed out', rompiendo por completo la capacidad de la interfaz para recibir o enviar datos sin un F5 manual.
"""

2. Diagrama del Flujo de Red (Representación de Pizarra)
"""Configuracion simple"""
URL = "http://127.0.0.1:8000/api/v1"
TOKEN = "eyJ0eXAiO..."
INT_BASE, INT_MAX = 5, 60

class MonitorInventario:
    def __init__(self):
        self.observers = []
        self.etag = None
        self.estado = None
        self.intervalo = INT_BASE
        self.ejecutando = False

    async def _notificar(self, inventario):
        for obs in self.observers:
            try: await obs.actualizar(inventario)
            except Exception as e: print(f"Falló observador: {e}")

    async def _consultar(self):
        headers = {"Authorization": f"Bearer {TOKEN}"}
        if self.etag: headers["If-None-Match"] = self.etag
        
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{URL}/inventario", headers=headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data and "productos" in data:
                        self.etag = r.headers.get("ETag")
                        return data
                elif r.status_code == 503:
                    self.intervalo = min(self.intervalo * 2, INT_MAX)
                elif r.status_code in [400, 401]:
                    print(f"Error crítico {r.status_code}")
        except Exception as e:
            print(f"Error de red: {e}")
        return None

    async def iniciar(self):
        self.ejecutando = True
        while self.ejecutando:
            datos = await self._consultar()
            if datos and datos != self.estado:
                self.estado = datos
                await self._notificar(datos)
                self.intervalo = INT_BASE
            else:
                self.intervalo = min(self.intervalo + 5, INT_MAX)
            await asyncio.sleep(self.intervalo)


class ModuloCompras:
    async def actualizar(self, inv):
        for p in [x for x in inv['productos'] if x['status'] == "BAJO_MINIMO"]:
            print(f"[COMPRAS] Pedir: {p['nombre']}")

class ModuloAlertas:
    async def actualizar(self, inv):
        bajos = [p for p in inv['productos'] if p['status'] == "BAJO_MINIMO"]
        for p in bajos:
            payload = {
                "producto_id": p['id'], "stock_actual": p['stock'],
                "stock_minimo": p.get('stock_minimo', 0), "timestamp": datetime.now().isoformat()
            }
            try:
                async with httpx.AsyncClient() as c:
                    await c.post(f"{URL}/alertas", json=payload, headers={"Authorization": f"Bearer {TOKEN}"})
            except: pass 

"""Aqui es la ejecucion"""
async def main():
    m = MonitorInventario()
    m.observers = [ModuloCompras(), ModuloAlertas()]
    await m.iniciar()
    
    def detener(self):
        self.ejecutando = False
        print("Cierre suave iniciado...")

if __name__ == "__main__":
    asyncio.run(main())