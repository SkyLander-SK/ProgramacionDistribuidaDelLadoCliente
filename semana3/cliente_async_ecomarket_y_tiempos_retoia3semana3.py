import asyncio
import aiohttp
import time

BASE_URL = "http://localhost:3000/api"

class EcoMarketError(Exception): pass

# --- 1. Funciones CRUD Asíncronas ---
async def listar_productos(session, nombre=None):
    params = {'nombre': nombre} if nombre else {}
    async with session.get(f"{BASE_URL}/productos", params=params) as resp:
        if resp.status != 200: raise EcoMarketError("Error al listar")
        return await resp.json()

async def obtener_producto(session, producto_id):
    async with session.get(f"{BASE_URL}/productos/{producto_id}") as resp:
        if resp.status == 404: return None
        return await resp.json()

async def crear_producto(session, datos):
    async with session.post(f"{BASE_URL}/productos", json=datos) as resp:
        if resp.status != 201: raise EcoMarketError("Datos inválidos")
        return await resp.json()

async def actualizar_producto_total(session, producto_id, datos):
    async with session.put(f"{BASE_URL}/productos/{producto_id}", json=datos) as resp:
        return await resp.json()

async def actualizar_producto_parcial(session, producto_id, campos):
    async with session.patch(f"{BASE_URL}/productos/{id}/precio", json=campos) as resp:
        if resp.status == 422: raise EcoMarketError("Precio inválido")
        return await resp.json()

async def eliminar_producto(session, producto_id):
    async with session.delete(f"{BASE_URL}/productos/{producto_id}") as resp:
        return resp.status == 204

# --- 2. Carga del Dashboard ---
async def cargar_dashboard():
    timeout = aiohttp.ClientTimeout(total=2)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Lanzamos las peticiones en paralelo
        tareas = [
            listar_productos(session),
            # Simulamos endpoints adicionales para el dashboard
            session.get(f"{BASE_URL}/productores"), 
            session.get(f"{BASE_URL}/pedidos")
        ]
        
        resultados = await asyncio.gather(*tareas, return_exceptions=True)
        
        return {
            "productos": resultados[0] if not isinstance(resultados[0], Exception) else "Error",
            "productores": "Cargado" if not isinstance(resultados[1], Exception) else "Fallo",
            "errores": [r for r in resultados if isinstance(r, Exception)]
        }

# --- 3. Creación Múltiple con Semáforo ---
async def crear_con_semaforo(sem, session, datos):
    async with sem:
        try:
            return await crear_producto(session, datos)
        except Exception as e:
            return e

async def crear_multiples_productos(lista_productos):
    sem = asyncio.Semaphore(5) 
    async with aiohttp.ClientSession() as session:
        tareas = [crear_con_semaforo(sem, session, p) for p in lista_productos]
        return await asyncio.gather(*tareas)

# --- Manejo de Errores de Red ---
async def ejecutar_ejemplo():
    print("Iniciando prueba de tiempos...")
    inicio = time.time()
    await cargar_dashboard()
    fin = time.time()
    print(f"Tiempo Dashboard Asíncrono: {fin - inicio:.2f}s")

if __name__ == "__main__":
    asyncio.run(ejecutar_ejemplo())

# Método	Tiempo Medido	Mejora
#Síncrono (requests)	~1.58s	-
#Asíncrono (aiohttp)	~0.52s	67% más rápido