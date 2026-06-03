import gspread
import yfinance as yf
import pandas as pd

from config import enviar_mensaje_telegram, obtener_credenciales_google


def limpiar_precio(texto_precio):
    limpio = str(texto_precio).upper().replace('USD', '').replace('$', '').replace(' ', '').replace(',', '.')
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def evaluar_alertas_cartera():
    """Devuelve líneas solo si hay Stop Loss o Take Profit disparado."""
    print("🔌 Conectando con los servidores de Google (cartera)...")
    credenciales = obtener_credenciales_google()
    cliente = gspread.authorize(credenciales)

    documento = cliente.open("Seguimiento Trades USD ARS - CARTERA Historico")
    hoja_cartera = documento.worksheet("Renta Variable")
    hoja_memoria = documento.worksheet("MemoriaBot")

    datos_memoria = hoja_memoria.get_all_records()
    memoria = {str(fila['Ticker']).strip().upper(): fila for fila in datos_memoria if fila.get('Ticker')}

    datos_crudos = hoja_cartera.get_all_values()
    activos_abiertos = []

    for fila in datos_crudos:
        if len(fila) > 15 and fila[2].strip().upper() == "ABIERTA":
            ticker = fila[5].strip()
            precio_entrada = limpiar_precio(fila[14])
            if ticker and precio_entrada > 0:
                activos_abiertos.append({"ticker": ticker, "entrada": precio_entrada})

    print(f"👁️ Revisando {len(activos_abiertos)} posiciones abiertas (solo SL/TP)...")
    alertas = []

    for activo in activos_abiertos:
        ticker = activo['ticker']
        entrada = activo['entrada']

        datos = yf.download(ticker, period="1d", progress=False)
        if datos.empty or 'Close' not in datos.columns:
            continue

        cierre = datos['Close']
        precio_actual = float(cierre[ticker].iloc[-1]) if isinstance(cierre, pd.DataFrame) else float(cierre.iloc[-1])
        rendimiento = ((precio_actual - entrada) / entrada) * 100
        estado = "🟢" if rendimiento > 0 else "🔴"
        linea_base = f"{estado} *{ticker}* | Comp: ${entrada:.2f} | Act: ${precio_actual:.2f} ({rendimiento:+.2f}%)"

        if ticker not in memoria:
            continue

        sl = limpiar_precio(memoria[ticker]['Stop Loss'])
        tp = limpiar_precio(memoria[ticker]['Take Profit'])

        if sl > 0 and precio_actual <= sl:
            alertas.append(f"{linea_base}\n ↳ 🚨 *VENTA POR STOP LOSS* (Perforó ${sl:.2f})\n")
        elif tp > 0 and precio_actual >= tp:
            alertas.append(f"{linea_base}\n ↳ 💰 *TOMA DE GANANCIAS* (Alcanzó ${tp:.2f})\n")

    return alertas


def enviar_alertas_cartera_si_corresponde():
    try:
        alertas = evaluar_alertas_cartera()
        if not alertas:
            print("📊 Cartera: sin SL/TP — no se envía Telegram.")
            return

        reporte = "📊 *ALERTAS DE CARTERA (SL / TP)*\n\n"
        for texto in alertas:
            if len(reporte) + len(texto) > 3500:
                enviar_mensaje_telegram(reporte)
                reporte = "📊 *ALERTAS DE CARTERA (cont.)*\n\n"
            reporte += texto + "\n"

        if reporte.strip():
            enviar_mensaje_telegram(reporte)
        print(f"✅ Cartera: {len(alertas)} alerta(s) enviada(s).")
    except Exception as e:
        print(f"❌ Error en cartera: {e}")


def vigilar_cartera_con_riesgo():
    enviar_alertas_cartera_si_corresponde()


if __name__ == "__main__":
    vigilar_cartera_con_riesgo()
