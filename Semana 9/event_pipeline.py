"""
ECOMARKET - RESUMEN DE VULNERABILIDADES DEL SERVIDOR (ETAPA 19)

1. Caos por Thundering Herd (DDoS Auto-infligido):
Si miles de clientes se desconectan por una falla de red y todos intentan reconectarse 
al mismo milisegundo de forma agresiva (sin usar Backoff), la CPU del servidor colapsa 
al 100% intentando resolver el cifrado criptografico de tantas negociaciones SSL/TLS juntas.

2. Agotamiento de Descriptores (Socket Exhaustion):
Los clientes ineficientes que abren conexiones nuevas sin cerrar adecuadamente los sockets 
anteriores consumen rapido los File Descriptors del sistema operativo del backend. Esto 
hace que el servidor se quede sin recursos y comience a rechazar compras con errores HTTP 503.

3. Degradacion de la Base de Datos (I/O Bottleneck):
Si los clientes no implementan buffers o colas asincronas para procesar rafagas, saturan 
al servidor con miles de peticiones HTTP POST de confirmacion simultaneas. Esto genera 
bloqueos criticos (Deadlocks) y retrasos en las transacciones legitimas del negocio.
"""

import asyncio
import random
import logging
import time

"""
ECOMARKET - RESUMEN DE PROCESAMIENTO (RETO 3 - CONCLUSION PIPELINE)

1. Cola con limite (CAPACIDAD_COLA = 50):
Frena el consumo desmedido de memoria RAM en el dispositivo cliente ante rafagas masivas 
de alertas. Si la cola se llena, se activa el Backpressure para evitar un desborde de 
memoria (Out of Memory), priorizando la estabilidad del sistema sobre la recepcion de datos.

2. Pool de hilos virtuales (NUM_WORKERS = 3):
Permite procesar hasta 3 eventos pesados de forma simultanea (como guardar en disco o actualizar 
la interfaz) de manera asincrona sin congelar la UI principal. Mas workers en un terminal 
de bajos recursos generarian lentitud por la competencia de ciclos de CPU.

3. Sincronizacion activa (task_done y join):
El metodo join() asegura que el programa no destruya los Workers ni cierre los canales de 
forma abrupta si quedan tareas pendientes en el buffer. Cada Worker debe avisar con 
task_done() al terminar para evitar un congelamiento total (Deadlock logico).
"""

# Configuracion de logs unificada y sin acentos
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EcoMarketPipeline")

# CONSTANTES DE DISEÑO DEL FLUJO CONCURRENTE
NUM_WORKERS = 3           # Cantidad de hilos virtuales concurrentes (Trabajadores)
CAPACIDAD_COLA = 50       # Limite maximo de la cola (Mitiga desborde de memoria / Backpressure)

class EventPipeline:
    """Administra una cola de tareas asincrona con hilos virtuales de procesamiento."""
    
    def __init__(self):
        # Cola asincrona FIFO (First In, First Out) con limite de capacidad
        self.cola_tareas = asyncio.Queue(maxsize=CAPACIDAD_COLA)
        self.workers_activos = []
        self._parar = False

    async def trabajador_worker(self, worker_id: int):
        """Consumidor Asincrono: Extrae eventos de la cola y los procesa de forma paralela."""
        logger.info(f"[WORKER {worker_id}] Inicializado y escuchando la cola de tareas...")
        
        while not self._parar or not self.cola_tareas.empty():
            try:
                # Esperar a que exista un elemento disponible en la cola sin bloquear el loop
                # Se agrega un timeout corto para revisar periodicamente la bandera de parada
                evento = await asyncio.wait_for(self.cola_tareas.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            # --- INICIO DEL PROCESAMIENTO DE LA TAREA ---
            tipo = evento.get("tipo", "desconocido")
            payload = evento.get("datos", {})
            timestamp_creacion = evento.get("timestamp", time.time())
            
            latencia_cola = time.time() - timestamp_creacion
            logger.info(
                f"[WORKER {worker_id}] Procesando evento: '{tipo}' | "
                f"Tiempo en espera de cola: {latencia_cola:.3f}s"
            )

            # Simular una tarea pesada de entrada/salida (ej. Guardar en Base de Datos, Escribir Disco)
            # Al usar await, el Worker cede el control para que otros Workers procesen sus tareas
            tiempo_computo = random.uniform(0.1, 0.5)
            await asyncio.sleep(tiempo_computo)

            logger.info(f"[WORKER {worker_id}] Tarea finalizada con exito en {tiempo_computo:.2f}s.")
            
            # Notificar a la cola que la tarea fue completamente resuelta (Control de flujo)
            self.cola_tareas.task_done()

    async def productor_eventos(self):
        """Productor Asincrono: Simula la llegada masiva y asimetrica de alertas desde EcoMarket."""
        tipos_disponibles = ["precio_actualizado", "stock_critico", "pedido_nuevo"]
        
        for i in range(20):  # Simular ráfaga inicial de 20 eventos consecutivos
            tipo_elegido = random.choice(tipos_disponibles)
            evento_falso = {
                "id_evento": f"evt-{i:03d}",
                "tipo": tipo_elegido,
                "timestamp": time.time(),
                "datos": {"valor_operacion": random.uniform(10.0, 1000.0)}
            }

            try:
                # Intentar meter a la cola de forma no bloqueante.
                # Si la cola se llena (Backpressure), put_nowait lanza QueueFull
                self.cola_tareas.put_nowait(evento_falso)
                logger.info(f"[PRODUCTOR] Evento '{tipo_elegido}' (ID: evt-{i:03d}) encolado con exito.")
            except asyncio.QueueFull:
                logger.warning(f"[BACKPRESSURE ACTIVADO] Cola llena ({CAPACIDAD_COLA} items). Rebotando evento.")
                # Esperar un momento a que los workers liberen espacio antes de reintentar
                await asyncio.sleep(0.5)

            # Tiempo aleatorio entre la llegada de cada alerta externa
            await asyncio.sleep(random.uniform(0.05, 0.2))

    async def iniciar_pipeline(self):
        """Punto de entrada: Levanta el pool de Workers y corre el pipeline completo."""
        self._parar = False
        
        # 1. Crear e iniciar el pool de consumidores concurrentes
        self.workers_activos = [
            asyncio.create_task(self.trabajador_worker(i + 1))
            for i in range(NUM_WORKERS)
        ]

        # 2. Correr el flujo del productor de eventos y esperar a que termine de enviar todo
        await self.productor_eventos()

        # 3. Esperar a que todos los elementos encolados sean procesados por completo (cola vacia)
        await self.cola_tareas.join()
        
        # 4. Activar bandera de salida limpia para romper el bucle infinito de los Workers
        self._parar = True
        
        # Esperar la finalizacion de los Workers de forma segura
        await asyncio.gather(*self.workers_activos)
        logger.info("[PIPELINE] Procesamiento terminado. Todos los canales cerrados limpiamente.")

if __name__ == "__main__":
    pipeline = EventPipeline()
    try:
        asyncio.run(pipeline.iniciar_pipeline())
    except KeyboardInterrupt:
        print("\nPipeline interrumpido por el usuario.")