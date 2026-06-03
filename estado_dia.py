from datetime import datetime

import pytz

ZONA_BA = pytz.timezone("America/Argentina/Buenos_Aires")

_alertas = {}
_fecha = None


def _hoy():
    return datetime.now(ZONA_BA).date()


def registrar_alerta(ticker, texto):
    global _fecha
    hoy = _hoy()
    if _fecha != hoy:
        _alertas.clear()
        _fecha = hoy
    _alertas[ticker.strip().upper()] = texto


def obtener_alertas():
    return list(_alertas.values())


def hay_alertas():
    return len(_alertas) > 0


def limpiar_alertas():
    global _fecha
    _alertas.clear()
    _fecha = None
