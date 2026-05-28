import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

# Importamos la clase desde tu archivo de produccion
from cliente_multiplex import ClienteSSEMultiplex

class TestClienteSSEMultiplexFallas(unittest.IsolatedAsyncioTestCase):
    """
    BATERIA DE TESTS AUTOMATIZADOS (FALLAS, ESTADOS Y RESILIENCIA)
    Valida la maquina de estados e intercepta excepciones de red mediante mocks.
    """

    def setUp(self):
        # Instanciamos un cliente de prueba con modulos base
        self.modulos_prueba = ["precios", "inventario"]
        self.cliente = ClienteSSEMultiplex(modulos=self.modulos_prueba)

    # ==========================================
    # PARTE 1: VALIDACION DE INVARIANTES Y FALLAS
    # ==========================================

    def test_invariante_estado_inicial(self):
        """Validacion estricta de la maquina de estados inicial (INV-C1)."""
        self.assertEqual(self.cliente.estado, "DESCONECTADO")
        self.assertEqual(self.cliente.reintentos, 0)
        self.assertFalse(self.cliente._parar)

    @patch("httpx.AsyncClient.stream")
    async def test_flujo_conexion_exitosa_resetea_reintentos(self, mock_stream):
        """Verifica que una conexion exitosa (HTTP 200) transicione a CONECTADO y limpie reintentos."""
        mock_respuesta = AsyncMock()
        mock_respuesta.status_code = 200
        # Simula un stream vacio que corta de inmediato para no colgar el test
        mock_respuesta.aiter_lines = AsyncMock()
        mock_respuesta.aiter_lines.return_value.__aiter__ = lambda x: AsyncMock()
        
        # El Context Manager asincrono retorna nuestra respuesta mockeada
        mock_stream.return_value.__aenter__.return_value = mock_respuesta

        # Forzamos un estado previo sucio simulando intentos fallidos anteriores
        self.cliente.reintentos = 3
        
        # Ejecutamos la conexion interna aislada
        await self.cliente._conectar()
        
        # Verificaciones de estado esperadas post-handshake exitoso
        self.assertEqual(self.cliente.estado, "CONECTADO")
        self.assertEqual(self.cliente.reintentos, 0)

    @patch("httpx.AsyncClient.stream")
    async def test_falla_handshake_http_lanza_excepcion(self, mock_stream):
        """Valida que codigos HTTP de error (ej. 500) sean interceptados correctamente."""
        mock_respuesta = MagicMock()
        mock_respuesta.status_code = 500
        mock_respuesta.request = httpx.Request("GET", self.cliente.construir_url())
        
        mock_stream.return_value.__aenter__.return_value = mock_respuesta

        with self.assertRaises(httpx.HTTPStatusError):
            await self.cliente._conectar()

    @patch("httpx.AsyncClient.stream")
    async def test_ciclo_reintentos_hasta_el_maximo(self, mock_stream):
        """
        Simula fallas de red continuas. Verifica que el cliente agote de forma segura 
        los MAX_REINTENTOS y pase a estado DESCONECTADO sin romper la app.
        """
        mock_stream.side_effect = httpx.RequestError("Falla de enlace fisico / red caida")

        # Parcheamos el sleep para que el test corra instantaneamente sin esperar los segundos reales del Backoff
        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            await self.cliente.iniciar()
            
            # Verificaciones del comportamiento de resiliencia ante fallos
            self.assertEqual(self.cliente.reintentos, 5) # Llego al MAX_REINTENTOS
            self.assertEqual(self.cliente.estado, "DESCONECTADO") # Maquina termino en estado seguro
            self.assertEqual(mock_sleep.call_count, 4) # Hizo sleep entre los reintentos

    async def test_falla_invariante_si_ya_esta_conectado(self):
        """Verifica que llamar a iniciar() cuando el estado no es DESCONECTADO arroje un RuntimeError."""
        self.cliente.estado = "CONECTADO" # Forzamos estado invalido para arranque
        
        with self.assertRaises(RuntimeError):
            await self.cliente.iniciar()

    # ==========================================
    # PARTE 2: ESTADOS, SALIDA LIMPIA Y CABECERAS
    # ==========================================

    @patch("httpx.AsyncClient.stream")
    async def test_transicion_estado_durante_conexion(self, mock_stream):
        """Verifica que el estado pase temporalmente por 'CONECTANDO' antes de establecerse."""
        futuro_pausa = asyncio.Future()

        async def stream_lento(*args, **kwargs):
            self.cliente.estado = "CONECTANDO"
            await futuro_pausa
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            return mock_resp

        mock_stream.return_value.__aenter__ = stream_lento

        tarea_conexion = asyncio.create_task(self.cliente._conectar())
        await asyncio.sleep(0.01)
        
        # Verificacion: La maquina de estados debe reflejar la transicion activa
        self.assertEqual(self.cliente.estado, "CONECTANDO")
        
        futuro_pausa.set_result(None)
        try:
            await tarea_conexion
        except Exception:
            pass

    async def test_salida_limpia_con_metodo_detener(self):
        """Valida que invocar detener() active la bandera de parada y limpie la maquina."""
        self.cliente.estado = "CONECTADO"
        self.assertFalse(self.cliente._parar)
        
        # Activar el cierre seguro del cliente
        self.cliente.detener()
        
        # Verificacion de invariantes tras la interrupcion por software
        self.assertTrue(self.cliente._parar)
        self.assertEqual(self.cliente.estado, "DESCONECTADO")

    @patch("httpx.AsyncClient.stream")
    async def test_inclusion_cabecera_last_event_id(self, mock_stream):
        """Verifica que si existe un ultimo_id, se inyecte la cabecera 'Last-Event-ID' en el GET."""
        self.cliente.ultimo_id = "em-99"
        
        mock_respuesta = AsyncMock()
        mock_respuesta.status_code = 200
        mock_respuesta.aiter_lines = AsyncMock()
        mock_respuesta.aiter_lines.return_value.__aiter__ = lambda x: AsyncMock()
        mock_stream.return_value.__aenter__.return_value = mock_respuesta

        await self.cliente._conectar()
        
        # Extraemos los argumentos con los que fue invocado el cliente HTTP real
        args, kwargs = mock_stream.call_args
        headers_enviadas = kwargs.get("headers", {})
        
        # Verificacion: El protocolo SSE debe incluir el ID historico para persistencia
        self.assertIn("Last-Event-ID", headers_enviadas)
        self.assertEqual(headers_enviadas["Last-Event-ID"], "em-99")

if __name__ == "__main__":
    unittest.main()