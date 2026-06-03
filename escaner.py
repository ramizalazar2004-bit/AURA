import gspread
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from concurrent.futures import ThreadPoolExecutor
from config import enviar_mensaje_telegram, obtener_credenciales_google

# Silenciamos advertencias de Yahoo Finance
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- FUNCIONES MATEMÁTICAS ---
def calcular_wma(serie_precios, longitud):
    pesos = np.arange(1, longitud + 1)
    return serie_precios.rolling(longitud).apply(lambda p: np.dot(p, pesos) / pesos.sum(), raw=True)

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
    cruzo_ayer_a_hoy = (precio_ayer <= ma_ayer) and (precio_hoy > ma_hoy)
    cruzo_intradiario = (apertura_hoy <= ma_hoy) and (precio_hoy > ma_hoy)
    return cruzo_ayer_a_hoy or cruzo_intradiario

# --- FUNCIÓN DE ANÁLISIS POR TICKER ---
def analizar_un_ticker(ticker):
    try:
        datos = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(datos) < 200: 
            return None
            
        if isinstance(datos.columns, pd.MultiIndex): 
            datos.columns = datos.columns.droplevel(1)

        cierre, apertura, volumen = datos['Close'], datos['Open'], datos['Volume']

        # Cálculo de Indicadores
        ema_20 = cierre.ewm(span=20, adjust=False).mean()
        wma_21 = calcular_wma(cierre, 21)
        asl_21 = (ema_20 + wma_21) / 2
        sma_30 = cierre.rolling(30).mean()
        ema_150 = cierre.ewm(span=150, adjust=False).mean()
        ema_200 = cierre.ewm(span=200, adjust=False).mean()

        delta = cierre.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))

        fast_ma = cierre.ewm(span=12, adjust=False).mean()
        slow_ma = cierre.ewm(span=26, adjust=False).mean()
        macd_hist = (((fast_ma - slow_ma) / slow_ma) * 1000) - (((fast_ma - slow_ma) / slow_ma) * 1000).ewm(span=9, adjust=False).mean()
        
        marron, media_konk, azul = calcular_koncorde(datos)

        vol_promedio_20d = volumen.rolling(window=20).mean()
        vol_hoy = volumen.iloc[-1]
        vol_promedio_hoy = vol_promedio_20d.iloc[-1]
        rvol = (vol_hoy / vol_promedio_hoy) if vol_promedio_hoy > 0 else 0

        precio_hoy, precio_ayer = cierre.iloc[-1], cierre.iloc[-2]
        apertura_hoy = apertura.iloc[-1]
        asl_hoy, asl_ayer = asl_21.iloc[-1], asl_21.iloc[-2]
        sma30_hoy, sma30_ayer = sma_30.iloc[-1], sma_30.iloc[-2]
        ema150_hoy, ema150_ayer = ema_150.iloc[-1], ema_150.iloc[-2]
        ema200_hoy, ema200_ayer = ema_200.iloc[-1], ema_200.iloc[-2]

        # --- FILTROS ---
        if azul.iloc[-1] <= 0:
            return None

        if not (45 <= rsi.iloc[-1] <= 65):
            return None

        d150 = ((ema150_hoy - precio_hoy)/precio_hoy)*100 if precio_hoy < ema150_hoy else 100
        d200 = ((ema200_hoy - precio_hoy)/precio_hoy)*100 if precio_hoy < ema200_hoy else 100
        if min(d150, d200) <= 3.0:
            return None

        cruce_asl = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, asl_ayer, asl_hoy)
        cruce_sma30 = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, sma30_ayer, sma30_hoy)
        cruce_150 = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, ema150_ayer, ema150_hoy)
        cruce_200 = detecto_cruce(precio_ayer, precio_hoy, apertura_hoy, ema200_ayer, ema200_hoy)

        gatillo_activo = cruce_asl or cruce_sma30 or cruce_150 or cruce_200
        if not gatillo_activo:
            return None

        motivo = "Quiebre ASL21" if cruce_asl else "Quiebre SMA30" if cruce_sma30 else "Breakout EMA Mayor"
        fuerza_convergente = (marron.iloc[-1] > media_konk.iloc[-1]) and (macd_hist.iloc[-1] > macd_hist.tail(4).iloc[0])
        
        if fuerza_convergente:
            if rvol >= 1.5:
                certeza = f"⭐⭐ *ALTA CERTEZA* (Volumen x{rvol:.1f})"
            elif rvol >= 0.8:
                certeza = f"⭐ Certeza Media (Vol. Normal x{rvol:.1f})"
            else:
                certeza = f"⚠️ Baja Certeza (Poco volumen x{rvol:.1f})"

            texto = f"🔥 *{ticker}* | {motivo} 🚀\n"
            texto += f"   ↳ {certeza}\n"
            texto += f"   ↳ Precio: ${precio_hoy:.2f} | RSI: {rsi.iloc[-1]:.1f} | M. Grandes: +{azul.iloc[-1]:.1f}\n\n"
            return texto

    except Exception:
        return None
    return None

# --- MOTOR PRINCIPAL ---
def escanear_mercado():
    print("🔌 Iniciando escáner...")
    credenciales = obtener_credenciales_google()
    cliente = gspread.authorize(credenciales)
    
    try:
        documento = cliente.open("Seguimiento Trades USD ARS - CARTERA Historico")
        hoja_master = documento.worksheet("DATA_MASTER")
        datos_master = hoja_master.get_all_values()
        
        tickers_crudos = []
        for fila in datos_master[2:]:
            if len(fila) >= 10:
                ticker = fila[0].strip().upper()
                categoria = fila[9].strip().upper()
                if ticker and (categoria == "ACCIONES" or categoria == "CEDEARS"):
                    tickers_crudos.append(ticker)
                    
        tickers = list(dict.fromkeys(tickers_crudos))
        
        print(f"📡 Escaneando {len(tickers)} activos en paralelo...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            resultados = list(executor.map(analizar_un_ticker, tickers))
            
        alertas_positivas = [r for r in resultados if r is not None]
        
        # --- ENVÍO DE REPORTES POR TELEGRAM ---
        if not alertas_positivas:
            mensaje_final = "📉 *RADAR BOT ASL*\n\nNingún activo superó los filtros estrictos hoy. Mercado en espera."
            enviar_mensaje_telegram(mensaje_final)
            print("Escaneo finalizado: Enviado reporte sin alertas.")
        else:
            reporte = f"🎯 *ALERTAS PREMIUM FILTRADAS* ({len(alertas_positivas)} Activos)\n\n"
            parte_mensaje = 1
            
            for alerta in alertas_positivas:
                # Telegram soporta hasta 4096, controlamos holgadamente a los 3500 caracteres
                if len(reporte) + len(alerta) > 3500:
                    enviar_mensaje_telegram(reporte)
                    parte_mensaje += 1
                    reporte = f"🎯 *ALERTAS PREMIUM (Parte {parte_mensaje})*\n\n"
                
                reporte += alerta
            
            if len(reporte) > 0 and not reporte.endswith(")*\n\n"):
                enviar_mensaje_telegram(reporte)
                
            print(f"✅ ¡{len(alertas_positivas)} alertas enviadas por Telegram!")

    except Exception as e:
        print(f"❌ Ocurrió un error crítico: {e}")

if __name__ == "__main__":
    escanear_mercado()