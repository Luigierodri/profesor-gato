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
CLAUDE_MODEL        = "claude-haiku-4-5-20251001"
SCRIPT_MAX_TOKENS   = 2048   # Aumentado para formato diálogo Gato+Bastet

# ─── VIDEO ────────────────────────────────────────────────────────────────────
VIDEO_WIDTH         = 1080
VIDEO_HEIGHT        = 1920   # Vertical 9:16
VIDEO_FPS           = 30
SIEVEDANCE_API_KEY  = os.getenv("SIEVEDANCE_API_KEY", "")   # Agregar cuando tengas acceso

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
