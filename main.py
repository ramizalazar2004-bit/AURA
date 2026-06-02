import schedule
import time
import pytz
from datetime import datetime

# Importamos las funciones principales de tus otros archivos
from conexion import vigilar_cartera_con_riesgo
from escaner import escanear_mercado

def tarea_cartera():
    print(f"[{datetime.now()}] 🚀 Ejecutando control de Cartera...")
    vigilar_cartera_con_riesgo()

def tarea_escaner():
    print(f"[{datetime.now()}] 🚀 Ejecutando escáner de Mercado...")
    escanear_mercado()

# Configuramos la zona horaria de Buenos Aires para que el bot no se confunda con la hora del servidor de Railway
zona_ba = pytz.timezone('America/Argentina/Buenos_Aires')

# Programamos los horarios de Lunes a Viernes
schedule.every().monday.at("11:30", zona_ba).do(tarea_cartera)
schedule.every().tuesday.at("11:30", zona_ba).do(tarea_cartera)
schedule.every().wednesday.at("11:30", zona_ba).do(tarea_cartera)
schedule.every().thursday.at("11:30", zona_ba).do(tarea_cartera)
schedule.every().friday.at("11:30", zona_ba).do(tarea_cartera)

schedule.every().monday.at("16:40", zona_ba).do(tarea_escaner)
schedule.every().tuesday.at("16:40", zona_ba).do(tarea_escaner)
schedule.every().wednesday.at("16:40", zona_ba).do(tarea_escaner)
schedule.every().thursday.at("16:40", zona_ba).do(tarea_escaner)
schedule.every().friday.at("16:40", zona_ba).do(tarea_escaner)

print("✅ Bot ASL iniciado en Railway. Esperando los horarios programados...")

# El bucle infinito que mantiene al bot vivo 24/7 en la nube
while True:
    schedule.run_pending()
    time.sleep(60) # Revisa la hora cada 60 segundos para no saturar el servidor