import asyncio
import aiohttp
import time

BASE_URL = "http://localhost:3000/api"

# --- 1. Timeout Individual con Wrapper ---
async def peticion_con_timeout(coro, segundos):
    """Envuelve una petición con un tiempo límite específico."""
    try:
        return await asyncio.wait_for(coro, timeout=segundos)
    except asyncio.TimeoutError:
        print(f"⚠️ [Timeout] Una petición excedió los {segundos}s y fue abortada.")
        return None

# --- 2. Cancelación en Grupo ---
async def cargar_con_seguridad(session):
    """Si el perfil falla con 401, cancela todo lo demás."""
    tareas = {
        "productos": asyncio.create_task(session.get(f"{BASE_URL}/productos")),
        "perfil": asyncio.create_task(session.get(f"{BASE_URL}/perfil")) # Simular 401 aquí
    }
    
    try:
        # Esperamos a que cualquiera termine
        done, pending = await asyncio.wait(tareas.values(), return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            resp = await task
            if resp.url.path.endswith("/perfil") and resp.status == 401:
                print("🚨 [Auth] 401 Detectado. Cancelando peticiones restantes...")
                for p in pending:
                    p.cancel()
                return {"error": "No autorizado", "data": None}
                
        return {"error": None, "data": "Dashboard cargado"}
    except Exception as e:
        return {"error": str(e)}

# --- 3. Carga con Prioridad (Procesamiento conforme llegan) ---
async def cargar_con_prioridad(session):
    """Procesa resultados conforme llegan y prioriza datos críticos."""
    urls = [
        f"{BASE_URL}/productos",  # Crítica
        f"{BASE_URL}/perfil",     # Crítica
        f"{BASE_URL}/categorias", # Secundaria (lenta)
        f"{BASE_URL}/pedidos"     # Secundaria
    ]
    
    tareas = [asyncio.create_task(session.get(u)) for u in urls]
    criticos_listos = 0
    resultados = []

    # as_completed nos da un iterador que rinde conforme terminan
    for coro_listo in asyncio.as_completed(tareas):
        try:
            resp = await coro_listo
            resultados.append(resp.url.path)
            print(f"✅ Llegó respuesta de: {resp.url.path}")
            
            # Lógica de prioridad
            if "/productos" in resp.url.path or "/perfil" in resp.url.path:
                criticos_listos += 1
            
            if criticos_listos == 2:
                print("⚡ [Prioridad] Datos críticos listos. Renderizando Dashboard Parcial...")
                
        except Exception as e:
            print(f"❌ Error en petición: {e}")

    return resultados

# --- Test de Comportamiento ---
async def main():
    async with aiohttp.ClientSession() as session:
        print("\n--- TEST 1: Timeout Individual ---")
        # Simulamos que categorías tarda 8s, pero el timeout es 3s
        # (En un server real se vería el delay, aquí usamos un mock mental)
        res = await peticion_con_timeout(session.get(f"{BASE_URL}/productos"), 5)
        print("Productos completado con éxito.")

        print("\n--- TEST 2: Carga con Prioridad ---")
        await cargar_con_prioridad(session)

if __name__ == "__main__":
    asyncio.run(main())