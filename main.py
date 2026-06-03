import os
import sys
import time
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytz

from config import validar_config, enviar_mensaje_telegram
from conexion import vigilar_cartera_con_riesgo
from escaner import escanear_mercado

ZONA_BA = pytz.timezone("America/Argentina/Buenos_Aires")

# Lunes a viernes — hora Argentina
HORARIO_CARTERA = (11, 30)
HORARIO_ESCANER = (16, 40)

ultima_ejecucion = {"cartera": None, "escaner": None}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot ASL activo")

    def log_message(self, format, *args):
        pass


def iniciar_servidor_salud():
    port = int(os.getenv("PORT", "8080"))
    servidor = HTTPServer(("0.0.0.0", port), HealthHandler)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    print(f"🌐 Health check en puerto {port}")


def tarea_cartera():
    print(f"[{datetime.now(ZONA_BA)}] 🚀 Ejecutando control de Cartera...")
    vigilar_cartera_con_riesgo()


def tarea_escaner():
    print(f"[{datetime.now(ZONA_BA)}] 🚀 Ejecutando escáner de Mercado...")
    escanear_mercado()


def revisar_horarios():
    ahora = datetime.now(ZONA_BA)
    if ahora.weekday() >= 5:
        return

    fecha_hoy = ahora.date()

    if ahora.hour == HORARIO_CARTERA[0] and ahora.minute == HORARIO_CARTERA[1]:
        if ultima_ejecucion["cartera"] != fecha_hoy:
            ultima_ejecucion["cartera"] = fecha_hoy
            tarea_cartera()

    if ahora.hour == HORARIO_ESCANER[0] and ahora.minute == HORARIO_ESCANER[1]:
        if ultima_ejecucion["escaner"] != fecha_hoy:
            ultima_ejecucion["escaner"] = fecha_hoy
            tarea_escaner()


def main():
    faltan = validar_config()
    if faltan:
        print("❌ Variables de entorno faltantes:", ", ".join(faltan))
        sys.exit(1)

    iniciar_servidor_salud()

    enviar_mensaje_telegram(
        "✅ *Bot ASL en Railway*\n"
        "Programado lun–vie:\n"
        "• Cartera 11:30 (AR)\n"
        "• Escáner 16:40 (AR)"
    )

    print("✅ Bot ASL iniciado. Esperando horarios (hora Argentina)...")
    while True:
        revisar_horarios()
        time.sleep(30)


if __name__ == "__main__":
    main()
