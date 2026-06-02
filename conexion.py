import gspread
from google.oauth2.service_account import Credentials
import yfinance as yf
import pandas as pd
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# ⚙️ CONFIGURACIÓN DE TELEGRAM Y GOOGLE
# ==========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RUTA_GOOGLE = os.getenv('RUTA_GOOGLE', 'credenciales.json')
# ==========================================

def limpiar_precio(texto_precio):
    limpio = str(texto_precio).upper().replace('USD', '').replace('$', '').replace(' ', '').replace(',', '.')
    try:
        return float(limpio)
    except ValueError:
        return 0.0

def enviar_mensaje_telegram(texto_mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto_mensaje,
        "parse_mode": "Markdown"
    }
    try:
        respuesta = requests.post(url, json=payload)
        if respuesta.status_code != 200:
            print(f"⚠️ Error al enviar a Telegram: {respuesta.text}")
    except Exception as e:
        print(f"❌ Falló la conexión con la API de Telegram: {e}")

def vigilar_cartera_con_riesgo():
    print("🔌 Conectando con los servidores de Google...")
    alcance = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    credenciales = None
    google_creds_env = os.getenv('GOOGLE_CREDENTIALS')
    
    if google_creds_env:
        # Cargar desde variable de entorno (ideal para Railway / Nube)
        creds_dict = json.loads(google_creds_env)
        credenciales = Credentials.from_service_account_info(creds_dict, scopes=alcance)
    else:
        # Cargar desde archivo local
        credenciales = Credentials.from_service_account_file(RUTA_GOOGLE, scopes=alcance)
        
    cliente = gspread.authorize(credenciales)
    
    try:
        documento = cliente.open("Seguimiento Trades USD ARS - CARTERA Historico")
        hoja_cartera = documento.worksheet("Renta Variable")
        hoja_memoria = documento.worksheet("MemoriaBot")
        
        datos_memoria = hoja_memoria.get_all_records()
        memoria = {str(fila['Ticker']).strip().upper(): fila for fila in datos_memoria if fila['Ticker']}
        
        datos_crudos = hoja_cartera.get_all_values()
        activos_abiertos = []
        
        for fila in datos_crudos:
            if len(fila) > 15 and fila[2].strip().upper() == "ABIERTA":
                ticker = fila[5].strip()
                precio_entrada = limpiar_precio(fila[14])
                if ticker and precio_entrada > 0:
                    activos_abiertos.append({"ticker": ticker, "entrada": precio_entrada})
        
        print(f"👁️ Vigilando {len(activos_abiertos)} activos. Evaluando riesgos y armando reporte...")
        
        reporte = "📊 *REPORTE DE CARTERA - BOT ASL*\n\n"
        parte_mensaje = 1
        
        for activo in activos_abiertos:
            ticker = activo['ticker']
            entrada = activo['entrada']
            
            datos = yf.download(ticker, period="1d", progress=False)
            texto_activo = ""
            
            if not datos.empty and 'Close' in datos.columns:
                cierre = datos['Close']
                precio_actual = float(cierre[ticker].iloc[-1]) if isinstance(cierre, pd.DataFrame) else float(cierre.iloc[-1])
                rendimiento = ((precio_actual - entrada) / entrada) * 100
                estado = "🟢" if rendimiento > 0 else "🔴"
                
                linea_base = f"{estado} *{ticker}* | Comp: ${entrada:.2f} | Act: ${precio_actual:.2f} ({rendimiento:+.2f}%)"
                
                if ticker in memoria:
                    sl = limpiar_precio(memoria[ticker]['Stop Loss'])
                    tp = limpiar_precio(memoria[ticker]['Take Profit'])
                    
                    if sl > 0 and precio_actual <= sl:
                        texto_activo = f"{linea_base}\n ↳ 🚨 *VENTA POR STOP LOSS* (Perforó ${sl:.2f})\n\n"
                    elif tp > 0 and precio_actual >= tp:
                        texto_activo = f"{linea_base}\n ↳ 💰 *TOMA DE GANANCIAS* (Alcanzó ${tp:.2f})\n\n"
                    else:
                        texto_activo = f"{linea_base}\n ↳ 🛡️ Protegido (SL: ${sl:.2f})\n\n"
                else:
                    texto_activo = f"{linea_base}\n ↳ ⚠️ Sin parámetros en memoria.\n\n"
            else:
                texto_activo = f"⚠️ *{ticker}*: Error al leer datos.\n\n"
                
            # Control de caracteres para Telegram (límite holgado de 3500)
            if len(reporte) + len(texto_activo) > 3500:
                enviar_mensaje_telegram(reporte)
                parte_mensaje += 1
                reporte = f"📊 *REPORTE DE CARTERA (Parte {parte_mensaje})*\n\n"
                
            reporte += texto_activo

        # Disparo final
        if len(reporte) > 0 and not reporte.endswith(")*\n\n"):
            enviar_mensaje_telegram(reporte)
            
        print("✅ ¡Escaneo finalizado y reporte enviado a Telegram!")
        
    except Exception as e:
        print(f"❌ Ocurrió un error crítico: {e}")

vigilar_cartera_con_riesgo()