import asyncio
import aiohttp
import time

class SmartSession:
    def __init__(self, limit=20, ttl_dns=300):
        # Configuramos el conector con límites específicos
        self.connector = aiohttp.TCPConnector(
            limit=limit, 
            ttl_dns_cache=ttl_dns,
            keepalive_timeout=60
        )
        self.session = aiohttp.ClientSession(connector=self.connector)
        self._metrics = {"created": 0, "reused": 0}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    async def get(self, url, **kwargs):
        # Monitoreo simple del estado del pool
        active = len(self.connector.active_connections)
        total = self.connector.limit
        print(f"📊 Pool Status: {active}/{total} conexiones activas")
        
        async with self.session.get(url, **kwargs) as response:
            return await response.json()

    def get_pool_report(self):
        return {
            "limit": self.connector.limit,
            "active": len(self.connector.active_connections),
            "acquired": self.connector.total_conns
        }

# --- 3. Benchmark de Configuración de Pool ---
async def run_pool_benchmark(limit_size):
    url = "http://localhost:3000/api/productos"
    start = time.perf_counter()
    
    # 50 peticiones con 100ms de delay simulado
    async with aiohttp.TCPConnector(limit=limit_size) as connector:
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for _ in range(50):
                tasks.append(asyncio.create_task(session.get(url)))
                # Simulamos delay de red local
                await asyncio.sleep(0.01) 
            
            await asyncio.gather(*tasks)
            
    end = time.perf_counter()
    return end - start

async def main():
    for limit in [5, 20, 0]: # 0 es ilimitado en aiohttp
        t = await run_pool_benchmark(limit)
        print(f"🚀 Pool Limit {limit if limit != 0 else '∞'}: {t:.4f}s")

if __name__ == "__main__":
    asyncio.run(main())