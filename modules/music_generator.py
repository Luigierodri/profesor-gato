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

# Sufijo seguro: fuerza composición ORIGINAL e instrumental. Evita que el
# filtro de "recitation" de Lyria bloquee el prompt por parecerse a una obra real.
_SAFE_SUFFIX = ", original instrumental background score, no vocals, no lyrics"

# Mapa musica_mood → prompt musical en inglés.
# Solo descriptores de instrumentación/mood/tempo. NUNCA nombres de géneros
# ligados a obras reales ni términos como "war music" (los bloquea recitation).
_MOOD_TO_PROMPT = {
    "lofi":                "calm lo-fi instrumental beats, soft piano, gentle mellow rhythm, relaxed study atmosphere",
    "ambient_misterioso":  "mysterious ambient instrumental, subtle tension, ethereal synth pads, suspenseful atmosphere",
    "epico":               "epic cinematic orchestral instrumental, powerful strings and brass, triumphant energetic percussion",
    "dramatico":           "dramatic orchestral instrumental, tense emotional strings, intense cinematic atmosphere",
    "alegre":              "upbeat cheerful instrumental, light positive melody, fun energetic rhythm",
    "melancolico":         "melancholic piano instrumental, bittersweet reflective mood, slow gentle tempo",
    "tension":             "suspenseful instrumental, building tension, thrilling cinematic intensity",
    "aventura":            "adventurous heroic orchestral instrumental, exploratory uplifting theme, energetic",
    "ciencia":             "curious electronic ambient instrumental, modern discovery mood, bright synths",
    "economia":            "modern corporate lo-fi instrumental, calm subtle electronic, light jazzy keys",
}

_DEFAULT_PROMPT = "calm neutral instrumental background music, soft melodic, gentle tempo"

# Prompt de rescate si el filtro de recitation bloquea el prompt contextual.
_SAFE_FALLBACK_PROMPT = "calm neutral instrumental background music, soft melodic piano, gentle ambient pads"


def _mood_to_prompt(musica_mood: str, tema: str) -> str:
    base = _MOOD_TO_PROMPT.get(musica_mood, _DEFAULT_PROMPT)
    # Enriquecer con palabras clave del tema para que la música PEGUE con el contenido.
    # Cada rama es 100% descriptiva (sin "war music" ni géneros ligados a obras reales).
    tema_lower = tema.lower()
    extra = None
    # OJO con el orden: "guerra" se chequea ANTES que "mundial" porque
    # "Guerra Mundial" contiene "mundial" pero NO es deporte.
    if any(w in tema_lower for w in ["guerra", "war", "batalla", "battle", "ww2", "soldado", "ejército"]):
        extra = "intense epic orchestral, powerful dramatic percussion, heroic cinematic atmosphere"
    # Deporte / Mundial de fútbol / olimpiadas → música deportiva épica (NO de guerra).
    elif any(w in tema_lower for w in ["mundial", "fútbol", "futbol", "soccer", "copa", "estadio",
                                       "deporte", "olimp", "gol", "campeonato"]):
        extra = "energetic triumphant orchestral, uplifting and celebratory, bright brass, driving percussion, sports victory mood"
    elif any(w in tema_lower for w in ["roman", "romano", "imperio", "antigua", "antiguo"]):
        extra = "grand ancient orchestral, ceremonial epic, sweeping historical atmosphere"
    elif any(w in tema_lower for w in ["revolución", "revolucion", "revolution", "francesa", "french"]):
        extra = "intense dramatic orchestral, historical tension, stirring strings"
    elif any(w in tema_lower for w in ["economía", "economia", "burbuja", "inflación", "mercado", "financ", "dinero"]):
        extra = "modern corporate lo-fi, calm subtle electronic, light jazzy keys"
    elif any(w in tema_lower for w in ["psicolog", "mente", "cerebro", "experimento", "milgram"]):
        extra = "uneasy psychological ambient, subtle suspense, introspective atmosphere"
    elif any(w in tema_lower for w in ["espacio", "space", "universo", "cosmos", "astrono", "planeta"]):
        extra = "cosmic ambient electronic, spacious atmospheric synths, sense of wonder"

    prompt = f"{extra}, {base}" if extra else base
    return prompt + _SAFE_SUFFIX


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

    # lyria-002 se invoca con :predict (instances/parameters), NO con generateContent.
    # El audio vuelve en predictions[0].bytesBase64Encoded (WAV 48kHz, ~30s).
    def _pedir(texto: str):
        payload = {
            "instances": [{"prompt": texto}],
            "parameters": {"sample_count": 1},
        }
        return requests.post(
            vertex_url(LYRIA_MODEL, "predict"),
            json=payload,
            headers=vertex_headers(),
            timeout=120,
        )

    try:
        resp = _pedir(prompt)

        # El filtro "recitation" de Lyria evalúa el AUDIO generado, no solo el
        # prompt → es probabilístico (el mismo prompt a veces pasa y a veces no).
        # Por eso reintentamos el MISMO prompt contextual una vez (suele pasar);
        # solo si vuelve a bloquear caemos a un prompt neutro garantizado, para
        # que el video tenga música contextual lo más seguido posible.
        if resp.status_code == 400 and "recitation" in resp.text.lower():
            log.warning("  [Lyria] Recitation — reintentando el mismo prompt contextual")
            resp = _pedir(prompt)
        if resp.status_code == 400 and "recitation" in resp.text.lower():
            log.warning("  [Lyria] Recitation de nuevo — usando prompt neutro seguro")
            resp = _pedir(_SAFE_FALLBACK_PROMPT + _SAFE_SUFFIX)

        resp.raise_for_status()
        data = resp.json()

        preds = data.get("predictions", [])
        for pred in preds:
            b64 = pred.get("bytesBase64Encoded") or pred.get("audioContent")
            if b64:
                ruta_salida.write_bytes(base64.b64decode(b64))
                size_kb = ruta_salida.stat().st_size / 1024
                log.info(f"  [Lyria] OK — {ruta_salida.name} ({size_kb:.0f} KB)")
                cost_tracker.registrar_audio(
                    LYRIA_MODEL,
                    duracion_seg=duracion_seg,
                    ctx=f"Mood: {musica_mood}",
                )
                return ruta_salida

        log.warning(f"  [Lyria] Respuesta sin audio. Predictions: {[list(p.keys()) for p in preds]}")
        return None

    except requests.exceptions.HTTPError as e:
        log.warning(f"  [Lyria] HTTP {e.response.status_code}: {e.response.text[:160]}")
        return None
    except Exception as e:
        log.warning(f"  [Lyria] Error: {e} — video continuará sin música")
        return None
