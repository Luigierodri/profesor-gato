import os
from dotenv import load_dotenv

load_dotenv()

# ─── API KEYS ────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")
NEWS_API_KEY        = os.getenv("NEWS_API_KEY")        # https://newsapi.org (gratis)
FREESOUND_API_KEY   = os.getenv("FREESOUND_API_KEY", "")  # https://freesound.org/apiv2/apply

# ─── ELEVENLABS ───────────────────────────────────────────────────────────────
VOICE_ID            = "jVhLuw5HHSDD176mpezF"           # Profesor Gato (Luigie)
BASTET_VOICE_ID     = os.getenv("BASTET_VOICE_ID", "XrExE9yKIg1WjnnlVkGX")  # Matilda preset
ELEVENLABS_MODEL    = "eleven_multilingual_v2"
VOICE_SETTINGS = {
    "stability":          0.45,   # Más variación = más expresivo
    "similarity_boost":   0.85,   # Alta similitud con tu voz original
    "style":              0.35,   # Algo de estilo/emoción
    "use_speaker_boost":  True
}

# ─── ANTHROPIC ────────────────────────────────────────────────────────────────
CLAUDE_MODEL        = "claude-sonnet-4-6"
SCRIPT_MAX_TOKENS   = 2048   # Aumentado para formato diálogo Gato+Bastet

# ─── VIDEO ────────────────────────────────────────────────────────────────────
VIDEO_WIDTH         = 1080
VIDEO_HEIGHT        = 1920   # Vertical 9:16
VIDEO_FPS           = 30
SIEVEDANCE_API_KEY  = os.getenv("SIEVEDANCE_API_KEY", "")   # Agregar cuando tengas acceso

# Objetivo de compresión cuando un guion se pasa de largo (debe quedar < 60s).
# La banda libre real es hasta 59s (ver ajustar_duracion_total): solo se acelera
# si se supera eso, y se comprime a 58s (suave) para no sonar robótico.
MAX_SHORT_DURATION  = 58.0

# ─── COPYRIGHT / MÚSICA ───────────────────────────────────────────────────────
# Los tracks estáticos de assets/music/ se descargaron de SoundCloud buscando
# "no copyright", pero NO están verificados contra Content ID de YouTube
# (ej. "Bella Ciao", grabaciones clásicas) → causaron el bloqueo del Short.
# Por defecto solo se usa música generada por Lyria 3 (original, segura).
# Si Lyria falla, el video va SIN música de fondo (mejor que bloqueado).
ALLOW_STATIC_MUSIC  = os.getenv("ALLOW_STATIC_MUSIC", "false").lower() == "true"

# ─── RUTAS ────────────────────────────────────────────────────────────────────
OUTPUT_DIR          = "output"
LOGS_DIR            = "logs"
ASSETS_DIR          = "assets"

# ─── PUBLICACIÓN ──────────────────────────────────────────────────────────────
TIKTOK_ACCESS_TOKEN     = os.getenv("TIKTOK_ACCESS_TOKEN", "")
YOUTUBE_CREDENTIALS     = os.getenv("YOUTUBE_CREDENTIALS", "")
META_ACCESS_TOKEN       = os.getenv("META_ACCESS_TOKEN", "")

KLING_ACCESS_KEY = os.getenv('KLING_ACCESS_KEY')
KLING_SECRET_KEY = os.getenv('KLING_SECRET_KEY')
