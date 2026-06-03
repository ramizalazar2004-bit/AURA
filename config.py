import json
import os

import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RUTA_GOOGLE = os.getenv("RUTA_GOOGLE", "credenciales.json")

ALCANCE_GOOGLE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def validar_config():
    faltan = []
    if not TELEGRAM_TOKEN:
        faltan.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID:
        faltan.append("TELEGRAM_CHAT_ID")
    if not os.getenv("GOOGLE_CREDENTIALS") and not os.path.isfile(RUTA_GOOGLE):
        faltan.append("GOOGLE_CREDENTIALS (o credenciales.json en local)")
    return faltan


def obtener_credenciales_google():
    google_creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_env:
        creds_dict = json.loads(google_creds_env)
        return Credentials.from_service_account_info(creds_dict, scopes=ALCANCE_GOOGLE)
    return Credentials.from_service_account_file(RUTA_GOOGLE, scopes=ALCANCE_GOOGLE)


def enviar_mensaje_telegram(texto_mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto_mensaje,
        "parse_mode": "Markdown",
    }
    try:
        respuesta = requests.post(url, json=payload, timeout=30)
        if respuesta.status_code != 200:
            print(f"⚠️ Error al enviar a Telegram: {respuesta.text}")
        return respuesta.status_code == 200
    except Exception as e:
        print(f"❌ Falló la conexión con la API de Telegram: {e}")
        return False
