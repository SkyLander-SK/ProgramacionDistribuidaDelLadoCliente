import asyncio
import random
import time
import logging

# Configuracion de logs sin acentos para visualizar la carga asimetrica
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EcoMarketCarga")

from event_pipeline import EventPipeline

class SimuladorCargaAsimetrica:
    """Genera rafagas desiguales y masivas de eventos para estresar el pool de Workers."""

    def __init__(self, pipeline: EventPipeline):
        self.pipeline = pipeline

    async def inyectar_bloque_rafaga(self, tipo_evento: str, cantidad: int, delay_interno: float):
        """Inyecta un grupo concentrado de eventos de un solo golpe para simular picos de demanda."""
        logger.info(f"[SIMULADOR] ---> Iniciando rafaga asimetrica: {cantidad} eventos de tipo '{tipo_evento}'")
        
        for i in range(cantidad):
            evento = {
                "id_evento": f"asym-{tipo_evento[:3]}-{i:03d}",
                "tipo": tipo_evento,
                "timestamp": time.time(),
                "datos": {"impacto": random.randint(1, 100)}
            }
            
            try:
                # El pipeline controla el Backpressure si la cola llega a 50 elementos
                self.pipeline.cola_tareas.put_nowait(evento)
            except asyncio.QueueFull:
                logger.warning(f"[ALERTA COLA LLENA] Backpressure activo en rafaga de {tipo_evento}. Rebotado.")
                await asyncio.sleep(0.2) # Espera de mitigacion corta
                
            await asyncio.sleep(delay_interno)

    async def ejecutar_escenario_estres(self):
        """
        REQUERIMIENTO ETAPA 13: Carga Asimetrica
        Simula un escenario real: 50 cambios de precios criticos juntos, 
        seguidos de alertas de stock e inyeccion esporadica de pedidos de alto valor.
        """
        # Fase 1: Pico masivo de Precios (Rafaga violenta muy rapida)
        tarea_precios = asyncio.create_task(
            self.inyectar_bloque_rafaga(tipo_evento="precio_actualizado", cantidad=35, delay_interno=0.01)
        )

        # Fase 2: Alertas de Stock Critico (Llegada constante paralela)
        tarea_stock = asyncio.create_task(
            self.inyectar_bloque_rafaga(tipo_evento="stock_critico", cantidad=15, delay_interno=0.05)
        )

        # Fase 3: Pedidos Nuevos Mayoristas (Llegada lenta y esporadica)
        tarea_pedidos = asyncio.create_task(
            self.inyectar_bloque_rafaga(tipo_evento="pedido_nuevo", quantity=10, delay_interno=0.15)
        )

        # Esperamos a que los tres flujos asimetricos terminen de rellenar la cola
        await asyncio.gather(tarea_precios, tarea_stock, tarea_pedidos)
        logger.info("[SIMULADOR] <--- Toda la carga asimetrica fue inyectada con exito.")

async def main():
    # 1. Instanciamos el pipeline core con sus 3 workers de fondo
    pipeline_core = EventPipeline()
    simulador = SimuladorCargaAsimetrica(pipeline=pipeline_core)

    # Levantamos el pool de Workers asincronos
    pipeline_core.workers_activos = [
        asyncio.create_task(pipeline_core.trabajador_worker(i + 1))
        for i in range(3) # NUM_WORKERS = 3
    ]

    # 2. Corremos la simulacion de la ráfaga asimetrica
    print("\n=== INICIANDO SIMULACION DE CARGA ASIMETRICA (ETAPA 13) ===\n")
    await simulador.ejecutar_escenario_estres()

    # 3. Esperamos a que el buffer de la cola se vacie por completo de forma segura
    await pipeline_core.cola_tareas.join()
    
    # Cierre limpio
    pipeline_core._parar = True
    await asyncio.gather(*pipeline_core.workers_activos)
    print("\n=== SIMULACION COMPLETADA: COLA VACIA Y WORKERS APAGADOS ===")

if __name__ == "__main__":
    asyncio.run(main())