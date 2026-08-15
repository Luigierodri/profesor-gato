#!/usr/bin/env python3
"""
masterizar_voz.py — Cadena de masterización para la voz de ElevenLabs.

Hace dos cosas que suben muchísimo la calidad percibida y que nadie nota
conscientemente:

  1. RITMO — recorta los silencios largos. ElevenLabs deja pausas de 700 ms
     a 1 s entre frases. Al bajarlas a ~260 ms el video se siente ágil y no
     "leído". Es el cambio más grande en sensación de todo el pipeline.

  2. SONIDO — filtro de graves, control de sibilancia, ecualización de
     presencia, compresión suave y normalización a -14 LUFS (el estándar de
     YouTube). El resultado suena a estudio en vez de a texto-a-voz.

IMPORTANTE — dónde va en el pipeline:

    guion → ElevenLabs → [masterizar_voz]  ← AQUÍ
                              ↓
                       render de video
                              ↓
                    subtítulos → efectos

Tiene que correr ANTES del render, porque el recorte de silencios cambia la
duración del audio. Si se corre después, la voz se desincroniza del video y
de los subtítulos.

Uso:

    from masterizar_voz import masterizar
    masterizar("audio/voz_cruda.mp3", "audio/voz.wav")

    # sin tocar el ritmo (si el timing ya está cerrado):
    masterizar("cruda.mp3", "voz.wav", recortar_silencios=False)

Terminal:

    python masterizar_voz.py voz_cruda.mp3 voz.wav
    python masterizar_voz.py voz_cruda.mp3 voz.wav --pausa 0.30 --lufs -14

Requiere: ffmpeg. Nada más.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

# Estándar de YouTube. Si entregas más bajo, tu video suena débil al lado
# de los demás; si entregas más alto, la plataforma te lo baja igual y
# encima te comes la distorsión.
LUFS_OBJETIVO = -14.0
TRUE_PEAK = -1.5

PAUSA_MAX = 0.26          # a cuánto se recorta un silencio largo
UMBRAL_SILENCIO = -34     # dB por debajo de los cuales se considera silencio


def _ffmpeg(args: list[str]) -> str:
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2500:], file=sys.stderr)
        raise RuntimeError("ffmpeg falló")
    return r.stderr


def medir_lufs(ruta: str) -> tuple[float, float]:
    """Devuelve (LUFS integrado, true peak dBTP)."""
    err = _ffmpeg(["-i", ruta, "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", err, re.S)
    if not m:
        return (0.0, 0.0)
    d = json.loads(m.group(0))
    return (float(d["input_i"]), float(d["input_tp"]))


# ── 1. RITMO ─────────────────────────────────────────────────────────

def recortar_silencios(entrada: str, salida: str,
                       pausa: float = PAUSA_MAX,
                       umbral: int = UMBRAL_SILENCIO) -> str:
    """
    Deja como máximo `pausa` segundos de silencio seguido.

    Se usa silenceremove en modo 'todos los silencios', con stop_periods=-1
    y un margen (stop_silence) que es justo la pausa que queremos conservar.
    No corta a cero: eso suena antinatural y come las respiraciones.
    """
    filtro = (
        f"silenceremove="
        f"stop_periods=-1:"
        f"stop_duration={pausa}:"
        f"stop_threshold={umbral}dB:"
        f"detection=rms"
    )
    _ffmpeg(["-i", entrada, "-af", filtro, "-ar", "48000", "-ac", "1", salida])
    return salida


# ── 2. SONIDO ────────────────────────────────────────────────────────

CADENA = ",".join([
    # rumble y plosivas: nada útil vive debajo de 80 Hz en una voz
    "highpass=f=80",
    # quita el "barro" de los 250-350 Hz que engorda la voz sintética
    "equalizer=f=300:t=q:w=1.1:g=-2.5",
    # presencia: es lo que hace que se entienda sin subir el volumen
    "equalizer=f=3800:t=q:w=1.0:g=2.5",
    # aire: le quita el techo de plástico al TTS
    "equalizer=f=11000:t=q:w=0.9:g=1.5",
    # sibilancia: ElevenLabs marca mucho la S en español
    "deesser=i=0.35:m=0.5:f=0.18",
    # compresión suave: empareja sin aplastar
    "acompressor=threshold=-20dB:ratio=2.6:attack=8:release=180:makeup=1.6",
    # techo de seguridad antes de normalizar
    "alimiter=limit=0.95",
])


def _tiene_deesser() -> bool:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                       capture_output=True, text=True)
    return " deesser " in r.stdout


def masterizar(entrada: str, salida: str,
               recortar: bool = True,
               pausa: float = PAUSA_MAX,
               lufs: float = LUFS_OBJETIVO) -> str:
    if not os.path.exists(entrada):
        sys.exit(f"No existe: {entrada}")

    antes = medir_lufs(entrada)
    dur_antes = _duracion(entrada)
    print(f"[voz] entrada: {dur_antes:.1f}s · {antes[0]:.1f} LUFS · pico {antes[1]:.1f} dBTP")

    cadena = CADENA
    if not _tiene_deesser():
        cadena = ",".join(p for p in CADENA.split(",") if not p.startswith("deesser"))
        print("      (sin deesser en este ffmpeg; se omite)")

    with tempfile.TemporaryDirectory() as tmp:
        actual = entrada

        if recortar:
            paso1 = os.path.join(tmp, "ritmo.wav")
            recortar_silencios(actual, paso1, pausa=pausa)
            actual = paso1
            print(f"      ritmo: {_duracion(actual):.1f}s "
                  f"(-{dur_antes - _duracion(actual):.1f}s de silencio)")

        # loudnorm en dos pasadas: la primera mide, la segunda corrige.
        # Una sola pasada da resultados inconsistentes en audios cortos.
        paso2 = os.path.join(tmp, "eq.wav")
        _ffmpeg(["-i", actual, "-af", cadena, "-ar", "48000", "-ac", "1", paso2])

        err = _ffmpeg(["-i", paso2,
                       "-af", f"loudnorm=I={lufs}:TP={TRUE_PEAK}:LRA=9:print_format=json",
                       "-f", "null", "-"])
        m = re.search(r"\{[^{}]*input_i[^{}]*\}", err, re.S)
        med = json.loads(m.group(0)) if m else {}

        if med:
            ln = (f"loudnorm=I={lufs}:TP={TRUE_PEAK}:LRA=9:"
                  f"measured_I={med['input_i']}:measured_TP={med['input_tp']}:"
                  f"measured_LRA={med['input_lra']}:measured_thresh={med['input_thresh']}:"
                  f"offset={med['target_offset']}:linear=true")
        else:
            ln = f"loudnorm=I={lufs}:TP={TRUE_PEAK}:LRA=9"

        _ffmpeg(["-i", paso2, "-af", ln, "-ar", "48000", "-ac", "1", salida])

    desp = medir_lufs(salida)
    print(f"[voz] salida:  {_duracion(salida):.1f}s · {desp[0]:.1f} LUFS · pico {desp[1]:.1f} dBTP")
    print(f"      {salida}")
    return salida


def _duracion(ruta: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", ruta],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description="Masterización de voz")
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--pausa", type=float, default=PAUSA_MAX,
                    help="segundos máximos de silencio (default 0.26)")
    ap.add_argument("--lufs", type=float, default=LUFS_OBJETIVO)
    ap.add_argument("--sin-recorte", action="store_true",
                    help="no tocar los silencios (conserva la duración)")
    a = ap.parse_args()

    masterizar(a.entrada, a.salida, recortar=not a.sin_recorte,
               pausa=a.pausa, lufs=a.lufs)


if __name__ == "__main__":
    main()
