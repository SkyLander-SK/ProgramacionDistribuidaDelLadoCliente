import asyncio
import time
import logging

# Configuracion de logs sin acentos para el modulo de filtrado
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EcoMarketFiltro")

# REQUERIMIENTO ETAPA 20: Estructura de control para tracking de estados anteriores
# Guarda el ultimo valor procesado por cada tipo de evento para evitar duplicados criticos
historico_estados = {
    "precio_actualizado": 0.0,
    "stock_critico": 0.0,
    "pedido_nuevo": 0.0
}

# Constante de umbral de negocio (Filtro de relevancia)
UMBRAL_MINIMO_PRECIO = 50.0

class WorkerConFiltrado:
    """Implementa logica de descarte temprano de alertas para proteger la CPU del cliente."""

    @staticmethod
    def es_evento_valido_y_mutado(evento: dict) -> bool:
        """
        Aplica filtros logicos antes de mandar el evento a la cola o al procesamiento pesado.
        Retorna True si el evento aporta informacion nueva o supera los umbrales basicos.
        """
        global historico_estados
        tipo = evento.get("tipo")
        datos = evento.get("datos", {})
        valor_actual = datos.get("valor_operacion", 0.0)

        # 1. Filtro de Relevancia (Umbral de Negocio)
        if tipo == "precio_actualizado" and valor_actual < UBRAL_MINIMO_PRECIO:
            logger.debug(f"[FILTRO - RECHAZADO] Precio ${valor_actual} por debajo del umbral (${UMBRAL_MINIMO_PRECIO}).")
            return False

        # 2. Filtro de Idempotencia / Mutacion (Evita procesar datos identicos)
        ultimo_valor_registrado = historico_estados.get(tipo, 0.0)
        if valor_actual == ultimo_valor_registrado:
            logger.debug(f"[FILTRO - DESCARTE] Evento '{tipo}' ignorado. El valor no ha cambiado (${valor_actual}).")
            return False

        # Si pasa los filtros, actualizamos el historico para las siguientes verificaciones
        historico_estados[tipo] = valor_actual
        return True

    async def trabajador_optimizado(self, worker_id: int, cola_tareas: asyncio.Queue):
        """Worker Consumidor que integra el descarte eficiente antes del computo pesado."""
        logger.info(f"[WORKER {worker_id}] Inicializado con filtros de optimizacion de CPU activos.")
        
        while True:
            evento = await cola_tareas.get()
            tipo = evento.get("tipo")
            valor = evento.get("datos", {}).get("valor_operacion", 0.0)

            # EVALUACION DE FILTRADO EFICIENTE (Etapa 20)
            if not self.es_evento_valido_y_mutado(evento):
                logger.info(f"[WORKER {worker_id}] ----> DESCARTE COMPLETO: Alerta '{tipo}' (${valor}) evito uso de CPU.")
                cola_tareas.task_done()
                continue

            # Computo pesado simulatado (Solo se ejecuta si los datos realmente mutaron o son criticos)
            logger.info(f"[WORKER {worker_id}] 🟩 [PROCESANDO CRITICO] Alerta validada de '{tipo}' (${valor}).")
            await asyncio.sleep(0.3) # Simula renderizado en UI o guardado en disco
            
            logger.info(f"[WORKER {worker_id}] Tarea completada con exito.")
            cola_tareas.task_done()

# Script de prueba rápida para validar los descartes
async def main():
    cola = asyncio.Queue()
    worker = WorkerConFiltrado()
    
    # Levantar el worker optimizado
    asyncio.create_task(worker.trabajador_optimizado(worker_id=1, cola_tareas=cola))

    # Inyectar casos de prueba:
    print("\n=== CASO 1: Inyeccion de precio bajo el umbral ($10.0) ===")
    cola.put_nowait({"tipo": "precio_actualizado", "datos": {"valor_operacion": 10.0}})
    
    print("\n=== CASO 2: Inyeccion de precio valido ($120.0) ===")
    cola.put_nowait({"tipo": "precio_actualizado", "datos": {"valor_operacion": 120.0}})
    
    print("\n=== CASO 3: Inyeccion de precio duplicado exactamente igual ($120.0) ===")
    cola.put_nowait({"tipo": "precio_actualizado", "datos": {"valor_operacion": 120.0}})

    await cola.join()
    print("\n=== FIN DE LA VERIFICACION DE FILTRADO ===")

if __name__ == "__main__":
    asyncio.run(main())