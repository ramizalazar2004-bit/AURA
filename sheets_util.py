import gspread

from config import obtener_credenciales_google

NOMBRE_DOCUMENTO = "Seguimiento Trades USD ARS - CARTERA Historico"
HOJA_MEMORIA = "MemoriaBot"
HOJA_RENTA = "Renta Variable"

# Columnas en Renta Variable (1-based, como en Google Sheets)
COL_OPERACION = 3   # C - Operacion (ABIERTA / CERRADA)
COL_TICKER_ARG = 5  # E - TICKER ARG (CEDEAR)
COL_TICKER_EEUU = 6  # F - TICKER EEUU
COL_PRECIO_ARS = 14  # N - precio entrada ARS
COL_PRECIO_USD = 15  # O - precio entrada USD
FILA_INICIO_RENTA = 98


def _cliente():
    return gspread.authorize(obtener_credenciales_google())


def obtener_hoja_memoria():
    return _cliente().open(NOMBRE_DOCUMENTO).worksheet(HOJA_MEMORIA)


def obtener_hoja_renta():
    return _cliente().open(NOMBRE_DOCUMENTO).worksheet(HOJA_RENTA)


def _celda(fila, indice_cero):
    if indice_cero < len(fila):
        return str(fila[indice_cero]).strip()
    return ""


def _fila_esta_libre(fila):
    # Fila disponible si la columna Operación (C) está vacía
    return not _celda(fila, 2)


def _asegurar_capacidad_fila(hoja, num_fila):
    if num_fila > hoja.row_count:
        hoja.add_rows(num_fila - hoja.row_count)


def _primera_fila_libre_renta(hoja):
    valores = hoja.get_all_values()
    limite = hoja.row_count

    for num_fila in range(FILA_INICIO_RENTA, limite + 1):
        fila = valores[num_fila - 1] if num_fila <= len(valores) else []
        if _fila_esta_libre(fila):
            return num_fila

    # Filas 98–N llenas: ampliar la hoja y usar la siguiente fila
    num_fila = max(limite, len(valores), FILA_INICIO_RENTA - 1) + 1
    _asegurar_capacidad_fila(hoja, num_fila)
    return num_fila


def abrir_trade_renta(ticker_arg, ticker_eeuu, precio_ars, precio_usd):
    ticker_arg = ticker_arg.strip().upper()
    ticker_eeuu = ticker_eeuu.strip().upper()
    hoja = obtener_hoja_renta()
    num_fila = _primera_fila_libre_renta(hoja)
    _asegurar_capacidad_fila(hoja, num_fila)

    hoja.update_cell(num_fila, COL_OPERACION, "ABIERTA")
    hoja.update_cell(num_fila, COL_TICKER_ARG, ticker_arg)
    hoja.update_cell(num_fila, COL_TICKER_EEUU, ticker_eeuu)
    hoja.update_cell(num_fila, COL_PRECIO_ARS, precio_ars)
    hoja.update_cell(num_fila, COL_PRECIO_USD, precio_usd)

    return num_fila, ticker_arg, ticker_eeuu, precio_ars, precio_usd


def cerrar_trade_renta(ticker):
    ticker = ticker.strip().upper()
    hoja = obtener_hoja_renta()
    valores = hoja.get_all_values()

    for num_fila in range(FILA_INICIO_RENTA, len(valores) + 1):
        fila = valores[num_fila - 1]
        if _celda(fila, 2).upper() != "ABIERTA":
            continue
        arg = _celda(fila, 4).upper()
        eeuu = _celda(fila, 5).upper()
        if ticker in (arg, eeuu):
            hoja.update_cell(num_fila, COL_OPERACION, "CERRADA")
            return num_fila, arg, eeuu

    raise ValueError(f"No hay operación ABIERTA para {ticker} desde la fila {FILA_INICIO_RENTA}")


def _indice_columna(encabezados, nombres_posibles):
    normalizados = {h.strip().lower(): i for i, h in enumerate(encabezados)}
    for nombre in nombres_posibles:
        if nombre.lower() in normalizados:
            return normalizados[nombre.lower()]
    return None


def guardar_memoria_bot(ticker, stop_loss, take_profit):
    ticker = ticker.strip().upper()
    stop_loss = str(stop_loss).strip()
    take_profit = str(take_profit).strip()
    hoja = obtener_hoja_memoria()
    filas = hoja.get_all_values()

    if not filas:
        hoja.append_row(["Ticker", "Stop Loss", "Take Profit"])
        filas = hoja.get_all_values()

    encabezados = filas[0]
    col_ticker = _indice_columna(encabezados, ["ticker", "symbol"])
    col_sl = _indice_columna(encabezados, ["stop loss", "stop_loss", "sl"])
    col_tp = _indice_columna(encabezados, ["take profit", "take_profit", "tp"])

    if col_ticker is None:
        col_ticker = 0
    if col_sl is None:
        col_sl = 1
    if col_tp is None:
        col_tp = 2

    for num_fila, fila in enumerate(filas[1:], start=2):
        if len(fila) > col_ticker and fila[col_ticker].strip().upper() == ticker:
            hoja.update_cell(num_fila, col_sl + 1, stop_loss)
            hoja.update_cell(num_fila, col_tp + 1, take_profit)
            return "actualizado", ticker, stop_loss, take_profit

    nueva = [""] * len(encabezados)
    nueva[col_ticker] = ticker
    nueva[col_sl] = stop_loss
    nueva[col_tp] = take_profit
    hoja.append_row(nueva)
    return "agregado", ticker, stop_loss, take_profit


def leer_memoria_bot(ticker):
    ticker = ticker.strip().upper()
    hoja = obtener_hoja_memoria()
    for fila in hoja.get_all_records():
        if str(fila.get("Ticker", "")).strip().upper() == ticker:
            return fila
    return None
