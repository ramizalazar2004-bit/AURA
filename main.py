import os
import sys
import time
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytz

from config import validar_config, enviar_mensaje_telegram
from conexion import enviar_alertas_cartera_si_corresponde
from escaner import ejecutar_escaneo_y_registrar, enviar_resumen_alertas_del_dia
from estado_dia import limpiar_alertas
from telegram_comandos import escuchar_comandos_telegram

ZONA_BA = pytz.timezone("America/Argentina/Buenos_Aires")

HORARIO_CIERRE = (16, 40)
ESCANEO_HORA_INICIO = 10
ESCANEO_HORA_FIN = 16
ESCANEO_MINUTOS = (0, 30)

ultima_ejecucion = {"cierre": None, "escaneo": None}


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


def tarea_cierre_del_dia():
    print(f"[{datetime.now(ZONA_BA)}] 📬 Cierre del día (16:40)...")
    enviar_resumen_alertas_del_dia()
    enviar_alertas_cartera_si_corresponde()
    limpiar_alertas()


def _slot_escaneo(ahora):
    return (ahora.date(), ahora.hour, ahora.minute)


def revisar_horarios():
    ahora = datetime.now(ZONA_BA)
    if ahora.weekday() >= 5:
        return

    fecha_hoy = ahora.date()

    if (
        ESCANEO_HORA_INICIO <= ahora.hour <= ESCANEO_HORA_FIN
        and ahora.minute in ESCANEO_MINUTOS
    ):
        slot = _slot_escaneo(ahora)
        if ultima_ejecucion["escaneo"] != slot:
            ultima_ejecucion["escaneo"] = slot
            ejecutar_escaneo_y_registrar()

    if ahora.hour == HORARIO_CIERRE[0] and ahora.minute == HORARIO_CIERRE[1]:
        if ultima_ejecucion["cierre"] != fecha_hoy:
            ultima_ejecucion["cierre"] = fecha_hoy
            tarea_cierre_del_dia()


def main():
    faltan = validar_config()
    if faltan:
        print("❌ Variables de entorno faltantes:", ", ".join(faltan))
        sys.exit(1)

    iniciar_servidor_salud()

    threading.Thread(target=escuchar_comandos_telegram, daemon=True).start()

    enviar_mensaje_telegram(
        "✅ *Bot ASL en Railway*\n\n"
        "Lun–vie (hora Argentina):\n"
        "• Escaneo cada 30 min (10:00–16:30)\n"
        "• Resumen alertas + cartera SL/TP a las *16:40*\n\n"
        "Escribí `/ayuda` para abrir/cerrar trades y cargar SL/TP."
    )

    print("✅ Bot ASL iniciado (escaneo continuo + cierre 16:40)...")
    while True:
        revisar_horarios()
        time.sleep(30)


if __name__ == "__main__":
    main()
