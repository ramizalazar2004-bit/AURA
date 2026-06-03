from config import configurar_salida_consola
from cartera import (
    enviar_alertas_cartera_si_corresponde,
    evaluar_alertas_cartera,
    vigilar_cartera_intraday,
)

configurar_salida_consola()


def limpiar_precio(texto_precio):
    from cartera import limpiar_precio as _limpiar

    return _limpiar(texto_precio)


def vigilar_cartera_con_riesgo():
    vigilar_cartera_intraday()


if __name__ == "__main__":
    vigilar_cartera_con_riesgo()
