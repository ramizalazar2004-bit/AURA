import os
import sys
import time
import threading
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytz

from config import (
    configurar_salida_consola,
    en_railway,
    enviar_mensaje_telegram,
    log,
    permitir_ejecucion_local,
    validar_config,
)
from cartera import (
    enviar_cierre_cartera,
    enviar_seguimiento_operaciones_abiertas,
    vigilar_cartera_intraday,
)
from escaner import ejecutar_escaneo_y_registrar, enviar_resumen_alertas_del_dia
from estado_dia import limpiar_alertas
from telegram_comandos import escuchar_comandos_telegram

configurar_salida_consola()

ZONA_BA = pytz.timezone("America/Argentina/Buenos_Aires")

HORARIO_CIERRE = (16, 40)
HORARIO_SEGUIMIENTO = (10, 30)
HORA_INICIO = 10
HORA_FIN = 16
MINUTOS_EJECUCION = (0, 30)

ultima_ejecucion = {
    "cierre": None,
    "escaneo": None,
    "cartera": None,
    "seguimiento": None,
}


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
    log(f"Health check en puerto {port}")


def _ahora_ba():
    return datetime.now(ZONA_BA)


def _ya_paso(ahora, hora, minuto):
    return (ahora.hour, ahora.minute) > (hora, minuto) or (
        ahora.hour == hora and ahora.minute >= minuto
    )


def _en_horario_mercado(ahora):
    if ahora.hour < HORA_INICIO:
        return False
    if ahora.hour > HORA_FIN:
        return False
    if ahora.hour == HORA_FIN and ahora.minute > HORARIO_CIERRE[1]:
        return False
    return ahora.minute in MINUTOS_EJECUCION


def _slot(ahora):
    return (ahora.date(), ahora.hour, ahora.minute)


def _correr_tarea(nombre, slot, funcion):
    if ultima_ejecucion[nombre] == slot:
        return
    try:
        funcion()
        ultima_ejecucion[nombre] = slot
    except Exception as e:
        log(f"[ERROR] Tarea {nombre}: {e}")
        traceback.print_exc()


def tarea_cierre_del_dia():
    log(f"[{_ahora_ba()}] Cierre del dia (16:40)...")
    try:
        enviar_resumen_alertas_del_dia()
    except Exception as e:
        log(f"[ERROR] Resumen alertas: {e}")
        traceback.print_exc()
    try:
        enviar_cierre_cartera()
    except Exception as e:
        log(f"[ERROR] Cierre cartera: {e}")
        traceback.print_exc()
    limpiar_alertas()


def revisar_horarios():
    ahora = _ahora_ba()
    if ahora.weekday() >= 5:
        return

    fecha_hoy = ahora.date()
    slot_seg = (fecha_hoy, HORARIO_SEGUIMIENTO[0], HORARIO_SEGUIMIENTO[1])

    # 10:30 — con recuperación si el bot arrancó tarde (hasta las 16:40)
    if (
        _ya_paso(ahora, HORARIO_SEGUIMIENTO[0], HORARIO_SEGUIMIENTO[1])
        and (ahora.hour, ahora.minute) <= HORARIO_CIERRE
        and ultima_ejecucion["seguimiento"] != slot_seg
    ):
        _correr_tarea("seguimiento", slot_seg, enviar_seguimiento_operaciones_abiertas)

    en_franja = _en_horario_mercado(ahora) or (
        ahora.hour == HORARIO_CIERRE[0] and ahora.minute == HORARIO_CIERRE[1]
    )
    if en_franja:
        slot = _slot(ahora)
        if _en_horario_mercado(ahora):
            _correr_tarea("escaneo", slot, ejecutar_escaneo_y_registrar)
        _correr_tarea("cartera", slot, vigilar_cartera_intraday)

    if ahora.hour == HORARIO_CIERRE[0] and ahora.minute == HORARIO_CIERRE[1]:
        slot_cierre = (fecha_hoy, HORARIO_CIERRE[0], HORARIO_CIERRE[1])
        if ultima_ejecucion["cierre"] != slot_cierre:
            ultima_ejecucion["cierre"] = slot_cierre
            tarea_cierre_del_dia()


def main():
    if not en_railway() and not permitir_ejecucion_local():
        log(
            "Este bot corre en Railway (24/7). No uses run_bot.bat en Windows.\n"
            "Subi el repo a GitHub y desplegalo en railway.app con las variables de entorno.\n"
            "Solo para prueba local: ALLOW_LOCAL=1 en .env"
        )
        sys.exit(0)

    faltan = validar_config()
    if faltan:
        log("Variables de entorno faltantes: " + ", ".join(faltan))
        sys.exit(1)

    if en_railway():
        log(f"Bot ASL en Railway | hora AR: {_ahora_ba().strftime('%Y-%m-%d %H:%M')}")
    else:
        log("Bot ASL en modo local (ALLOW_LOCAL=1)")

    iniciar_servidor_salud()

    threading.Thread(target=escuchar_comandos_telegram, daemon=True).start()

    enviar_mensaje_telegram(
        "✅ *Bot ASL en Railway*\n\n"
        "Lun–vie (hora Argentina):\n"
        "• Escaneo cada 30 min (10:00–16:30)\n"
        "• Cartera SL/TP cada 30 min (10:00–16:40)\n"
        "• Seguimiento operaciones abiertas *10:30*\n"
        "• Cierre alertas + cartera a las *16:40*\n\n"
        "SL en planilla: precio (`22`) o media (`SMA20`, `EMA9`).\n"
        "Escribí `/ayuda` para comandos."
    )

    log("Bot ASL iniciado (escaneo + cartera + cierre 16:40)...")
    while True:
        revisar_horarios()
        time.sleep(30)


if __name__ == "__main__":
    main()
