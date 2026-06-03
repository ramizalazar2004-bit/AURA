import base64
import json
import os
import re

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
    if not os.getenv("GOOGLE_CREDENTIALS") and not os.getenv("GOOGLE_CREDENTIALS_BASE64"):
        if not os.path.isfile(RUTA_GOOGLE):
            faltan.append("GOOGLE_CREDENTIALS o GOOGLE_CREDENTIALS_BASE64")
    return faltan


def _parsear_json_credenciales(texto):
    texto = texto.strip()
    if not texto:
        raise ValueError("GOOGLE_CREDENTIALS vacío")
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    # A veces Railway o el panel convierten comillas o saltos de línea
    texto = texto.replace("\r\n", "\n").strip()
    if texto.startswith("{") and texto.endswith("}"):
        return json.loads(texto)
    raise ValueError(
        "GOOGLE_CREDENTIALS no es JSON válido. Usá generar_google_env.py o GOOGLE_CREDENTIALS_BASE64."
    )


def _cargar_dict_credenciales():
    raw_b64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    if raw_b64:
        decodificado = base64.b64decode(raw_b64.strip()).decode("utf-8")
        return _parsear_json_credenciales(decodificado)

    raw = os.getenv("GOOGLE_CREDENTIALS")
    if raw:
        return _parsear_json_credenciales(raw)

    with open(RUTA_GOOGLE, encoding="utf-8") as archivo:
        return json.load(archivo)


def _normalizar_private_key(creds_dict):
    key = creds_dict.get("private_key") or ""
    if not key:
        raise ValueError("Falta private_key en las credenciales de Google")

    # Literales \\n pegados en Railway sin convertir
    if "\\n" in key:
        key = key.replace("\\n", "\n")

    key = key.strip().replace("\r\n", "\n")

    if "BEGIN PRIVATE KEY" not in key:
        cuerpo = key
        if "END PRIVATE KEY" in cuerpo:
            cuerpo = re.split(r"-----END PRIVATE KEY-----", cuerpo, maxsplit=1)[0].strip()
        key = f"-----BEGIN PRIVATE KEY-----\n{cuerpo}\n-----END PRIVATE KEY-----\n"

    if "END PRIVATE KEY" not in key:
        key = key.rstrip() + "\n-----END PRIVATE KEY-----\n"

    creds_dict["private_key"] = key
    return creds_dict


def obtener_credenciales_google():
    creds_dict = _normalizar_private_key(_cargar_dict_credenciales())
    return Credentials.from_service_account_info(creds_dict, scopes=ALCANCE_GOOGLE)


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
