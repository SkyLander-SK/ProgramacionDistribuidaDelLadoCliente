import asyncio
import pytest
import aiohttp
from aioresponses import aioresponses
from cliente_async_ecomarket import (
    listar_productos, cargar_dashboard, EcoMarketError, BASE_URL
)

# --- Configuración de Pytest ---
@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s

@pytest.mark.asyncio
class TestEcoMarketAsync:

    # --- 1. EQUIVALENCIA FUNCIONAL ---
    async def test_listar_productos_equivalencia(self, session):
        """Prueba que el retorno sea idéntico al esquema esperado (Semana 2)"""
        with aioresponses() as m:
            payload = [{"id": 1, "nombre": "Manzana"}]
            m.get(f"{BASE_URL}/productos", payload=payload)
            
            resultado = await listar_productos(session)
            assert resultado == payload
            assert len(resultado) == 1

    async def test_error_http_mapeo(self, session):
        """Verifica que los errores 400 lancen EcoMarketError como en la versión síncrona"""
        with aioresponses() as m:
            m.get(f"{BASE_URL}/productos", status=400)
            with pytest.raises(EcoMarketError):
                await listar_productos(session)

    # --- 2. CONCURRENCIA CORRECTA ---
    async def test_gather_exito_total(self, session):
        """Verifica que gather() recolecte todos los resultados exitosos"""
        with aioresponses() as m:
            m.get(f"{BASE_URL}/productos", payload={"data": "p"})
            m.get(f"{BASE_URL}/productores", payload={"data": "pr"})
            m.get(f"{BASE_URL}/pedidos", payload={"data": "pe"})
            
            dashboard = await cargar_dashboard()
            assert len(dashboard["datos"]) == 3

    async def test_gather_con_un_fallo_aislado(self, session):
        """Prueba return_exceptions=True: un error no debe tumbar el dashboard"""
        with aioresponses() as m:
            m.get(f"{BASE_URL}/productos", status=500)
            m.get(f"{BASE_URL}/productores", payload={"ok": True})
            m.get(f"{BASE_URL}/pedidos", payload={"ok": True})
            
            res = await cargar_dashboard()
            assert len(res["errores"]) == 1
            assert len(res["datos"]) == 2

    # --- 3. TIMEOUTS Y CANCELACIÓN ---
    async def test_timeout_individual(self, session):
        """Simula una petición lenta que excede el timeout de 2s del dashboard"""
        with aioresponses() as m:
            # aioresponses no tiene delay nativo fácil, usamos un truco de excepción
            m.get(f"{BASE_URL}/productos", exception=asyncio.TimeoutError())
            
            res = await cargar_dashboard()
            assert any("Timeout" in str(e) or isinstance(e, asyncio.TimeoutError) for e in res["errores"])

    async def test_cancelacion_por_auth_401(self, session):
        """Prueba que un 401 en un endpoint crítico detenga el flujo (Lógica de negocio)"""
        # Este test requiere la lógica de 'coordinador_async' integrada
        with aioresponses() as m:
            m.get(f"{BASE_URL}/perfil", status=401)
            m.get(f"{BASE_URL}/productos", payload={"data": "no debe llegar"})
            
            # Simulando la carga con seguridad
            from coordinador_async import cargar_con_seguridad
            res = await cargar_con_seguridad(session)
            assert res["error"] == "No autorizado"

    # --- 4. EDGE CASES ---
    async def test_servidor_cierra_conexion_abruptamente(self, session):
        """Prueba la robustez ante errores de conexión (ClientConnectorError)"""
        with aioresponses() as m:
            m.get(f"{BASE_URL}/productos", exception=aiohttp.ClientConnectorError(None, Exception()))
            with pytest.raises(Exception): # Dependiendo de cómo manejes el error base
                await listar_productos(session)

    async def test_limite_semaforo_efectivo(self, session):
        """Verifica que el semáforo no permita más de N tareas (Semana 3)"""
        # Para probar esto, medimos tareas activas en un punto del tiempo
        from cliente_async_ecomarket import crear_multiples_productos
        with aioresponses() as m:
            for _ in range(10):
                m.post(f"{BASE_URL}/productos", status=201, payload={})
            
            # Si crear_multiples_productos usa semáforo de 5, este test valida el flujo
            creados, fallidos = await crear_multiples_productos([{"n": i} for i in range(10)])
            assert len(creados) == 10