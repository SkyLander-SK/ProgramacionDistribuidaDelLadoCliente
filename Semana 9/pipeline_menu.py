import asyncio
import sys
import logging

# Importamos los componentes desarrollados previamente
from event_pipeline import EventPipeline
from carga_asimétrica import SimuladorCargaAsimetrica

# Configuracion de logging limpia y sin acentos
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EcoMarketPipelineMenu")

class MenuPipelineConcurrente:
    """Controla el ciclo de vida y los escenarios de estres de la cola desde la consola."""

    def __init__(self):
        self.pipeline = None
        self.simulador = None
        self.workers_tareas = []

    def mostrar_interfaz(self):
        """Despliega las opciones del menu por pantalla."""
        print("\n=========================================")
        print("    CONTROL DE OPERACIONES - PIPELINE     ")
        print("=========================================")
        print(" 1. Inicializar Pool de Workers (Consumidores)")
        print(" 2. Inyectar Rafaga de Carga Asimetrica")
        print(" 3. Ver Monitoreo y Carga en Buffer")
        print(" 4. Apagar Pipeline y Salir")
        print("=========================================")

    async def procesar_comando(self, comando: str):
        """Maneja las tareas asincronas segun la opcion seleccionada."""
        if comando == "1":
            if self.pipeline:
                print("\n[!] El pool de Workers ya fue inicializado y escucha de fondo.")
                return
                
            print("\n[+] Levantando e instanciando el canal de datos asincrono...")
            self.pipeline = EventPipeline()
            self.simulador = SimuladorCargaAsimetrica(pipeline=self.pipeline)
            
            # Inicializar los 3 Workers en segundo plano usando create_task
            self.workers_tareas = [
                asyncio.create_task(self.pipeline.trabajador_worker(i + 1))
                for i in range(3) # NUM_WORKERS = 3
            ]
            print(f"[+] Pool de 3 Workers activo. Estado: Escuchando cola FIFO.")

        elif comando == "2":
            if not self.pipeline:
                print("\n[!] Error: Primero debe inicializar el pool con la opcion 1.")
                return
                
            print("\n[+] Disparando escenario de estres asimetrico...")
            # Lanza las rafagas violentas en segundo plano sin congelar la escucha del menu
            asyncio.create_task(self.simulador.ejecutar_escenario_estres())

        elif comando == "3":
            if not self.pipeline:
                print("\n[ESTADO] Pipeline no inicializado.")
                return
                
            tamano_cola = self.pipeline.cola_tareas.qsize()
            max_cola = self.pipeline.cola_tareas.maxsize
            print(f"\n[MONITOREO] Elementos en buffer: {tamano_cola} / {max_cola}")
            print(f"[MONITOREO] Workers activos procesando: {len(self.workers_tareas)}")

        elif comando == "4":
            if self.pipeline:
                print("\n[-] Vaciando buffers pendientes... Espere.")
                await self.pipeline.cola_tareas.join() # Bloquea hasta procesar el ultimo elemento
                self.pipeline._parar = True
                await asyncio.gather(*self.workers_tareas) # Cierre limpio de tareas de fondo
                print("[-] Pool de Workers destruido de forma segura.")
            print("Cerrando la aplicacion de control de operaciones. Adios.")
            sys.exit(0)
        else:
            print("\n[!] Comando no reconocido. Intente un numero del 1 al 4.")

    async def bucle_interactivo(self):
        """Captura los comandos de teclado sin detener las operaciones concurrentes."""
        while True:
            self.mostrar_interfaz()
            # Lee la consola en un hilo virtual separado para no bloquear las alertas de fondo
            comando = await asyncio.to_thread(input, "Seleccione una opcion (1-4): ")
            try:
                await self.procesar_comando(comando.strip())
            except SystemExit:
                break
            except Exception as e:
                logger.error(f"Incidente en el bucle de ejecucion: {e}")

if __name__ == "__main__":
    menu = MenuPipelineConcurrente()
    try:
        # Iniciamos el motor asincrono global
        asyncio.run(menu.bucle_interactivo())
    except KeyboardInterrupt:
        print("\n\n[-] Ctrl+C detectado. Forzando vaciado y apagado seguro de sockets...")
        if menu.pipeline:
            menu.pipeline._parar = True
        print("[-] Pipeline cerrado de manera integra.")