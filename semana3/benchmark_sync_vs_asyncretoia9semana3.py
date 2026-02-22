import asyncio
import time
import tracemalloc
import requests
import aiohttp
import pandas as pd # Para formatear tablas en consola

# Configuración del Benchmark
LATENCIA_MS = 200 / 1000  # 200ms convertidos a segundos
URLS_DASHBOARD = ["http://localhost:3000/api/productos"] * 4
ITERACIONES = 5

# --- Clientes de Prueba ---
def fetch_sync(urls):
    results = []
    for url in urls:
        time.sleep(LATENCIA_MS) # Simula delay del servidor
        r = requests.get(url)
        results.append(r.status_code)
    return results

async def fetch_async(urls):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            async def get_with_delay(u):
                await asyncio.sleep(LATENCIA_MS)
                async with session.get(u) as r:
                    return r.status
            tasks.append(get_with_delay(url))
        return await asyncio.gather(*tasks)

# --- Motor de Benchmark ---
def run_benchmark(name, func, data, is_async=False):
    tracemalloc.start()
    start_time = time.perf_counter()
    
    if is_async:
        asyncio.run(func(data))
    else:
        func(data)
    
    end_time = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    total_time = end_time - start_time
    return {
        "Estrategia": name,
        "Tiempo Total (s)": round(total_time, 4),
        "Memoria Peak (KB)": round(peak / 1024, 2),
        "Throughput (req/s)": round(len(data) / total_time, 2)
    }

def ejecutar_suite():
    print(f"--- Iniciando Benchmark EcoMarket (Latencia: {LATENCIA_MS*1000}ms) ---")
    
    # Escenario: Dashboard (4 peticiones)
    res_sync = run_benchmark("Síncrono (Req)", fetch_sync, URLS_DASHBOARD)
    res_async = run_benchmark("Asíncrono (Aio)", fetch_async, URLS_DASHBOARD)
    
    df = pd.DataFrame([res_sync, res_async])
    speedup = res_sync["Tiempo Total (s)"] / res_async["Tiempo Total (s)"]
    
    print("\n### TABLA COMPARATIVA: ESCENARIO DASHBOARD ###")
    print(df.to_string(index=False))
    print(f"\n🚀 SPEEDUP: La versión asíncrona es {speedup:.2f}x más rápida.")

if __name__ == "__main__":
    ejecutar_suite()