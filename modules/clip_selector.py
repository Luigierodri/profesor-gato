"""
clip_selector.py — Selecciona el clip de personaje según emoción del panel
Proyecto: Profesor Gato

Devuelve el clip correcto para Gato o Bastet según el número de panel
y el speaker. Los clips se usan como overlay de 2-3 segundos sobre
el fondo real de Wikimedia Commons.
"""

from pathlib import Path

VIDEOS_DIR = Path(__file__).parent.parent / "videos"

# Clips por emoción — filenames en videos/
GATO_CLIPS = {
    "hook":     "profesor gato habla.mp4",    # gancho inicial
    "explain":  "clip_explicando.mp4",         # explicación
    "point":    "clip_señalando.mp4",          # señalando dato
    "surprise": "clip_sorpresa.mp4",           # dato inesperado
    "lesson":   "clip_leccion.mp4",            # cierre / lección
}

BASTET_CLIPS = {
    "confused":  "bastet_confundida.mp4",     # confusión inicial
    "question":  "bastet_pregunta..mp4",      # pregunta directa
    "wow":       "bastet_wow..mp4",           # sorpresa / dato impresionante
    "nod":       "bastet_asintiendo.mp4",     # asentir / de acuerdo
    "notes":     "bastet_apuntes..mp4",       # tomando notas
}

# Emoción por panel y speaker — sigue la estructura narrativa de 6 paneles
_PANEL_EMOTION = {
    1: {"gato": "hook",     "bastet": "wow"},
    2: {"gato": "explain",  "bastet": "confused"},
    3: {"gato": "explain",  "bastet": "question"},
    4: {"gato": "point",    "bastet": "question"},
    5: {"gato": "surprise", "bastet": "wow"},
    6: {"gato": "lesson",   "bastet": "nod"},
}


def elegir_clip_personaje(numero: int, speaker: str) -> Path:
    """
    Devuelve la Path al clip de personaje correcto para este panel.
    Intenta nombre exacto → búsqueda flexible por stem → fallback.
    """
    emotions = _PANEL_EMOTION.get(numero, _PANEL_EMOTION[3])
    speaker_key = "bastet" if speaker == "bastet" else "gato"

    if speaker_key == "bastet":
        emotion   = emotions.get("bastet", "question")
        filename  = BASTET_CLIPS.get(emotion, BASTET_CLIPS["question"])
        fallback  = "bastet_asintiendo.mp4"
    else:
        emotion   = emotions.get("gato", "explain")
        filename  = GATO_CLIPS.get(emotion, GATO_CLIPS["explain"])
        fallback  = "profesor gato habla.mp4"

    candidato = VIDEOS_DIR / filename
    if candidato.exists():
        return candidato

    # Búsqueda flexible (maneja variantes con puntos extras en el nombre)
    stem = Path(filename).stem.rstrip(".")
    matches = list(VIDEOS_DIR.glob(f"*{stem}*"))
    if matches:
        return matches[0]

    return VIDEOS_DIR / fallback
