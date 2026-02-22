import requests

BASE_URL = "http://localhost:3000/api"

class EcoMarketError(Exception):
    pass

class RecursoNoEncontrado(EcoMarketError):
    pass

class ConflictoRecurso(EcoMarketError):
    pass

def listar_productos() -> list:
    url = f"{BASE_URL}/productos"
    response = requests.get(url)
    if response.status_code != 200:
        raise EcoMarketError("Error al listar productos")
    return response.json()

def obtener_producto(producto_id: int) -> dict:
    url = f"{BASE_URL}/productos/{producto_id}"
    response = requests.get(url)
    if response.status_code == 404:
        raise RecursoNoEncontrado("Producto no encontrado")
    if response.status_code != 200:
        raise EcoMarketError("Error al obtener producto")
    return response.json()

def crear_producto(datos: dict) -> dict:
    url = f"{BASE_URL}/productos"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=datos, headers=headers)
    if response.status_code == 409:
        raise ConflictoRecurso("Producto duplicado")
    if response.status_code != 201:
        raise EcoMarketError("Error al crear producto")
    return response.json()

def actualizar_producto_total(producto_id: int, datos: dict) -> dict:
    url = f"{BASE_URL}/productos/{producto_id}"
    headers = {"Content-Type": "application/json"}
    response = requests.put(url, json=datos, headers=headers)
    if response.status_code == 404:
        raise RecursoNoEncontrado("Producto no encontrado")
    if response.status_code == 409:
        raise ConflictoRecurso("Conflicto al actualizar producto")
    if response.status_code != 200:
        raise EcoMarketError("Error al actualizar producto")
    return response.json()

def actualizar_producto_parcial(producto_id: int, campos: dict) -> dict:
    url = f"{BASE_URL}/productos/{producto_id}"
    headers = {"Content-Type": "application/json"}
    response = requests.patch(url, json=campos, headers=headers)
    if response.status_code == 404:
        raise RecursoNoEncontrado("Producto no encontrado")
    if response.status_code == 409:
        raise ConflictoRecurso("Conflicto al actualizar producto")
    if response.status_code != 200:
        raise EcoMarketError("Error en actualización parcial")
    return response.json()

def eliminar_producto(producto_id: int) -> bool:
    url = f"{BASE_URL}/productos/{producto_id}"
    response = requests.delete(url)
    if response.status_code == 404:
        raise RecursoNoEncontrado("Producto no existe")
    if response.status_code != 204:
        raise EcoMarketError("Error al eliminar producto")
    return True
