import yaml
import inspect
import json
from jsonschema import validate, ValidationError
import importlib

OPENAPI_FILE = "openapi_ecomarket.yaml"
CLIENTE_MODULO = "cliente"
REPORTE_SALIDA = "reporte_conformidad.txt"

REPORTE = []

def log(tipo, mensaje):
    linea = f"{tipo} {mensaje}"
    REPORTE.append(linea)

def cargar_openapi(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def nombre_funcion(metodo, ruta):
    ruta_limpia = ruta.replace("/", "_").replace("{", "").replace("}", "")
    return f"{metodo.lower()}{ruta_limpia}"

def validar_schema(schema, ejemplo):
    try:
        validate(instance=ejemplo, schema=schema)
        return True
    except ValidationError:
        return False

def auditar_contrato():
    spec = cargar_openapi(OPENAPI_FILE)
    paths = spec.get("paths", {})

    try:
        cliente = importlib.import_module(CLIENTE_MODULO)
    except Exception:
        return

    funciones_cliente = {
        name: fn for name, fn in inspect.getmembers(cliente, inspect.isfunction)
    }

    for ruta, operaciones in paths.items():
        for metodo, contenido in operaciones.items():

            fn_name = nombre_funcion(metodo, ruta)

            if fn_name not in funciones_cliente:
                log("❌", f"Falta implementar función '{fn_name}' para {metodo.upper()} {ruta}")
                continue
            else:
                log("✔", f"Función encontrada para {metodo.upper()} {ruta}: {fn_name}")

            fn = funciones_cliente[fn_name]
            sig = inspect.signature(fn)

            parametros = contenido.get("parameters", [])
            for p in parametros:
                if p.get("in") == "header":
                    header_name = p["name"]
                    if header_name not in sig.parameters:
                        log("⚠", f"La función {fn_name} no recibe el header obligatorio '{header_name}'")

            docstring = fn.__doc__ or ""
            for code in contenido.get("responses", {}).keys():
                if code not in docstring:
                    log("⚠", f"La función {fn_name} no documenta el manejo del código {code}")

            for code, response in contenido.get("responses", {}).items():
                contenido_json = response.get("content", {}).get("application/json", {})
                schema = contenido_json.get("schema")
                ejemplo = contenido_json.get("example")

                if schema and ejemplo:
                    ok = validar_schema(schema, ejemplo)
                    if ok:
                        log("✔", f"Schema válido para {fn_name} en código {code}")
                    else:
                        log("⚠", f"El ejemplo del código {code} NO cumple el schema en {fn_name}")

    with open(REPORTE_SALIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORTE))

if __name__ == "__main__":
    auditar_contrato()
