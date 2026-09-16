"""
eleven_music.py — Música por IA con ElevenLabs Music (licencia comercial PERMANENTE)
Proyecto: Profesor Gato

A diferencia de Lyria (Google, se genera por-video y cuenta en el presupuesto de
Cloud), lo que generas con ElevenLabs MIENTRAS tu plan está activo conserva los
derechos comerciales PARA SIEMPRE, aunque después bajes de plan. Por eso esto se usa
para armar una "despensa" reutilizable (assets/music/despensa/<mood>/) de una sola
vez — no en cada render.

Endpoint: POST https://api.elevenlabs.io/v1/music  (devuelve audio binario)

OJO CRÉDITOS: la música consume MUCHO del plan ElevenLabs (cuota compartida con la
voz, ver reference-elevenlabs-cuota). Genera la despensa una vez y reutilízala; NO
llames esto por-video o te quedas sin voz a media semana.
"""
import logging
import requests
from pathlib import Path
from config import ELEVENLABS_API_KEY

log = logging.getLogger("eleven_music")

ELEVEN_MUSIC_URL = "https://api.elevenlabs.io/v1/music"
MODEL_ID         = "music_v2"          # v2 = liberado para uso comercial
MIN_MS, MAX_MS   = 3_000, 600_000


def generar_musica_eleven(prompt: str, duracion_seg: float, ruta_salida: Path,
                          force_instrumental: bool = True,
                          output_format: str = "mp3_44100_128") -> Path | None:
    """
    Genera una pista con ElevenLabs Music.

    Args:
        prompt:             Descripción de la música (inglés funciona mejor).
        duracion_seg:       Duración deseada (se clampa a 3–600 s).
        ruta_salida:        Dónde guardar el audio.
        force_instrumental: True garantiza que no traiga voz cantada.
        output_format:      Códec/bitrate ElevenLabs (default mp3 44.1k/128).

    Returns:
        Path al archivo, o None si falla (el llamador decide el fallback).
    """
    if not ELEVENLABS_API_KEY:
        log.warning("  [ElevenMusic] Sin ELEVENLABS_API_KEY — omito")
        return None

    ms = int(max(MIN_MS, min(MAX_MS, round(duracion_seg * 1000))))
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.post(ELEVEN_MUSIC_URL, json={
            "prompt": prompt,
            "music_length_ms": ms,
            "model_id": MODEL_ID,
            "force_instrumental": force_instrumental,
            "output_format": output_format,
        }, headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }, timeout=180)
        if r.status_code == 200 and r.content:
            ruta_salida.write_bytes(r.content)
            log.info(f"  [ElevenMusic] OK — {ruta_salida.name} ({len(r.content)//1024} KB)")
            return ruta_salida
        log.warning(f"  [ElevenMusic] {r.status_code}: {r.text[:160]}")
    except Exception as e:
        log.warning(f"  [ElevenMusic] Error: {e}")
    return None
