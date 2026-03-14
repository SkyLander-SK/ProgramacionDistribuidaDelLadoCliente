import asyncio, httpx
from datetime import datetime

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