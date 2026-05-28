import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import time

# Importamos el componente de la cola asincrona que armamos antes
# Asegurate de que el archivo 'event_pipeline.py' este en la misma carpeta
from event_pipeline import EventPipeline, CAPACIDAD_COLA

class TestEventPipelineConcurrente(unittest.IsolatedAsyncioTestCase):
    """Bateria de pruebas automatizadas para validar el pool de Workers y la cola FIFO."""

    def setUp(self):
        self.pipeline = EventPipeline()

    def test_inicializacion_y_limites_base(self):
        """Verifica las invariantes de configuracion inicial del pipeline."""
        self.assertEqual(self.pipeline.cola_tareas.maxsize, CAPACIDAD_COLA)
        self.assertFalse(self.pipeline._parar)
        self.assertEqual(len(self.pipeline.workers_activos), 0)

    async def test_insercion_y_extraccion_fifo(self):
        """Valida que los eventos mantengan estrictamente el orden de llegada FIFO."""
        evento_1 = {"tipo": "precio_actualizado", "id": "evt-001"}
        evento_2 = {"tipo": "stock_critico", "id": "evt-002"}

        # Meter elementos a la cola de forma directa
        self.pipeline.cola_tareas.put_nowait(evento_1)
        self.pipeline.cola_tareas.put_nowait(evento_2)

        # Extraer elementos y validar el orden secuencial FIFO
        primer_salida = await self.pipeline.cola_tareas.get()
        segunda_salida = await self.pipeline.cola_tareas.get()

        self.assertEqual(primer_salida["id"], "evt-001")
        self.assertEqual(segunda_salida["id"], "evt-002")

    async def test_mecanismo_backpressure_cola_llena(self):
        """Verifica que el productor controle el desborde si la cola llega a su limite maximo."""
        # Forzamos que la capacidad maxima de la cola en este test sea de solo 2 elementos
        self.pipeline.cola_tareas = asyncio.Queue(maxsize=2)

        # Llenamos el tope de la cola de forma manual
        self.pipeline.cola_tareas.put_nowait({"id": "1"})
        self.pipeline.cola_tareas.put_nowait({"id": "2"})

        # El tercer intento de insercion no bloqueante debe lanzar QueueFull obligatoriamente
        with self.assertRaises(asyncio.QueueFull):
            self.pipeline.cola_tareas.put_nowait({"id": "3"})

    @patch("asyncio.sleep", return_value=None)
    async def test_worker_procesa_y_notifica_task_done(self, mock_sleep):
        """Valida que el Worker extraiga la tarea de forma correcta y mande el task_done."""
        evento_prueba = {
            "tipo": "pedido_nuevo",
            "timestamp": time.time(),
            "datos": {}
        }
        
        # Insertamos la tarea de prueba en la cola
        self.pipeline.cola_tareas.put_nowait(evento_prueba)
        self.assertEqual(self.pipeline.cola_tareas.qsize(), 1)

        # Ejecutamos un ciclo controlado del Worker de forma aislada
        # Levantamos la tarea del Worker en el fondo
        tarea_worker = asyncio.create_task(self.pipeline.trabajador_worker(worker_id=99))
        
        # Esperamos a que la cola se vacie (join() se desbloquea cuando todas las tareas marcan task_done)
        await self.pipeline.cola_tareas.join()
        
        # Verificaciones de exito
        self.assertEqual(self.pipeline.cola_tareas.qsize(), 0)
        
        # Limpieza de la tarea en segundo plano
        tarea_worker.cancel()
        try:
            await tarea_worker
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    unittest.main()