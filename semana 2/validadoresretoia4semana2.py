
class ValidationError(Exception):
    """Error de validación para datos de productos."""
    pass


CATEGORIAS_VALIDAS = ['frutas', 'verduras', 'lacteos', 'miel', 'conservas']


def _validar_iso8601(fecha: str) -> bool:
    import datetime
    try:
        datetime.datetime.fromisoformat(fecha.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def validar_producto(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("El producto debe ser un diccionario (dict).")

    campos_requeridos = ['id', 'nombre', 'precio', 'categoria']
    for campo in campos_requeridos:
        if campo not in data:
            raise ValidationError(f"Falta el campo requerido: '{campo}'.")

    if not isinstance(data['id'], int):
        raise ValidationError("El campo 'id' debe ser de tipo int.")

    if not isinstance(data['nombre'], str):
        raise ValidationError("El campo 'nombre' debe ser de tipo str.")

    if not isinstance(data['precio'], (int, float)):
        raise ValidationError("El campo 'precio' debe ser numérico (float).")

    if float(data['precio']) <= 0:
        raise ValidationError("El campo 'precio' debe ser mayor que 0.")

    if data['categoria'] not in CATEGORIAS_VALIDAS:
        raise ValidationError(
            f"Categoria inválida '{data['categoria']}'. Debe estar en {CATEGORIAS_VALIDAS}."
        )

    if 'disponible' in data and not isinstance(data['disponible'], bool):
        raise ValidationError("El campo 'disponible' debe ser bool.")

    if 'descripcion' in data and not isinstance(data['descripcion'], str):
        raise ValidationError("El campo 'descripcion' debe ser str.")

    if 'productor' in data:
        productor = data['productor']
        if not isinstance(productor, dict):
            raise ValidationError("El campo 'productor' debe ser un dict.")
        if 'id' not in productor or 'nombre' not in productor:
            raise ValidationError("El campo 'productor' debe tener 'id' y 'nombre'.")
        if not isinstance(productor['id'], int):
            raise ValidationError("El campo 'productor.id' debe ser int.")
        if not isinstance(productor['nombre'], str):
            raise ValidationError("El campo 'productor.nombre' debe ser str.")

    if 'creado_en' in data:
        if not isinstance(data['creado_en'], str) or not _validar_iso8601(data['creado_en']):
            raise ValidationError("El campo 'creado_en' debe ser una fecha ISO 8601 válida.")

    data['precio'] = float(data['precio'])
    return data


def validar_lista_productos(data: list) -> list:
    if not isinstance(data, list):
        raise ValidationError("La respuesta debe ser una lista de productos.")
    return [validar_producto(p) for p in data]
