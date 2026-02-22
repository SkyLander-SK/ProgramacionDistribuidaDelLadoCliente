# comparacion_validacion.py
# Models based on YAML for Producto and CarritoItem
import time
from typing import Optional
from pydantic import BaseModel
from jsonschema import validate

class Producto(BaseModel):
    id: int
    nombre: str
    descripcion: str
    precio: float
    categoria: str
    stock: int

class CarritoItem(BaseModel):
    productoId: int
    cantidad: int

producto_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "nombre": {"type": "string"},
        "descripcion": {"type": "string"},
        "precio": {"type": "number"},
        "Categoria": {"type": "string"},
        "stock": {"type": "integer"}
    },
    "required": ["id","nombre","descripcion","precio","categoria","stock"]
}

def validar_manual_producto(p):
    if not isinstance(p.get("id"), int): raise ValueError
    if not isinstance(p.get("nombre"), str): raise ValueError
    if not isinstance(p.get("descripcion"), str): raise ValueError
    if not isinstance(p.get("precio"), (int, float)): raise ValueError
    if not isinstance(p.get("categoria"), str): raise ValueError
    if not isinstance(p.get("stock"), int): raise ValueError

def validar_pydantic_producto(p):
    return Producto(**p)

def validar_jsonschema_producto(p):
    validate(instance=p, schema=producto_schema)

sample = {
    "id": 1,
    "nombre": "A",
    "descripcion": "abc",
    "precio": 10.5,
    "categoria": "general",
    "stock": 10
}

def bench(fn, data, n=1000):
    t = time.time()
    for _ in range(n):
        fn(data)
    return time.time() - t

if __name__ == "__main__":
    print("Manual:", bench(validar_manual_producto, sample))
    print("Pydantic:", bench(validar_pydantic_producto, sample))
    print("JSONSchema:", bench(validar_jsonschema_producto, sample))
