import re
import time

import requests

from config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, enviar_mensaje_telegram
from sheets_util import (
    abrir_trade_renta,
    cerrar_trade_renta,
    guardar_memoria_bot,
    leer_memoria_bot,
)

AYUDA_TEXTO = (
    "📋 *Comandos Bot ASL*\n\n"
    "*Renta Variable* (desde fila 98):\n"
    "Abrir trade:\n"
    "`/abrir TICKER_ARG TICKER_EEUU PRECIO_ARS PRECIO_USD`\n"
    "Ej: `/abrir GGAL GLOB 4500 25.50`\n\n"
    "Cerrar trade:\n"
    "`/cerrar TICKER` (ARG o EEUU)\n"
    "Ej: `/cerrar GLOB`\n\n"
    "*MemoriaBot* (SL / TP):\n"
    "`/memoria TICKER_EEUU SL TP`\n"
    "SL: precio (`22`) o media (`SMA20`, `EMA9`, `MM50`)\n"
    "Ej: `/memoria GLOB SMA20 28`\n\n"
    "Consultar memoria:\n"
    "`/ver GLOB`\n\n"
    "Horarios (lun–vie, AR):\n"
    "• Escaneo cada 30 min (10:00–16:30)\n"
    "• Cartera SL/TP cada 30 min (10:00–16:30)\n"
    "• Seguimiento operaciones *10:30*\n"
    "• Cierre alertas + cartera a las *16:40*"
)


def _es_chat_autorizado(chat_id):
    return str(chat_id) == str(TELEGRAM_CHAT_ID)


def _procesar_texto(texto):
    texto = (texto or "").strip()
    if not texto:
        return

    bajo = texto.lower()
    if bajo in ("/ayuda", "/help", "ayuda", "help", "/start"):
        enviar_mensaje_telegram(AYUDA_TEXTO)
        return

    match = re.match(
        r"^/?memoria\s+([A-Za-z0-9.\-]+)\s+(\S+)\s+([\d.,]+)\s*$",
        texto,
        re.IGNORECASE,
    )
    if match:
        ticker = match.group(1)
        sl = match.group(2).strip().upper()
        tp = float(match.group(3).replace(",", "."))
        try:
            accion, t, sl_v, tp_v = guardar_memoria_bot(ticker, sl, tp)
            enviar_mensaje_telegram(
                f"✅ *MemoriaBot* ({accion})\n"
                f"*{t}*\n"
                f"Stop Loss: `${sl_v}`\n"
                f"Take Profit: `${tp_v}`"
            )
        except Exception as e:
            enviar_mensaje_telegram(f"❌ No pude guardar en la planilla:\n`{e}`")
        return

    match_abrir = re.match(
        r"^/?abrir\s+([A-Za-z0-9.\-]+)\s+([A-Za-z0-9.\-]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
        texto,
        re.IGNORECASE,
    )
    if match_abrir:
        ticker_arg = match_abrir.group(1)
        ticker_eeuu = match_abrir.group(2)
        precio_ars = float(match_abrir.group(3).replace(",", "."))
        precio_usd = float(match_abrir.group(4).replace(",", "."))
        try:
            fila, arg, eeuu, ars, usd = abrir_trade_renta(
                ticker_arg, ticker_eeuu, precio_ars, precio_usd
            )
            enviar_mensaje_telegram(
                f"✅ *Trade ABIERTO* (fila {fila})\n"
                f"ARG: `{arg}` | EEUU: `{eeu}`\n"
                f"ARS: `{ars}` | USD: `{usd}`"
            )
        except Exception as e:
            enviar_mensaje_telegram(f"❌ No pude abrir en Renta Variable:\n`{e}`")
        return

    match_cerrar = re.match(r"^/?cerrar\s+([A-Za-z0-9.\-]+)\s*$", texto, re.IGNORECASE)
    if match_cerrar:
        ticker = match_cerrar.group(1)
        try:
            fila, arg, eeuu = cerrar_trade_renta(ticker)
            enviar_mensaje_telegram(
                f"✅ *Trade CERRADO* (fila {fila})\n"
                f"ARG: `{arg}` | EEUU: `{eeu}`"
            )
        except Exception as e:
            enviar_mensaje_telegram(f"❌ No pude cerrar:\n`{e}`")
        return

    match_ver = re.match(r"^/?ver\s+([A-Za-z0-9.\-]+)\s*$", texto, re.IGNORECASE)
    if match_ver:
        ticker = match_ver.group(1).upper()
        try:
            fila = leer_memoria_bot(ticker)
            if not fila:
                enviar_mensaje_telegram(f"ℹ️ *{ticker}* no está en MemoriaBot.")
                return
            enviar_mensaje_telegram(
                f"📌 *{ticker}*\n"
                f"SL: `{fila.get('Stop Loss', '-')}`\n"
                f"TP: `{fila.get('Take Profit', '-')}`"
            )
        except Exception as e:
            enviar_mensaje_telegram(f"❌ Error al leer planilla:\n`{e}`")
        return

    if texto.startswith("/"):
        enviar_mensaje_telegram(
            "Comando no reconocido. Escribí `/ayuda` para ver el formato."
        )


def escuchar_comandos_telegram():
    requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook",
        timeout=10,
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    offset = None
    print("💬 Escuchando comandos de Telegram...")

    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            respuesta = requests.get(url, params=params, timeout=35)
            datos = respuesta.json()
            if not datos.get("ok"):
                time.sleep(5)
                continue

            for update in datos.get("result", []):
                offset = update["update_id"] + 1
                mensaje = update.get("message") or update.get("edited_message")
                if not mensaje:
                    continue
                chat_id = mensaje["chat"]["id"]
                if not _es_chat_autorizado(chat_id):
                    continue
                texto = mensaje.get("text", "")
                _procesar_texto(texto)
        except Exception as e:
            print(f"⚠️ Error en listener Telegram: {e}")
            time.sleep(5)
