import asyncio
import time
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI(title="Servidor SSE Falso de EcoMarket - Reto 3")

# Variable global para controlar de forma dinamica el estado del servidor desde la consola
# True = Funciona normal | False = Deja de mandar datos (Servidor Zombi / Colgamiento)
servidor_vivo = True

async def simulador_stream_sse(request: Request):
    """Generador asincrono que inyecta datos y simula fallos de conexion."""
    global servidor_vivo
    contador_id = 1
    
    # Sincronizacion inicial del bucle
    yield "retry: 3000\n\n"

    while True:
        # Si el cliente cancela la peticion desde su terminal, cerramos el bucle
        if await request.is_disconnected():
            print("[-] El cliente se ha desconectado del stream.")
            break

        if servidor_vivo:
            # Mandar un Heartbeat de control estructurado en texto plano SSE
            yield f"event: heartbeat\ndata: {{\"timestamp\": {time.time()}}}\nid: em-{contador_id}\n\n"
            print(f"[MOCK] Heartbeat 'em-{contador_id}' enviado con exito.")
            contador_id += 1
            await asyncio.sleep(10.0) # Pulso periodico cada 10 segundos
        else:
            # El servidor simula estar colgado (Zombi). Entra en silencio de radio completo.
            # No manda datos, pero tampoco rompe el socket TCP para forzar el salto del Watchdog.
            print("[MOCK DE FALLA] Servidor en silencio... Esperando que el Watchdog del cliente lo detecte.")
            await asyncio.sleep(5.0)

@app.get("/eventos")
async def obtener_eventos(modulos: str, request: Request):
    """Endpoint que emula el handshake de la API real de EcoMarket."""
    print(f"[HANDSHAKE] Cliente conectado pidiendo los modulos: {modulos}")
    return StreamingResponse(simulador_stream_sse(request), media_type="text/event-stream")


async def consola_control():
    """Hilo secundario asincrono para alternar fallas en caliente usando el teclado."""
    global servidor_vivo
    print("\n========================================================")
    print("  SIMULADOR DE FALLAS DE ENLACE ECOMARKET (CONSOLA)")
    print("========================================================")
    print(" Presione [ENTER] para congelar/reactivar el Heartbeat")
    print("========================================================\n")
    
    while True:
        # Espera interrupcion manual por teclado de forma asincrona
        await asyncio.to_thread(input)
        servidor_vivo = not servidor_vivo
        
        status = "ACTIVO (Normal)" if servidor_vivo else "CONGELADO (Zombi / Falla)"
        print(f"\n[ALERTA SIMULADOR] Estado del flujo cambiado a: {status}\n")


async def main():
    """Arranca de forma concurrente el servidor web y la consola de control de fallas."""
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    servidor = uvicorn.Server(config)
    
    # Corre ambas tareas en paralelo en el mismo loop
    await asyncio.gather(
        servidor.serve(),
        consola_control()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulador apagado de forma segura.")