"""
Genera GOOGLE_CREDENTIALS_BASE64 para Railway.

Uso:
  python generar_google_env.py

Escribe railway_google_base64.txt (no se sube a Git).
"""
import base64
import json
import os
import re
import sys

RUTA = os.getenv("RUTA_GOOGLE", "credenciales.json")
SALIDA = "railway_google_base64.txt"


def main():
    if not os.path.isfile(RUTA):
        print(f"❌ No encontré {RUTA}")
        sys.exit(1)

    with open(RUTA, encoding="utf-8") as f:
        data = json.load(f)

    key = data.get("private_key") or ""
    if "\\n" in key:
        key = key.replace("\\n", "\n")
    key = key.strip().replace("\r\n", "\n")
    if "BEGIN PRIVATE KEY" not in key:
        cuerpo = key.split("-----END PRIVATE KEY-----")[0].strip() if "END PRIVATE KEY" in key else key
        key = f"-----BEGIN PRIVATE KEY-----\n{cuerpo}\n-----END PRIVATE KEY-----\n"
    data["private_key"] = key

    una_linea = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.b64encode(una_linea.encode("utf-8")).decode("ascii")

    # Verificar ida y vuelta
    decodificado = json.loads(base64.b64decode(b64).decode("utf-8"))
    if decodificado.get("client_email") != data.get("client_email"):
        print("❌ Error al verificar base64")
        sys.exit(1)

    ruta_salida = os.path.join(os.path.dirname(__file__) or ".", SALIDA)
    with open(ruta_salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(b64)

    print("OK - Listo.")
    print(f"   Archivo: {os.path.abspath(ruta_salida)}")
    print(f"   Longitud: {len(b64)} caracteres")
    print(f"   Empieza con: {b64[:12]}... (debe ser eyJ0eXBlIjo)")
    print()
    print("En Railway:")
    print("  1. Variable GOOGLE_CREDENTIALS_BASE64")
    print("  2. Abrí el archivo, Ctrl+A, Ctrl+C, pegar en Railway")
    print("  3. Borrá GOOGLE_CREDENTIALS si existe")
    print("  4. Redeploy")


if __name__ == "__main__":
    main()
