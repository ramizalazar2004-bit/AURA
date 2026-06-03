# Despliegue en Railway (sin depender de tu PC)

## 1. Subir código a GitHub

Asegurate de que `credenciales.json` y `.env` **no** estén en el repo (ya están en `.gitignore`).

```bash
git add .
git commit -m "Configurar bot para Railway"
git push
```

## 2. Crear servicio en Railway

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Elegí tu repositorio `ASL`
3. Railway detecta Python y usa `python main.py` (ver `railway.toml` / `Procfile`)

## 3. Variables de entorno en Railway

En el servicio → **Variables** → agregar:

| Variable | Valor |
|----------|--------|
| `TELEGRAM_TOKEN` | Token de @BotFather |
| `TELEGRAM_CHAT_ID` | Tu chat ID numérico |
| `GOOGLE_CREDENTIALS` | Contenido **completo** de `credenciales.json` en **una sola línea** |

Para `GOOGLE_CREDENTIALS`: abrí `credenciales.json`, copiá todo el JSON y pegalo como valor de la variable (sin saltos de línea extra si Railway lo permite; si falla, minificá el JSON en [jsonformatter.org](https://jsonformatter.org)).

## 4. Horarios automáticos (hora Argentina)

| Tarea | Días | Cuándo |
|-------|------|--------|
| Escaneo de alertas | Lun–Vie | Cada 30 min, 10:00 a 16:30 |
| Resumen alertas + cartera (solo SL/TP) | Lun–Vie | 16:40 |

Comandos por Telegram: `/ayuda`, `/memoria TICKER SL TP`, `/ver TICKER`

## 5. Probar sin esperar al horario

En Railway → **Deployments** → ver logs. Para forzar una prueba local:

```powershell
cd D:\ASL
.\.venv\Scripts\Activate.ps1
$env:GOOGLE_CREDENTIALS = Get-Content credenciales.json -Raw
python conexion.py
```

## 6. Seguridad

Si el token de Telegram quedó alguna vez en el código o en GitHub, revocalo en @BotFather (`/revoke`) y generá uno nuevo.
