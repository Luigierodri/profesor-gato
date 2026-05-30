"""
sound_generator.py — Efectos de sonido contextuales
Proyecto: Profesor Gato

Estrategia con fallbacks:
  1. Freesound.org API — descarga efecto real por keyword
  2. ElevenLabs Sound Generation — genera con IA (requiere plan Creator+)
  3. yt-dlp — busca en SoundCloud
  4. assets/sfx/ — efectos locales elegidos por keywords del tema
"""

import os
import re
import requests
import logging
import subprocess
import shutil
from pathlib import Path
from config import ELEVENLABS_API_KEY

log = logging.getLogger("sound_generator")

ELEVENLABS_URL  = "https://api.elevenlabs.io/v1/sound-generation"
FREESOUND_URL   = "https://freesound.org/apiv2"
MAX_DURATION    = 22.0

# Mapa de keywords → archivo SFX local (fallback final)
_SFX_KEYWORDS = {
    "battle":    "battle_swords.mp3",
    "guerra":    "battle_swords.mp3",
    "roman":     "battle_swords.mp3",
    "revolution": "crowd_cheering.mp3",
    "crowd":     "crowd_cheering.mp3",
    "multitud":  "crowd_cheering.mp3",
    "protest":   "crowd_cheering.mp3",
    "explosi":   "explosion.mp3",
    "bomb":      "explosion.mp3",
    "money":     "coins.mp3",
    "coin":      "coins.mp3",
    "dinero":    "coins.mp3",
    "economia":  "coins.mp3",
    "clock":     "clock_ticking.mp3",
    "time":      "clock_ticking.mp3",
    "tiempo":    "clock_ticking.mp3",
    "thunder":   "thunder.mp3",
    "storm":     "thunder.mp3",
    "tormenta":  "thunder.mp3",
    "space":     "space_ambient.mp3",
    "espacio":   "space_ambient.mp3",
    "science":   "lab_bubbles.mp3",
    "laborator": "lab_bubbles.mp3",
}

SFX_DIR = Path(__file__).parent.parent / "assets" / "sfx"


# ─── MÉTODO 1: Freesound ──────────────────────────────────────────────────────

def _via_freesound(descripcion: str, ruta_salida: Path) -> bool:
    api_key = os.getenv("FREESOUND_API_KEY", "")
    if not api_key:
        return False
    try:
        # Buscar por texto
        r = requests.get(f"{FREESOUND_URL}/search/text/", params={
            "query": descripcion[:100],
            "token": api_key,
            "fields": "id,name,previews,duration",
            "filter": "duration:[5 TO 60]",
            "sort": "score",
            "page_size": 3,
        }, timeout=15)
        results = r.json().get("results", [])
        if not results:
            return False

        sound = results[0]
        preview_url = sound["previews"].get("preview-hq-mp3") or sound["previews"].get("preview-lq-mp3")
        if not preview_url:
            return False

        log.info(f"  [Freesound] Descargando: {sound['name'][:60]}")
        r2 = requests.get(preview_url, headers={"Authorization": f"Token {api_key}"}, timeout=30)
        if r2.status_code == 200:
            ruta_salida.write_bytes(r2.content)
            log.info(f"  [Freesound] OK ({ruta_salida.stat().st_size // 1024} KB)")
            return True
    except Exception as e:
        log.warning(f"  [Freesound] Error: {e}")
    return False


# ─── MÉTODO 2: ElevenLabs ─────────────────────────────────────────────────────

def _via_elevenlabs(descripcion: str, duracion_clip: float, ruta_salida: Path) -> bool:
    try:
        r = requests.post(ELEVENLABS_URL, json={
            "text": descripcion,
            "duration_seconds": duracion_clip,
            "prompt_influence": 0.4,
        }, headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }, timeout=60)
        if r.status_code == 200:
            ruta_salida.write_bytes(r.content)
            log.info(f"  [ElevenLabs] OK ({ruta_salida.stat().st_size // 1024} KB)")
            return True
        log.warning(f"  [ElevenLabs] {r.status_code}: {r.text[:80]}")
    except Exception as e:
        log.warning(f"  [ElevenLabs] Error: {e}")
    return False


# ─── MÉTODO 3: yt-dlp (SoundCloud) ───────────────────────────────────────────

def _via_ytdlp(descripcion: str, ruta_salida: Path) -> bool:
    if not shutil.which("yt-dlp"):
        return False
    query = f"scsearch1:{descripcion[:80]} sound effect no copyright"
    cmd = [
        "yt-dlp", query,
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "5",
        "--output", str(ruta_salida.with_suffix("")) + ".%(ext)s",
        "--no-playlist", "--quiet", "--no-warnings",
        "--match-filter", "duration < 120",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=90)
        candidatos = list(ruta_salida.parent.glob(ruta_salida.stem + "*.mp3"))
        if candidatos:
            if candidatos[0] != ruta_salida:
                candidatos[0].rename(ruta_salida)
            log.info(f"  [yt-dlp] OK ({ruta_salida.stat().st_size // 1024} KB)")
            return True
    except Exception as e:
        log.warning(f"  [yt-dlp] Error: {e}")
    return False


# ─── MÉTODO 4: SFX local por keyword ─────────────────────────────────────────

def _via_sfx_local(descripcion: str, tema: str, ruta_salida: Path) -> bool:
    if not SFX_DIR.exists():
        return False
    texto = (descripcion + " " + tema).lower()
    for keyword, filename in _SFX_KEYWORDS.items():
        if keyword in texto:
            sfx_file = SFX_DIR / filename
            if sfx_file.exists():
                import shutil as _sh
                _sh.copy(sfx_file, ruta_salida)
                log.info(f"  [SFX local] {filename} (keyword: {keyword})")
                return True
    # Fallback: cualquier SFX disponible
    sfx_files = list(SFX_DIR.glob("*.mp3"))
    if sfx_files:
        import random, shutil as _sh
        elegido = random.choice(sfx_files)
        _sh.copy(elegido, ruta_salida)
        log.info(f"  [SFX local] {elegido.name} (random fallback)")
        return True
    return False


# ─── ORQUESTADOR ─────────────────────────────────────────────────────────────

def generar_ambiente(descripcion: str, duracion_video: float, ruta_salida: Path,
                     tema: str = "") -> Path:
    """
    Genera efecto ambiental contextual. Prueba métodos en orden:
    Freesound → ElevenLabs → yt-dlp → SFX local

    Args:
        descripcion:    Campo ambiente_sonoro del script (en inglés)
        duracion_video: Duración total del video
        ruta_salida:    Dónde guardar el .mp3
        tema:           Tema del video (para keyword matching en SFX local)
    """
    duracion_clip = min(duracion_video, MAX_DURATION)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"  Ambiente: \"{descripcion[:65]}\"")

    if _via_freesound(descripcion, ruta_salida):
        return ruta_salida

    log.info("  Freesound fallo, probando ElevenLabs...")
    if _via_elevenlabs(descripcion, duracion_clip, ruta_salida):
        return ruta_salida

    log.info("  ElevenLabs fallo, probando yt-dlp...")
    if _via_ytdlp(descripcion, ruta_salida):
        return ruta_salida

    log.info("  yt-dlp fallo, usando SFX local...")
    if _via_sfx_local(descripcion, tema, ruta_salida):
        return ruta_salida

    raise RuntimeError("Todos los métodos de generación de ambiente fallaron")
