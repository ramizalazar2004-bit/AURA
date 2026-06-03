# Bot ASL en Railway (producción — sin usar la PC)

El bot **solo debe estar encendido en Railway**. No hace falta `run_bot.bat`, `run_cartera.bat` ni dejar la PC prendida.

## Checklist rápido

1. **GitHub** — código actualizado (`git push`)
2. **Railway** — proyecto conectado al repo → deploy automático
3. **Variables** en Railway → **Variables** del servicio:

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `TELEGRAM_TOKEN` | Sí | Token de @BotFather |
| `TELEGRAM_CHAT_ID` | Sí | Tu chat ID numérico |
| `GOOGLE_CREDENTIALS_BASE64` | Sí | Salida de `python generar_google_env.py` |

4. **Borrar** en Railway la variable `GOOGLE_CREDENTIALS` si la tenías en texto plano (usar solo BASE64).
5. Tras cada deploy, en **Logs** debe aparecer: `Bot ASL en Railway | hora AR: ...`
6. En Telegram llega el mensaje: *Bot ASL en Railway* al reiniciar el servicio.

## Crear / conectar el servicio

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Repositorio **ASL**
3. Railway usa `python main.py` (`railway.toml` / `Procfile`)
4. El puerto lo asigna Railway vía `PORT` (health check en `/`)

## Generar GOOGLE_CREDENTIALS_BASE64 (una vez, en tu PC)

```powershell
cd D:\ASL
.\.venv\Scripts\python.exe generar_google_env.py
```

Copiá el valor al portapapeles y pegalo en Railway → **GOOGLE_CREDENTIALS_BASE64** (sin comillas).

## Horarios automáticos (hora Argentina, lun–vie)

| Tarea | Cuándo |
|-------|--------|
| Escaneo de alertas | Cada 30 min, 10:00–16:30 |
| Cartera SL/TP (Telegram si dispara) | Cada 30 min, 10:00–16:40 |
| Seguimiento operaciones abiertas | 10:30 (se recupera si el deploy fue tarde) |
| Cierre alertas + cartera | 16:40 |

**MemoriaBot — Stop Loss:** precio (`22.5`) o media (`SMA20`, `EMA9`). **Take Profit:** precio.

Comandos Telegram: `/ayuda`, `/abrir`, `/cerrar`, `/memoria`, `/ver`

## Ver que funciona

1. Railway → tu servicio → **Deployments** → último deploy **Success**
2. **Logs** en vivo: sin `Variables de entorno faltantes` ni `Error Telegram 404`
3. Abrí en el navegador la URL pública del servicio → debe decer `Bot ASL activo`
4. Escribí `/ayuda` al bot en Telegram

## Si no llegan mensajes

| Síntoma en Logs | Qué hacer |
|-----------------|-----------|
| `Variables de entorno faltantes` | Completar las 3 variables en Railway y **Redeploy** |
| `Error Telegram 404` | Token mal copiado; regenerar en @BotFather y actualizar `TELEGRAM_TOKEN` |
| `MalformedFraming` / PEM | Usar solo `GOOGLE_CREDENTIALS_BASE64`, borrar `GOOGLE_CREDENTIALS` |
| Servicio se apaga | Plan Railway activo; revisar que el deploy no crashee al inicio |

## Subir cambios del código

```bash
git add .
git commit -m "Actualizar bot para Railway"
git push
```

Railway redeploya solo. No necesitás correr nada en Windows.

## Prueba local (opcional, no producción)

Solo si querés depurar en la PC:

```powershell
# .env con ALLOW_LOCAL=1, TELEGRAM_*, credenciales.json o GOOGLE_*
.\.venv\Scripts\python.exe main.py
```

En producción **no uses** esto: dejá solo Railway encendido.

## Seguridad

Si el token de Telegram estuvo en GitHub, revocalo en @BotFather (`/revoke`) y poné el nuevo en Railway.
