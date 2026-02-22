import asyncio
import time
import aiohttp
from collections import deque

# --- 1. Limitador de Concurrencia (Semaphore) ---
class ConcurrencyLimiter:
    def __init__(self, n):
        self.semaphore = asyncio.Semaphore(n)
        self.in_flight = 0

    async def __aenter__(self):
        await self.semaphore.acquire()
        self.in_flight += 1
        print(f"🚀 Petición en vuelo. Total actual: {self.in_flight}")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.in_flight -= 1
        self.semaphore.release()

# --- 2. Limitador de Tasa (Token Bucket) ---
class RateLimiter:
    def __init__(self, rate_per_second):
        self.rate = rate_per_second
        self.tokens = rate_per_second
        self.updated_at = time.monotonic()
        self.queue = deque()

    async def wait(self):
        now = time.monotonic()
        # Rellenar tokens basados en el tiempo transcurrido
        self.tokens += (now - self.updated_at) * self.rate
        if self.tokens > self.rate:
            self.tokens = self.rate
        self.updated_at = now

        if self.tokens < 1:
            wait_time = (1 - self.tokens) / self.rate
            print(f"⏳ Rate limit excedido. Esperando {wait_time:.2f}s en cola...")
            await asyncio.sleep(wait_time)
            # Recursión para re-verificar tras la espera
            return await self.wait()
        
        self.tokens -= 1

# --- 3. ThrottledClient (Combinado) ---
class ThrottledClient:
    def __init__(self, max_concurrent, max_per_second):
        self.concurrency = ConcurrencyLimiter(max_concurrent)
        self.rate_limiter = RateLimiter(max_per_second)

    async def execute(self, coro):
        # Primero respetamos la tasa (cuántas por segundo)
        wait_start = time.monotonic()
        await self.rate_limiter.wait()
        wait_duration = time.monotonic() - wait_start

        # Luego respetamos la concurrencia (cuántas abiertas al mismo tiempo)
        async with self.concurrency:
            result = await coro
            return result, wait_duration

# --- 4. Test de Stress: 50 Productos ---
async def test_throttling():
    client = ThrottledClient(max_concurrent=10, max_per_second=20)
    
    async with aiohttp.ClientSession() as session:
        async def mock_post(i):
            # Simula una petición POST que tarda 0.5s en el servidor
            url = f"http://localhost:3000/api/productos"
            return await client.execute(session.get(url)) # Usamos GET para el mock

        print("--- Iniciando envío de 50 peticiones ---")
        start_time = time.monotonic()
        
        tareas = [mock_post(i) for i in range(50)]
        resultados = await asyncio.gather(*tareas)
        
        total_time = time.monotonic() - start_time
        print(f"\n✅ Test Finalizado")
        print(f"⏱️ Tiempo total: {total_time:.2f}s")
        print(f"📈 Throughput real: {50/total_time:.2f} req/s")

if __name__ == "__main__":
    asyncio.run(test_throttling())