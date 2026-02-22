import asyncio
import time

async def fetch(name, delay, fail=False):
    await asyncio.sleep(delay)
    if fail: raise Exception(f"Error en {name}")
    return f"Datos de {name}"

# --- ESTRATEGIA 1: GATHER ---
async def estrategia_gather():
    print("\n--- Ejecutando GATHER (Esperar a todos) ---")
    start = time.time()
    try:
        # return_exceptions=True permite que los exitosos se guarden
        res = await asyncio.gather(
            fetch("Categorías", 0.1), fetch("Productos", 0.2), 
            fetch("Perfil", 0.5), fetch("Notas", 2.0, fail=True),
            return_exceptions=True
        )
        print(f"Finalizado en {time.time()-start:.2f}s. Resultados: {len(res)}")
    except Exception as e:
        print(f"Falló el bloque: {e}")

# --- ESTRATEGIA 2: FIRST_COMPLETED ---
async def estrategia_first_completed():
    print("\n--- Ejecutando FIRST_COMPLETED (Latencia mínima) ---")
    start = time.time()
    tasks = [
        asyncio.create_task(fetch("Categorías", 0.1)),
        asyncio.create_task(fetch("Perfil", 0.5))
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in done:
        print(f"Primer dato visible ({t.result()}) a los {time.time()-start:.2f}s")
    # Limpieza: Cancelar pendientes si no se necesitan
    for p in pending: p.cancel()

# --- ESTRATEGIA 3: AS_COMPLETED ---
async def estrategia_as_completed():
    print("\n--- Ejecutando AS_COMPLETED (Progresivo) ---")
    start = time.time()
    tasks = [fetch("Categorías", 0.1), fetch("Productos", 0.2), fetch("Perfil", 0.5)]
    for coro in asyncio.as_completed(tasks):
        res = await coro
        print(f"Dato recibido: {res} a los {time.time()-start:.2f}s")

# --- ESTRATEGIA 4: FIRST_EXCEPTION ---
async def estrategia_first_exception():
    print("\n--- Ejecutando FIRST_EXCEPTION (Abortar rápido) ---")
    tasks = [
        asyncio.create_task(fetch("Productos", 0.2)),
        asyncio.create_task(fetch("Perfil", 0.5, fail=True))
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    print(f"Operación abortada. Una tarea falló. Pendientes canceladas: {len(pending)}")
    for p in pending: p.cancel()

async def main():
    await estrategia_gather()
    await estrategia_first_completed()
    await estrategia_as_completed()
    await estrategia_first_exception()

if __name__ == "__main__":
    asyncio.run(main())