# YouTube Setup — Profesor Gato

Pasos para obtener `credentials.json` y publicar videos en YouTube.

## 1. Crear proyecto en Google Cloud Console

1. Abre [console.cloud.google.com](https://console.cloud.google.com)
2. Crea un proyecto nuevo (o usa el existente con los créditos)
3. En el menú lateral: **APIs & Services → Library**
4. Busca **"YouTube Data API v3"** y haz clic en **Enable**

## 2. Crear credenciales OAuth 2.0

1. Ve a **APIs & Services → Credentials**
2. Haz clic en **+ Create Credentials → OAuth client ID**
3. Si te pide configurar la pantalla de consentimiento:
   - User Type: **External**
   - App name: `Profesor Gato`
   - Scopes: agrega `youtube.upload`
   - Test users: agrega tu email
4. Tipo de aplicación: **Desktop app**
5. Nombre: `profesor-gato-publisher`
6. Haz clic en **Create**
7. Descarga el JSON → renómbralo a `credentials.json`
8. Colócalo en la raíz del proyecto (`~/profesor-gato/credentials.json`)

> **Importante:** `credentials.json` y `token.json` contienen información sensible.
> Están en `.gitignore` y nunca deben subirse a git.

## 3. Instalar dependencias

```bash
pip install google-auth google-auth-oauthlib google-api-python-client
```

O agrega al proyecto:

```bash
pip install -r requirements.txt
```

## 4. Primera ejecución (OAuth)

```bash
python publisher.py --dry-run
```

- Se abrirá el browser para autorizar la app con tu cuenta de YouTube
- Acepta los permisos → se genera `token.json` automáticamente
- Las ejecuciones siguientes no abren el browser

## 5. Publicar el video más reciente

```bash
# Vista previa (sin subir)
python publisher.py --dry-run

# Subir el video más reciente en videos/
python publisher.py

# Subir un video específico
python publisher.py --video videos/20260524_013645_El_Experimento_de_Milgram.mp4
```

## Resultado esperado

```
17:00:01 [INFO] Video más reciente: 20260524_013645_El_Experimento_de_Milgram.mp4
17:00:01 [INFO] ============================================================
17:00:01 [INFO]   YOUTUBE UPLOAD — Profesor Gato
17:00:01 [INFO] ============================================================
17:00:01 [INFO]   Título: El Experimento de Milgram: ¿Por Qué Obedecemos?
17:00:15 [INFO]   Subiendo... 50% (3.2/6.4 MB)
17:00:28 [INFO]   Subiendo... 100% (6.4/6.4 MB)
17:00:29 [INFO] ============================================================
17:00:29 [INFO]   PUBLICADO
17:00:29 [INFO]   Video ID: dQw4w9WgXcQ
17:00:29 [INFO]   URL:      https://youtu.be/dQw4w9WgXcQ
17:00:29 [INFO] ============================================================
17:00:29 [INFO]   cost_tracker.json actualizado con youtube_id: dQw4w9WgXcQ
```

## Integración con el pipeline principal

Para publicar automáticamente después de generar el video:

```bash
python main.py "La Burbuja de los Tulipanes" && python publisher.py
```

## Troubleshooting

| Error | Causa | Solución |
|-------|-------|----------|
| `credentials.json not found` | Falta el archivo | Descárgalo de Cloud Console |
| `access_denied` | App no autorizada | Agrega tu email como test user |
| `quotaExceeded` | Límite diario de YouTube API | Espera 24h (límite = 10,000 unidades/día) |
| `videoNotFound` después de subir | YouTube necesita ~1 min para procesar | Espera y refresca |
