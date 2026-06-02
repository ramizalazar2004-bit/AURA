import yfinance as yf
import pandas as pd
import numpy as np

def calcular_wma(serie_precios, longitud):
    pesos = np.arange(1, longitud + 1)
    return serie_precios.rolling(longitud).apply(lambda precios: np.dot(precios, pesos) / pesos.sum(), raw=True)

def calcular_koncorde(df):
    close, vol, high, low, open_p = df['Close'], df['Volume'], df['High'], df['Low'], df['Open']
    ohlc4 = (open_p + high + low + close) / 4
    tp = (high + low + close) / 3

    roc = close.pct_change()
    vol_diff = vol.diff()
    nvi_change = np.where(vol_diff < 0, roc, 0)
    nvi = (1 + pd.Series(nvi_change, index=df.index).fillna(0)).cumprod() * 1000
    nvim = nvi.ewm(span=15, adjust=False).mean()
    nvimax = nvim.rolling(90).max()
    nvimin = nvim.rolling(90).min()
    azul = (nvi - nvim) * 100 / (nvimax - nvimin)

    rmf = tp * vol
    mf_pos = pd.Series(np.where(tp > tp.shift(1), rmf, 0), index=df.index).rolling(14).sum()
    mf_neg = pd.Series(np.where(tp < tp.shift(1), rmf, 0), index=df.index).rolling(14).sum()
    mfi = 100 - (100 / (1 + (mf_pos / mf_neg)))

    basis = ohlc4.rolling(25).mean()
    dev = 2.0 * ohlc4.rolling(25).std()
    boll_osc = (ohlc4 - basis) / dev * 100

    stoch_k = 100 * (ohlc4 - low.rolling(21).min()) / (high.rolling(21).max() - low.rolling(21).min())
    stoch = stoch_k.rolling(3).mean()

    delta = ohlc4.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    xrsi = 100 - (100 / (1 + (gain / loss)))

    marron = (xrsi + mfi + boll_osc + stoch / 3) / 2
    media = marron.ewm(span=21, adjust=False).mean()

    return marron, media, azul

def detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, ma_ayer, ma_hoy):
    """
    Detecta si hubo un quiebre alcista válido (ya sea por Gap, interdiario o intradiario)
    """
    cruzo_ayer_a_hoy = (precio_ayer <= ma_ayer) and (precio_hoy > ma_hoy)
    cruzo_intradiario = (apertura_hoy <= ma_hoy) and (precio_hoy > ma_hoy)
    return cruzo_ayer_a_hoy or cruzo_intradiario

def analizar_activo(ticker):
    print(f"📡 Analizando {ticker} (Módulo 5: Radares de Quiebre Múltiple)...")
    
    datos = yf.download(ticker, period="1y", interval="1d", progress=False)
    if len(datos) < 200: return
    if isinstance(datos.columns, pd.MultiIndex): datos.columns = datos.columns.droplevel(1)

    cierre = datos['Close']
    apertura = datos['Open']

    # --- MEDIAS MÓVILES ---
    ema_20 = cierre.ewm(span=20, adjust=False).mean()
    wma_21 = calcular_wma(cierre, 21)
    asl_21 = (ema_20 + wma_21) / 2
    sma_30 = cierre.rolling(30).mean() # Sumamos la SMA30
    ema_150 = cierre.ewm(span=150, adjust=False).mean()
    ema_200 = cierre.ewm(span=200, adjust=False).mean()

    # --- OSCILADORES ---
    delta = cierre.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100 - (100 / (1 + (gain / loss)))
    media_rsi = rsi.rolling(14).mean()

    fast_ma = cierre.ewm(span=12, adjust=False).mean()
    slow_ma = cierre.ewm(span=26, adjust=False).mean()
    macd_hist = (((fast_ma - slow_ma) / slow_ma) * 1000) - (((fast_ma - slow_ma) / slow_ma) * 1000).ewm(span=9, adjust=False).mean()
    marron, media_konk, azul = calcular_koncorde(datos)

    # --- EXTRACCIÓN DE DATOS TEMPORALES ---
    precio_hoy = cierre.iloc[-1]
    precio_ayer = cierre.iloc[-2]
    apertura_hoy = apertura.iloc[-1]
    
    asl_hoy, asl_ayer = asl_21.iloc[-1], asl_21.iloc[-2]
    sma30_hoy, sma30_ayer = sma_30.iloc[-1], sma_30.iloc[-2]
    ema150_hoy, ema150_ayer = ema_150.iloc[-1], ema_150.iloc[-2]
    ema200_hoy, ema200_ayer = ema_200.iloc[-1], ema_200.iloc[-2]

    # --- SISTEMA DE DETECCIÓN DE QUIEBRES ---
    cruce_asl = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, asl_ayer, asl_hoy)
    cruce_sma30 = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, sma30_ayer, sma30_hoy)
    cruce_150 = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, ema150_ayer, ema150_hoy)
    cruce_200 = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, ema200_ayer, ema200_hoy)

    # Identificamos el gatillo principal para el mensaje
    gatillo_activo = False
    motivo_quiebre = ""
    
    if cruce_asl:
        gatillo_activo = True
        motivo_quiebre = "Quiebre de ASL21 (Prioridad Alta)"
    elif cruce_sma30:
        gatillo_activo = True
        motivo_quiebre = "Quiebre de SMA30"
    elif cruce_150 or cruce_200:
        gatillo_activo = True
        motivo_quiebre = "Breakout de EMAs Pesadas (150/200)"

    # Estado de Mantenimiento (Si no cruzó nada hoy, pero ya estaba por arriba de todo)
    ya_estaba_arriba = (precio_ayer > asl_ayer) and (precio_hoy > asl_hoy) and not gatillo_activo

    # --- FILTROS DE RIESGO E INDICADORES ---
    margen_valido = min(((ema150_hoy - precio_hoy)/precio_hoy)*100 if precio_hoy < ema150_hoy else 100, 
                        ((ema200_hoy - precio_hoy)/precio_hoy)*100 if precio_hoy < ema200_hoy else 100) > 3.0

    rsi_habilitado = rsi.iloc[-1] < 70
    fuerza_general = (marron.iloc[-1] > media_konk.iloc[-1]) or (rsi.iloc[-1] > media_rsi.iloc[-1]) or (macd_hist.iloc[-1] > macd_hist.tail(4).iloc[0])
    manos_grandes = azul.iloc[-1] > 0

    print(f"\n--- ESTADO DEL PRECIO ---")
    print(f"Precio Actual: ${precio_hoy:.2f}")
    print(f"ASL21: ${asl_hoy:.2f} | SMA30: ${sma30_hoy:.2f}")
    
    # --- VEREDICTO FINAL ---
    print("\n--- RESULTADO DEL SISTEMA ---")
    if not rsi_habilitado:
        print("⛔ CANCELADA: RSI en sobrecompra.")
    elif not margen_valido:
        print("⛔ CANCELADA: Resistencia pesada muy cerca (< 3%).")
    elif gatillo_activo and fuerza_general:
        estado_manos = "🚀 (Manos grandes acompañan)" if manos_grandes else "⚠️ (Sin manos grandes)"
        print(f"✅ ALERTA DE COMPRA CONFIRMADA {estado_manos}")
        print(f"   ↳ Motivo: {motivo_quiebre}")
    elif ya_estaba_arriba and fuerza_general:
        print("🛡️ TRADE ACTIVO / MANTENER: El activo está subiendo fuerte pero la entrada se dio en días anteriores.")
    elif gatillo_activo and not fuerza_general:
        print(f"⚠️ PRECAUCIÓN: {motivo_quiebre}, pero los indicadores no acompañan con fuerza.")
    else:
        print("🔴 ZONA BAJISTA o SIN SEÑAL CLARA.")

# Probalo con distintos activos
analizar_activo("GLOB")