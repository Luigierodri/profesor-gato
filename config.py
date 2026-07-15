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
    # PERFIL B (2026-07-05, A/B/C en partida-guardada/_ab_voz, Luigi eligió de oído):
    # más grave y natural, sin "estirar palabras". Unificado en TODOS los pipelines
    # que usan la voz Luigie (shorts+largos de ambos canales). Bastet NO se toca.
    # ANTI-TARTAMUDEO (2026-07-14): PERFIL B había subido similarity 0.85→0.90 y bajado
    # stability 0.55→0.52 → volvió el trabado (Luigi lo oyó en shorts de AMBOS canales).
    # similarity 0.90 fuerza copiar imperfecciones del audio de referencia (repite
    # sílabas). Se regresa a similarity 0.85 (estable, sigue sonando a él) y stability
    # 0.55 (con el que los largos nunca tartamudearon). style 0.25 se conserva. SIN A/B.
    "stability":          0.55,
    "similarity_boost":   0.85,
    "style":              0.25,
    "use_speaker_boost":  True
}

# ─── PRESUPUESTO ELEVENLABS (cuota por ciclo, COMPARTIDA con Partida Guardada) ──
# Misma cuenta/API key que PG. modules/voice_budget lleva un contador local por
# ciclo (archivo compartido en el home) y avisa antes de reventar la cuota. Reset
# el día VOZ_RESET_DIA (aniversario del plan). Ver reference-elevenlabs-cuota.
ELEVENLABS_LIMITE_MENSUAL = 153_204
VOZ_RESET_DIA = 15
VOZ_PRESUPUESTO_HARD_STOP = False

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
