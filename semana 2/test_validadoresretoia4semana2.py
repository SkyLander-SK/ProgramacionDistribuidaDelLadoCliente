
import unittest
from validadores import validar_producto, validar_lista_productos, ValidationError


class TestValidadores(unittest.TestCase):

    def test_falta_campo_requerido(self):
        producto = {'id': 1, 'precio': 10.5, 'categoria': 'frutas'}
        with self.assertRaises(ValidationError):
            validar_producto(producto)

    def test_precio_negativo(self):
        producto = {
            'id': 1,
            'nombre': 'Manzana',
            'precio': -5,
            'categoria': 'frutas'
        }
        with self.assertRaises(ValidationError):
            validar_producto(producto)

    def test_categoria_invalida(self):
        producto = {
            'id': 1,
            'nombre': 'Manzana',
            'precio': 10,
            'categoria': 'electronica'
        }
        with self.assertRaises(ValidationError):
            validar_producto(producto)

    def test_tipo_id_incorrecto(self):
        producto = {
            'id': '1',
            'nombre': 'Manzana',
            'precio': 10,
            'categoria': 'frutas'
        }
        with self.assertRaises(ValidationError):
            validar_producto(producto)

    def test_lista_no_es_lista(self):
        with self.assertRaises(ValidationError):
            validar_lista_productos({'id': 1})


if __name__ == '__main__':
    unittest.main()
