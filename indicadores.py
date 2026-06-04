"""Niveles de indicadores ASL (mismas fórmulas que escaner.py / bot.py)."""

import numpy as np
import pandas as pd
import yfinance as yf

INDICADORES_SL = frozenset({"ASL21", "SMA30"})


def calcular_wma(serie_precios, longitud):
    pesos = np.arange(1, longitud + 1)
    return serie_precios.rolling(longitud).apply(
        lambda precios: np.dot(precios, pesos) / pesos.sum(), raw=True
    )


def _serie_cierre(ticker, period="1y"):
    datos = yf.download(ticker, period=period, progress=False)
    if datos.empty:
        return None
    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.droplevel(1)
    cierre = datos["Close"]
    if isinstance(cierre, pd.DataFrame):
        col = ticker if ticker in cierre.columns else cierre.columns[0]
        cierre = cierre[col]
    return cierre


def nivel_indicador(ticker, nombre):
    """
    Devuelve el valor actual del indicador para usar como stop loss.
    ASL21 = (EMA20 + WMA21) / 2
    SMA30 = media simple 30 períodos
    """
    nombre = str(nombre).upper().replace(" ", "").replace("_", "")
    if nombre not in INDICADORES_SL:
        return None

    cierre = _serie_cierre(ticker)
    if cierre is None or len(cierre) < 30:
        return None

    if nombre == "ASL21":
        if len(cierre) < 21:
            return None
        ema_20 = cierre.ewm(span=20, adjust=False).mean()
        wma_21 = calcular_wma(cierre, 21)
        asl_21 = (ema_20 + wma_21) / 2
        ultimo = asl_21.iloc[-1]
    elif nombre == "SMA30":
        sma_30 = cierre.rolling(30).mean()
        ultimo = sma_30.iloc[-1]
    else:
        return None

    if pd.isna(ultimo):
        return None
    return float(ultimo)
