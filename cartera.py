import re

import gspread
import pandas as pd
import yfinance as yf

from config import enviar_mensaje_telegram, log, obtener_credenciales_google
from indicadores import INDICADORES_SL, nivel_indicador
from sheets_util import (
    COL_OPERACION,
    COL_PRECIO_ARS,
    COL_PRECIO_USD,
    COL_TICKER_ARG,
    COL_TICKER_EEUU,
    FILA_INICIO_RENTA,
    celda_renta,
    es_operacion_abierta,
)
from estado_dia import (
    limpiar_alertas_cartera,
    marcar_alerta_cartera_enviada,
    ya_envio_alerta_cartera,
)

NOMBRE_DOCUMENTO = "Seguimiento Trades USD ARS - CARTERA Historico"
HOJA_RENTA = "Renta Variable"
HOJA_MEMORIA = "MemoriaBot"

_RE_MA = re.compile(r"^(SMA|EMA|MM|WMA)\s*(\d+)\s*$", re.IGNORECASE)


def limpiar_precio(texto_precio):
    limpio = (
        str(texto_precio)
        .upper()
        .replace("USD", "")
        .replace("$", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def parsear_take_profit(texto):
    if not texto or not str(texto).strip():
        return None
    valor = limpiar_precio(texto)
    if valor > 0:
        return {"tipo": "precio", "valor": valor, "texto": f"${valor:.2f}"}
    return None


def parsear_stop_loss(texto):
    """Precio fijo o media móvil: SMA20, EMA9, MM50, etc."""
    if not texto or not str(texto).strip():
        return None

    raw = str(texto).strip()
    compacto = raw.upper().replace(" ", "").replace("_", "")

    if compacto in INDICADORES_SL:
        return {"tipo": "indicador", "nombre": compacto, "texto": compacto}

    match = _RE_MA.match(compacto)
    if match:
        tipo = match.group(1).upper()
        if tipo == "MM":
            tipo = "SMA"
        periodos = int(match.group(2))
        return {
            "tipo": tipo,
            "periodos": periodos,
            "texto": f"{tipo}{periodos}",
        }

    valor = limpiar_precio(raw)
    if valor > 0:
        return {"tipo": "precio", "valor": valor, "texto": f"${valor:.2f}"}
    return None


def _precio_serie(datos, ticker):
    if datos.empty:
        return None
    cierre = datos["Close"]
    if isinstance(cierre, pd.DataFrame):
        col = ticker if ticker in cierre.columns else cierre.columns[0]
        return cierre[col]
    return cierre


def precio_actual(ticker):
    datos = yf.download(ticker, period="1d", progress=False)
    serie = _precio_serie(datos, ticker)
    if serie is None or serie.empty:
        return None
    return float(serie.iloc[-1])


def _simbolos_yfinance(ticker_eeuu, ticker_arg):
    """Candidatos para cotización: EEUU primero, luego CEDEAR .BA."""
    vistos = set()
    candidatos = []
    for raw in (ticker_eeuu, ticker_arg):
        if not raw:
            continue
        sym = raw.strip().upper()
        if sym and sym not in vistos:
            vistos.add(sym)
            candidatos.append(sym)
        if sym and "." not in sym:
            ba = f"{sym}.BA"
            if ba not in vistos:
                vistos.add(ba)
                candidatos.append(ba)
    return candidatos


def precio_actual_posicion(pos):
    for simbolo in pos.get("simbolos_yf") or []:
        precio = precio_actual(simbolo)
        if precio is not None:
            return precio, simbolo
    return None, None


def _resolver_entrada(fila, ticker_eeuu, ticker_arg):
    """Precio de entrada: USD (col O) si hay ticker EEUU; si no, ARS (col N)."""
    usd = limpiar_precio(celda_renta(fila, COL_PRECIO_USD))
    ars = limpiar_precio(celda_renta(fila, COL_PRECIO_ARS))
    if ticker_eeuu and usd > 0:
        return usd, "USD"
    if ars > 0:
        return ars, "ARS"
    if usd > 0:
        return usd, "USD"
    return 0.0, None


def calcular_media_movil(ticker, spec_sl):
    periodos = spec_sl["periodos"]
    tipo = spec_sl["tipo"]
    ventana = max(periodos + 5, 60)
    datos = yf.download(ticker, period=f"{ventana}d", progress=False)
    serie = _precio_serie(datos, ticker)
    if serie is None or len(serie) < periodos:
        return None

    if tipo == "EMA":
        ma = serie.ewm(span=periodos, adjust=False).mean()
    else:
        ma = serie.rolling(window=periodos).mean()
    ultimo = ma.iloc[-1]
    if pd.isna(ultimo):
        return None
    return float(ultimo)


def resolver_nivel_sl(spec_sl, ticker):
    if spec_sl is None:
        return None, "sin configurar"
    if spec_sl["tipo"] == "precio":
        return spec_sl["valor"], spec_sl["texto"]
    if spec_sl["tipo"] == "indicador":
        nivel = nivel_indicador(ticker, spec_sl["nombre"])
        if nivel is None:
            return None, f"{spec_sl['texto']} (sin datos)"
        return nivel, f"{spec_sl['texto']} = ${nivel:.2f}"
    ma = calcular_media_movil(ticker, spec_sl)
    if ma is None:
        return None, f"{spec_sl['texto']} (sin datos)"
    return ma, f"{spec_sl['texto']} = ${ma:.2f}"


def _conectar_hojas():
    credenciales = obtener_credenciales_google()
    cliente = gspread.authorize(credenciales)
    documento = cliente.open(NOMBRE_DOCUMENTO)
    return documento.worksheet(HOJA_RENTA), documento.worksheet(HOJA_MEMORIA)


def _cargar_memoria(hoja_memoria):
    memoria = {}
    for fila in hoja_memoria.get_all_records():
        ticker = str(fila.get("Ticker", "")).strip().upper()
        if ticker:
            memoria[ticker] = fila
    return memoria


def _buscar_memoria(memoria, ticker):
    clave = ticker.strip().upper()
    if clave in memoria:
        return memoria[clave]
    return None


def listar_posiciones_abiertas():
    hoja_cartera, hoja_memoria = _conectar_hojas()
    memoria = _cargar_memoria(hoja_memoria)
    datos_crudos = hoja_cartera.get_all_values()
    posiciones = []

    for num_fila, fila in enumerate(datos_crudos, start=1):
        if num_fila < FILA_INICIO_RENTA:
            continue
        if not es_operacion_abierta(celda_renta(fila, COL_OPERACION)):
            continue

        ticker_arg = celda_renta(fila, COL_TICKER_ARG).upper()
        ticker_eeuu = celda_renta(fila, COL_TICKER_EEUU).upper()
        ticker = ticker_eeuu or ticker_arg
        if not ticker:
            continue

        entrada, moneda_entrada = _resolver_entrada(fila, ticker_eeuu, ticker_arg)
        simbolos_yf = _simbolos_yfinance(ticker_eeuu, ticker_arg)
        symbol_yf = simbolos_yf[0] if simbolos_yf else ticker

        fila_mem = _buscar_memoria(memoria, ticker_eeuu) or _buscar_memoria(
            memoria, ticker_arg
        )
        posiciones.append(
            {
                "ticker": ticker,
                "ticker_arg": ticker_arg,
                "ticker_eeuu": ticker_eeuu,
                "symbol_yf": symbol_yf,
                "simbolos_yf": simbolos_yf,
                "entrada": entrada,
                "moneda_entrada": moneda_entrada,
                "fila": num_fila,
                "memoria": fila_mem,
            }
        )
    return posiciones


def _analizar_posicion(pos, precio=None, symbol_cotizacion=None):
    ticker = pos["ticker"]
    entrada = pos["entrada"]
    fila_mem = pos["memoria"]
    symbol_yf = symbol_cotizacion or pos.get("symbol_yf") or ticker

    if precio is not None:
        precio_actual_val = precio
    else:
        precio_actual_val, symbol_yf = precio_actual_posicion(pos)
        if precio_actual_val is None:
            simbolos = ", ".join(pos.get("simbolos_yf") or [ticker])
            return {
                "ticker": ticker,
                "error": f"sin cotizacion ({simbolos})",
                "entrada": entrada,
            }

    if entrada > 0:
        rendimiento = ((precio_actual_val - entrada) / entrada) * 100
        estado = "🟢" if rendimiento > 0 else "🔴"
    else:
        rendimiento = 0.0
        estado = "⚪"

    spec_sl = None
    spec_tp = None
    if fila_mem:
        spec_sl = parsear_stop_loss(fila_mem.get("Stop Loss", ""))
        spec_tp = parsear_take_profit(fila_mem.get("Take Profit", ""))

    nivel_sl, desc_sl = resolver_nivel_sl(spec_sl, symbol_yf)
    nivel_tp = spec_tp["valor"] if spec_tp else None
    desc_tp = spec_tp["texto"] if spec_tp else "sin configurar"

    falta_sl = spec_sl is None
    falta_tp = spec_tp is None

    disparo_sl = False
    disparo_tp = False
    if nivel_sl is not None and precio_actual_val <= nivel_sl:
        disparo_sl = True
    if nivel_tp is not None and precio_actual_val >= nivel_tp:
        disparo_tp = True

    return {
        "ticker": ticker,
        "entrada": entrada,
        "precio": precio_actual_val,
        "rendimiento": rendimiento,
        "estado": estado,
        "spec_sl": spec_sl,
        "spec_tp": spec_tp,
        "nivel_sl": nivel_sl,
        "nivel_tp": nivel_tp,
        "desc_sl": desc_sl,
        "desc_tp": desc_tp,
        "falta_sl": falta_sl,
        "falta_tp": falta_tp,
        "disparo_sl": disparo_sl,
        "disparo_tp": disparo_tp,
    }


def _linea_base(info):
    if info.get("entrada", 0) > 0:
        return (
            f"{info['estado']} *{info['ticker']}* | Comp: ${info['entrada']:.2f} | "
            f"Act: ${info['precio']:.2f} ({info['rendimiento']:+.2f}%)"
        )
    return (
        f"{info['estado']} *{info['ticker']}* | Act: ${info['precio']:.2f} "
        f"(sin precio de entrada en planilla)"
    )


def _enviar_reporte_partido(titulo, lineas):
    if not lineas:
        return
    reporte = f"{titulo}\n\n" if titulo else ""
    for texto in lineas:
        if len(reporte) + len(texto) > 3500:
            enviar_mensaje_telegram(reporte.rstrip())
            reporte = titulo + " (cont.)\n\n"
        reporte += texto + "\n"
    if reporte.strip():
        enviar_mensaje_telegram(reporte.rstrip())


def vigilar_cartera_intraday():
    """Revisa SL/TP en horario de mercado; avisa una vez por disparo y por SL/TP faltante."""
    log("Vigilancia intradia de cartera (SL/TP)...")
    posiciones = listar_posiciones_abiertas()
    if not posiciones:
        log("Cartera: sin posiciones abiertas.")
        return

    alertas = []
    avisos_config = []

    for pos in posiciones:
        info = _analizar_posicion(pos)
        if info.get("error"):
            continue

        ticker = info["ticker"]
        if info["falta_sl"] or info["falta_tp"]:
            partes = []
            if info["falta_sl"]:
                partes.append("Stop Loss")
            if info["falta_tp"]:
                partes.append("Take Profit")
            clave = f"FALTA:{ticker}"
            if not ya_envio_alerta_cartera(clave):
                marcar_alerta_cartera_enviada(clave)
                avisos_config.append(
                    f"⚠️ *{ticker}*: falta asignar {' y '.join(partes)} en MemoriaBot."
                )

        if info["disparo_sl"] and not info["falta_sl"] and not ya_envio_alerta_cartera(ticker, "SL"):
            marcar_alerta_cartera_enviada(ticker, "SL")
            alertas.append(
                f"{_linea_base(info)}\n ↳ 🚨 *STOP LOSS* "
                f"(precio ${info['precio']:.2f} ≤ {info['desc_sl']})\n"
            )
        elif info["disparo_tp"] and not info["falta_tp"] and not ya_envio_alerta_cartera(ticker, "TP"):
            marcar_alerta_cartera_enviada(ticker, "TP")
            alertas.append(
                f"{_linea_base(info)}\n ↳ 💰 *TAKE PROFIT* "
                f"(precio ${info['precio']:.2f} ≥ {info['desc_tp']})\n"
            )

    if avisos_config:
        _enviar_reporte_partido("⚠️ *CARTERA — SL/TP sin asignar*", avisos_config)
    if alertas:
        _enviar_reporte_partido("📊 *ALERTA CARTERA (SL / TP)*", alertas)
        log(f"Cartera intradia: {len(alertas)} alerta(s) enviada(s).")
    elif not avisos_config:
        log("Cartera intradia: sin disparos.")


def enviar_seguimiento_operaciones_abiertas():
    """Resumen de operaciones abiertas (10:30 lun–vie)."""
    log("Seguimiento matutino de operaciones abiertas (10:30)...")
    try:
        posiciones = listar_posiciones_abiertas()
    except Exception as e:
        log(f"[ERROR] No se pudo leer la planilla: {e}")
        enviar_mensaje_telegram(
            f"❌ *SEGUIMIENTO CARTERA (10:30)*\n\nError al leer Google Sheets:\n`{e}`"
        )
        raise
    if not posiciones:
        enviar_mensaje_telegram("📋 *SEGUIMIENTO CARTERA (10:30)*\n\nSin operaciones abiertas.")
        return

    lineas = []
    avisos = []
    for pos in posiciones:
        info = _analizar_posicion(pos)
        if info.get("error"):
            lineas.append(f"⚠️ *{pos['ticker']}*: {info['error']}")
            continue

        linea = (
            f"{_linea_base(info)}\n"
            f" ↳ SL: {info['desc_sl']} | TP: {info['desc_tp']}"
        )
        lineas.append(linea)
        if info["falta_sl"] or info["falta_tp"]:
            partes = []
            if info["falta_sl"]:
                partes.append("Stop Loss")
            if info["falta_tp"]:
                partes.append("Take Profit")
            avisos.append(f"⚠️ *{info['ticker']}*: asignar {' y '.join(partes)}.")

    _enviar_reporte_partido("📋 *SEGUIMIENTO CARTERA (10:30)*", lineas)
    if avisos:
        _enviar_reporte_partido("⚠️ *Configuración pendiente*", avisos)


def enviar_cierre_cartera():
    """Cierre 16:40: solo tickers con SL o TP disparado (no lista toda la cartera)."""
    log("Cierre de cartera (16:40)...")
    posiciones = listar_posiciones_abiertas()
    if not posiciones:
        enviar_mensaje_telegram(
            "📊 *CIERRE CARTERA (16:40)*\n\nSin operaciones abiertas en Renta Variable."
        )
        limpiar_alertas_cartera()
        return

    lineas_disparo = []
    ejecutados_sl = []
    ejecutados_tp = []

    for pos in posiciones:
        info = _analizar_posicion(pos)
        if info.get("error"):
            continue

        if info["disparo_sl"]:
            ejecutados_sl.append(info["ticker"])
            lineas_disparo.append(
                f"{_linea_base(info)}\n ↳ 🚨 *STOP LOSS* — condición cumplida ({info['desc_sl']})\n"
            )
        elif info["disparo_tp"]:
            ejecutados_tp.append(info["ticker"])
            lineas_disparo.append(
                f"{_linea_base(info)}\n ↳ 💰 *TAKE PROFIT* — condición cumplida ({info['desc_tp']})\n"
            )

    resumen = "📊 *CIERRE CARTERA (16:40)*\n\n"
    if ejecutados_sl:
        resumen += f"🚨 *Stop Loss disparado:* {', '.join(ejecutados_sl)}\n"
    else:
        resumen += "✅ *Stop Loss:* ningún disparo al cierre.\n"
    if ejecutados_tp:
        resumen += f"💰 *Take Profit:* {', '.join(ejecutados_tp)}\n"
    else:
        resumen += "✅ *Take Profit:* ningún disparo al cierre.\n"

    if lineas_disparo:
        _enviar_reporte_partido(resumen.strip(), lineas_disparo)
    else:
        enviar_mensaje_telegram(resumen.strip())

    limpiar_alertas_cartera()


# Compatibilidad con conexion.py / run_cartera.bat
def evaluar_alertas_cartera():
    alertas = []
    for pos in listar_posiciones_abiertas():
        info = _analizar_posicion(pos)
        if info.get("error"):
            continue
        if info["disparo_sl"]:
            alertas.append(
                f"{_linea_base(info)}\n ↳ 🚨 *VENTA POR STOP LOSS* ({info['desc_sl']})\n"
            )
        elif info["disparo_tp"]:
            alertas.append(
                f"{_linea_base(info)}\n ↳ 💰 *TOMA DE GANANCIAS* ({info['desc_tp']})\n"
            )
    return alertas


def enviar_alertas_cartera_si_corresponde():
    enviar_cierre_cartera()
