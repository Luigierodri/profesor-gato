"""
music_generator.py — Música contextual con Lyria 3
Proyecto: Profesor Gato

Genera una pista musical única por video usando Lyria 3 (Google AI).
Fallback: tracks estáticos en assets/music/ si Lyria falla.

Modelo: lyria-002 (Vertex AI)
"""

import os
import base64
import logging
import time
import requests
from pathlib import Path
from datetime import datetime
from modules.gcp_client import vertex_url, vertex_headers
from modules import cost_tracker

log = logging.getLogger("music_generator")

BASE_DIR    = Path(__file__).parent.parent
MUSIC_DIR   = BASE_DIR / "assets" / "music" / "generated"
LYRIA_MODEL = "lyria-002"

# Mapa musica_mood → prompt musical en inglés
_MOOD_TO_PROMPT = {
    "lofi":                "calm lo-fi hip hop beats, study music, soft piano, gentle rhythm, educational vibe",
    "ambient_misterioso":  "mysterious ambient music, subtle tension, ethereal pads, psychological suspense",
    "epico":               "epic orchestral music, cinematic, dramatic strings, powerful percussion",
    "dramatico":           "dramatic classical music, tense strings, historical atmosphere, emotional",
    "alegre":              "upbeat cheerful music, light and positive, educational and fun",
    "melancolico":         "melancholic piano music, bittersweet, reflective, slow tempo",
    "tension":             "building tension music, suspenseful, thriller-like, increasing intensity",
    "aventura":            "adventure music, heroic, exploration theme, orchestral",
    "ciencia":             "electronic ambient music, scientific discovery, curious and modern",
    "economia":            "modern lofi hip hop beats, calm, educational, subtle jazz influences",
}

_DEFAULT_PROMPT = "calm educational background music, neutral mood, subtle lo-fi beats"


def _mood_to_prompt(musica_mood: str, tema: str) -> str:
    base = _MOOD_TO_PROMPT.get(musica_mood, _DEFAULT_PROMPT)
    # Enriquecer con palabras clave del tema para contexto extra
    tema_lower = tema.lower()
    if any(w in tema_lower for w in ["roman", "romano", "imperio"]):
        return f"epic orchestral roman music, {base}, cinematic historical"
    if any(w in tema_lower for w in ["revolución", "revolucion", "revolution", "francesa", "french"]):
        return f"dramatic french classical revolution music, {base}, historical tension"
    if any(w in tema_lower for w in ["guerra", "war", "batalla", "battle", "ww2", "mundial"]):
        return f"dramatic war music, {base}, military drums, epic"
    if any(w in tema_lower for w in ["economía", "economia", "burbuja", "inflación", "mercado", "financ"]):
        return f"modern corporate lofi, {base}, subtle electronic"
    if any(w in tema_lower for w in ["psicolog", "mente", "cerebro", "experimento", "milgram"]):
        return f"psychological thriller ambient, {base}, uneasy atmosphere"
    if any(w in tema_lower for w in ["espacio", "space", "universo", "cosmos", "astrono"]):
        return f"space ambient music, {base}, electronic, cosmic"
    return base


def generar_musica_lyria(
    musica_mood: str,
    tema: str,
    duracion_seg: float,
    ruta_salida: Path = None,
) -> Path | None:
    """
    Genera una pista musical con Lyria 3 (Google AI).

    Args:
        musica_mood:  Campo musica_mood del script (e.g. "lofi", "dramatico")
        tema:         Tema del video para enriquecer el prompt
        duracion_seg: Duración objetivo del video en segundos
        ruta_salida:  Dónde guardar el .wav. Auto-generada si None.

    Returns:
        Path al archivo generado, o None si Lyria falla (pipeline continúa con tracks estáticos).
    """
    if ruta_salida is None:
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        slug = tema.replace(" ", "_").replace("/", "-")[:40]
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_salida = MUSIC_DIR / f"{slug}_{ts}.wav"
    else:
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    prompt = _mood_to_prompt(musica_mood, tema)
    log.info(f"  [Lyria] Mood: {musica_mood} | Prompt: \"{prompt[:70]}...\"")

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
        },
    }

    try:
        resp = requests.post(
            vertex_url(LYRIA_MODEL, "generateContent"),
            json=payload,
            headers=vertex_headers(),
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extraer audio de la respuesta
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                audio_bytes = base64.b64decode(part["inlineData"]["data"])
                ruta_salida.write_bytes(audio_bytes)
                size_kb = ruta_salida.stat().st_size / 1024
                log.info(f"  [Lyria] OK — {ruta_salida.name} ({size_kb:.0f} KB)")
                cost_tracker.registrar_audio(
                    LYRIA_MODEL,
                    duracion_seg=duracion_seg,
                    ctx=f"Mood: {musica_mood}",
                )
                return ruta_salida

        log.warning(f"  [Lyria] Respuesta sin audio. Parts: {[list(p.keys()) for p in parts]}")
        return None

    except requests.exceptions.HTTPError as e:
        log.warning(f"  [Lyria] HTTP {e.response.status_code}: {e.response.text[:120]}")
        return None
    except Exception as e:
        log.warning(f"  [Lyria] Error: {e} — usando tracks estáticos")
        return None
