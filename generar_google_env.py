"""
Uso local: genera valores para pegar en Railway (Variables).

  python generar_google_env.py

No subas la salida a GitHub.
"""
import base64
import json
import os

RUTA = os.getenv("RUTA_GOOGLE", "credenciales.json")


def main():
    with open(RUTA, encoding="utf-8") as f:
        data = json.load(f)

    una_linea = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.b64encode(una_linea.encode("utf-8")).decode("ascii")

    print("=== Opción recomendada en Railway ===")
    print("Nombre: GOOGLE_CREDENTIALS_BASE64")
    print("Valor (copiar todo lo de abajo):\n")
    print(b64)
    print("\n=== Alternativa (si la base64 falla) ===")
    print("Nombre: GOOGLE_CREDENTIALS")
    print("Valor: una sola línea JSON (muy larga):\n")
    print(una_linea[:120] + "... (truncado en pantalla, usá la base64)")


if __name__ == "__main__":
    main()
