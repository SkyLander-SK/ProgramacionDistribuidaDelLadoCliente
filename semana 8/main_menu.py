import asyncio
import logging
import sys

# Importamos el cliente especializado de la actividad anterior
# Asegurate de que el archivo 'cliente_heartbeat.py' este en la misma carpeta
from cliente_heartbeat import ClienteSSEHeartbeat

# Configuracion de logs simplificada y sin acentos
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EcoMarketMenu")

class MenuInteractivoEcoMarket:
    """Maneja el ciclo de vida y la interfaz de usuario por consola para el cliente multiplexado."""
    
    def __init__(self):
        self.cliente = None
        self.tarea_cliente = None

    def mostrar_opciones(self):
        """Despliega el menu visual en la terminal."""
        print("\n=========================================")
        print("    SISTEMA DE MONITOREO ECOMARKET       ")
        print("=========================================")
        print(" 1. Iniciar Cliente Multiplexado (Precios y Stock)")
        print(" 2. Detener Cliente de Forma Limpia")
        print(" 3. Ver Estado Actual de la Conexion")
        print(" 4. Salir del Programa")
        print("=========================================")

    async def ejecutar_opcion(self, opcion: str):
        """Procesa la seleccion del usuario de manera asincrona sin bloquear el hilo."""
        if opcion == "1":
            if self.cliente and self.cliente.estado != "DESCONECTADO":
                print("\n[!] El cliente ya se encuentra operando o conectando.")
                return
                
            print("\n[+] Instanciando cliente para los modulos: 'precios' e 'inventario'...")
            # Creamos el cliente heartbeat nuevo
            self.cliente = ClienteSSEHeartbeat(modulos=["precios", "inventario"])
            
            # Lanzamos el loop de conexion en segundo plano usando create_task
            # Esto evita que el menu se congele mientras el cliente espera datos
            self.tarea_cliente = asyncio.create_task(self.cliente.iniciar())
            print("[+] Cliente corriendo en segundo plano de forma asincrona.")

        elif opcion == "2":
            if self.cliente and self.cliente.estado != "DESCONECTADO":
                print("\n[-] Solicitando detencion controlada del cliente...")
                self.cliente.detener()
                if self.tarea_cliente:
                    # Esperamos a que la tarea termine sus bloques finally de forma limpia
                    await self.tarea_cliente
                print("[-] Sockets cerrados y buffers limpios con exito.")
            else:
                print("\n[!] No hay ningun cliente activo para detener.")

        elif opcion == "3":
            estado_actual = self.cliente.estado if self.cliente else "NO INSTANCIADO"
            reintentos_actuales = self.cliente.reintentos if self.cliente else 0
            print(f"\n[ESTADO] Cliente: {estado_actual} | Reintentos acumulados: {reintentos_actuales}")

        elif opcion == "4":
            if self.cliente:
                self.cliente.detener()
                if self.tarea_cliente:
                    await self.tarea_cliente
            print("\nCerrando el Sistema de Monitoreo EcoMarket. Hasta luego.")
            sys.exit(0)
        else:
            print("\n[!] Opcion invalida. Intente de nuevo.")

    async def bucle_principal(self):
        """Mantiene la escucha activa del teclado por consola."""
        while True:
            self.mostrar_opciones()
            # Ejecutar el input de consola de forma asincrona en un hilo separado 
            # para no congelar las alertas o el watchdog que corren de fondo
            opcion = await asyncio.to_thread(input, "Seleccione una opcion (1-4): ")
            try:
                await self.ejecutar_opcion(opcion.strip())
            except SystemExit:
                break
            except Exception as e:
                logger.error(f"Error procesando el comando: {e}")

if __name__ == "__main__":
    menu = MenuInteractivoEcoMarket()
    try:
        # Arranca el loop de eventos asincrono de asyncio
        asyncio.run(menu.bucle_principal())
    except KeyboardInterrupt:
        # Captura segura del cierre forzado con Ctrl+C sin romper el entorno
        print("\n\n[-] Interrupcion por teclado detectada (Ctrl+C). Limpiando recursos...")
        if menu.cliente:
            menu.cliente.detener()
        print("[-] Salida limpia completada de forma segura.")