from datetime import datetime

import pytz

ZONA_BA = pytz.timezone("America/Argentina/Buenos_Aires")

_alertas = {}
_fecha = None
_cartera_alertas = {}
_fecha_cartera = None


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


def _asegurar_dia_cartera():
    global _fecha_cartera
    hoy = _hoy()
    if _fecha_cartera != hoy:
        _cartera_alertas.clear()
        _fecha_cartera = hoy


def ya_envio_alerta_cartera(ticker, tipo=None):
    _asegurar_dia_cartera()
    clave = ticker.strip().upper()
    if tipo is None:
        return clave in _cartera_alertas
    return _cartera_alertas.get(clave) == tipo


def marcar_alerta_cartera_enviada(ticker, tipo=None):
    _asegurar_dia_cartera()
    clave = ticker.strip().upper()
    _cartera_alertas[clave] = tipo or "1"


def limpiar_alertas_cartera():
    global _fecha_cartera
    _cartera_alertas.clear()
    _fecha_cartera = None
