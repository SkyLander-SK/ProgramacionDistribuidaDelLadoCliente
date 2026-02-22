# test_cliente.py
import pytest
import responses
import json
import requests

BASE = "http://ecomarket.test"

class Cliente:
    def listar_productos(self):
        r = requests.get(f"{BASE}/productos")
        r.raise_for_status()
        return r.json()

    def crear_producto(self, d):
        r = requests.post(f"{BASE}/productos", json=d)
        r.raise_for_status()
        return r.json()

    def obtener_producto(self, id):
        r = requests.get(f"{BASE}/productos/%s" % id)
        r.raise_for_status()
        return r.json()

    def actualizar_producto_total(self, id, d):
        r = requests.put(f"{BASE}/productos/%s" % id, json=d)
        r.raise_for_status()
        return r.json()

    def actualizar_producto_parcial(self, id, d):
        r = requests.patch(f"{BASE}/productos/%s" % id, json=d)
        r.raise_for_status()
        return r.json()

    def eliminar_producto(self, id):
        r = requests.delete(f"{BASE}/productos/%s" % id)
        r.raise_for_status()
        return r.status_code

    def obtener_carrito(self):
        r = requests.get(f"{BASE}/carrito")
        r.raise_for_status()
        return r.json()

    def agregar_carrito(self, d):
        r = requests.post(f"{BASE}/carrito", json=d)
        r.raise_for_status()
        return r.json()

    def eliminar_carrito(self):
        r = requests.delete(f"{BASE}/carrito")
        r.raise_for_status()
        return r.status_code

    def eliminar_item_carrito(self, id):
        r = requests.delete(f"{BASE}/carrito/%s" % id)
        r.raise_for_status()
        return r.status_code

client = Cliente()

def add(method,url,status,data=None):
    body = json.dumps(data) if data is not None else ""
    responses.add(method,url,body=body,status=status,content_type="application/json")

@responses.activate
def test_listar_productos_ok():
    add(responses.GET,f"{BASE}/productos",200,[{"id":1}])
    assert client.listar_productos()==[{"id":1}]

@responses.activate
def test_crear_producto_ok():
    p={"nombre":"A","descripcion":"x","precio":1,"categoria":"g","stock":1}
    add(responses.POST,f"{BASE}/productos",201,{"id":1})
    assert client.crear_producto(p)=={"id":1}

@responses.activate
def test_obtener_producto_ok():
    add(responses.GET,f"{BASE}/productos/1",200,{"id":1})
    assert client.obtener_producto(1)=={"id":1}

@responses.activate
def test_actualizar_producto_total_ok():
    add(responses.PUT,f"{BASE}/productos/1",200,{"id":1,"precio":2})
    assert client.actualizar_producto_total(1,{"precio":2})["precio"]==2

@responses.activate
def test_actualizar_producto_parcial_ok():
    add(responses.PATCH,f"{BASE}/productos/1",200,{"id":1,"stock":9})
    assert client.actualizar_producto_parcial(1,{"stock":9})["stock"]==9

@responses.activate
def test_eliminar_producto_ok():
    responses.add(responses.DELETE,f"{BASE}/productos/1",status=204)
    assert client.eliminar_producto(1)==204

@responses.activate
def test_obtener_carrito_ok():
    add(responses.GET,f"{BASE}/carrito",200,[{"productoId":1,"cantidad":2}])
    assert client.obtener_carrito()==[{"productoId":1,"cantidad":2}]

@responses.activate
def test_agregar_carrito_ok():
    add(responses.POST,f"{BASE}/carrito",201,{"ok":True})
    assert client.agregar_carrito({"productoId":1,"cantidad":2})=={"ok":True}

@responses.activate
def test_eliminar_carrito_ok():
    responses.add(responses.DELETE,f"{BASE}/carrito",status=204)
    assert client.eliminar_carrito()==204

@responses.activate
def test_eliminar_item_carrito_ok():
    responses.add(responses.DELETE,f"{BASE}/carrito/1",status=204)
    assert client.eliminar_item_carrito(1)==204
