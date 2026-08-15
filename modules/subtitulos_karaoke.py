#!/usr/bin/env python3
"""
subtitulos_karaoke.py — Subtítulos palabra por palabra estilo TikTok/Reels.

Genera un .ass con karaoke real (palabra activa resaltada) y lo quema en el video.

Uso típico dentro de tu pipeline:

    from subtitulos_karaoke import quemar_subtitulos

    quemar_subtitulos(
        video_in="videos/render_crudo.mp4",
        audio_voz="audio/voz.mp3",       # el mismo audio de ElevenLabs
        video_out="videos/final.mp4",
        estilo=ESTILO_SHORT,             # o ESTILO_LARGO
    )

Desde terminal:

    python subtitulos_karaoke.py crudo.mp4 voz.mp3 final.mp4
    python subtitulos_karaoke.py crudo.mp4 voz.mp3 final.mp4 --estilo largo
    python subtitulos_karaoke.py crudo.mp4 voz.mp3 final.mp4 --guion guion.txt

Dependencias:
    pip install faster-whisper
    ffmpeg en el PATH

Notas de diseño (por qué está hecho así):
  - faster-whisper con word_timestamps da los tiempos por palabra. Es lo único
    que se necesita; no hace falta ningún servicio de pago.
  - Se escribe .ass y no .srt porque .srt no soporta resaltado por palabra.
  - Si le pasas --guion con el texto exacto que mandaste a ElevenLabs, se usa
    ese texto (respeta tus mayúsculas, números y nombres propios) y Whisper
    solo aporta los tiempos. Es notablemente más preciso.
  - Cero dependencias exóticas a propósito: esto tiene que seguir corriendo
    dentro de cinco años sin que nadie lo mantenga.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable


# ─────────────────────────────────────────────────────────────────────
#  ESTILOS
# ─────────────────────────────────────────────────────────────────────

@dataclass
class Estilo:
    """Todo lo visual vive aquí. Para cambiar el look, toca solo esto."""

    fuente: str = "Montserrat ExtraBold"
    tamano: int = 78                  # px sobre 1080 de ancho
    color_base: str = "&H00FFFFFF"    # blanco       (ASS = &HAABBGGRR)
    color_activo: str = "&H0000D4FF"  # amarillo     (BGR invertido)
    color_borde: str = "&H00000000"   # negro
    grosor_borde: int = 5
    sombra: int = 2

    # Posición: 2 = abajo-centro, 5 = centro, 8 = arriba-centro
    alineacion: int = 2
    margen_vertical: int = 380        # sube el texto desde abajo (9:16)
    margen_lateral: int = 90

    palabras_por_bloque: int = 3      # cuántas se ven a la vez
    pop: bool = True                  # escala 1.0 → 1.08 al entrar
    mayusculas: bool = True

    resolucion: tuple[int, int] = (1080, 1920)

    # Palabras que NUNCA se resaltan aunque caigan en turno (son de relleno)
    sin_resalte: set[str] = field(default_factory=lambda: {
        "de", "la", "el", "los", "las", "un", "una", "y", "o", "que", "en",
        "a", "al", "del", "se", "es", "por", "con", "para", "su", "lo", "le",
    })


ESTILO_SHORT = Estilo()

ESTILO_LARGO = Estilo(
    tamano=58,
    palabras_por_bloque=5,
    margen_vertical=120,
    alineacion=2,
    resolucion=(1920, 1080),
    pop=False,          # en 16:9 el pop distrae
    mayusculas=False,
)


# ─────────────────────────────────────────────────────────────────────
#  TRANSCRIPCIÓN
# ─────────────────────────────────────────────────────────────────────

@dataclass
class Palabra:
    texto: str
    inicio: float
    fin: float


def transcribir(audio: str, modelo: str = "small", idioma: str = "es") -> list[Palabra]:
    """Devuelve la lista de palabras con sus tiempos, usando faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit(
            "Falta faster-whisper.\n"
            "  pip install faster-whisper\n"
        )

    print(f"[1/4] Transcribiendo con whisper '{modelo}' ...")
    wm = WhisperModel(modelo, device="cpu", compute_type="int8")
    segmentos, _ = wm.transcribe(audio, language=idioma, word_timestamps=True)

    palabras: list[Palabra] = []
    for seg in segmentos:
        for w in (seg.words or []):
            texto = w.word.strip()
            if texto:
                palabras.append(Palabra(texto, float(w.start), float(w.end)))

    print(f"      {len(palabras)} palabras detectadas")
    return palabras


def _normalizar(s: str) -> str:
    """Para comparar palabras ignorando acentos, signos y mayúsculas."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", s)


def alinear_con_guion(palabras: list[Palabra], guion: str) -> list[Palabra]:
    """
    Sustituye el texto transcrito por el del guion original, conservando los
    tiempos. Whisper acierta los tiempos pero se equivoca en nombres propios,
    cifras y anglicismos; el guion no.

    Avanza en paralelo y solo reemplaza cuando la palabra coincide de forma
    aproximada, así un desfase no arruina el resto.
    """
    del_guion = [p for p in re.split(r"\s+", guion.strip()) if p]
    if not del_guion:
        return palabras

    salida: list[Palabra] = []
    j = 0
    for p in palabras:
        if j >= len(del_guion):
            salida.append(p)
            continue

        candidato = del_guion[j]
        if _normalizar(candidato) == _normalizar(p.texto):
            salida.append(Palabra(candidato, p.inicio, p.fin))
            j += 1
        else:
            # Busca hasta 3 adelante por si whisper se comió o inventó algo
            ventana = del_guion[j : j + 4]
            hit = next(
                (k for k, c in enumerate(ventana) if _normalizar(c) == _normalizar(p.texto)),
                None,
            )
            if hit is not None:
                salida.append(Palabra(ventana[hit], p.inicio, p.fin))
                j += hit + 1
            else:
                salida.append(p)

    print(f"[2/4] Alineado con el guion original")
    return salida


# ─────────────────────────────────────────────────────────────────────
#  GENERACIÓN DEL .ASS
# ─────────────────────────────────────────────────────────────────────

def _t(segundos: float) -> str:
    """Formato de tiempo ASS: H:MM:SS.cc"""
    segundos = max(0.0, segundos)
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _bloques(palabras: list[Palabra], n: int) -> Iterable[list[Palabra]]:
    """Agrupa de n en n, cortando antes si hay una pausa larga (respiración)."""
    grupo: list[Palabra] = []
    for i, p in enumerate(palabras):
        grupo.append(p)
        pausa_larga = (
            i + 1 < len(palabras) and palabras[i + 1].inicio - p.fin > 0.45
        )
        if len(grupo) >= n or pausa_larga or i == len(palabras) - 1:
            yield grupo
            grupo = []


def generar_ass(palabras: list[Palabra], estilo: Estilo, destino: str) -> str:
    ancho, alto = estilo.resolucion

    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ancho}
PlayResY: {alto}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{estilo.fuente},{estilo.tamano},{estilo.color_base},{estilo.color_activo},{estilo.color_borde},&H80000000,-1,0,0,0,100,100,0,0,1,{estilo.grosor_borde},{estilo.sombra},{estilo.alineacion},{estilo.margen_lateral},{estilo.margen_lateral},{estilo.margen_vertical},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lineas: list[str] = []
    grupos = list(_bloques(palabras, estilo.palabras_por_bloque))

    for gi, grupo in enumerate(grupos):
        # El bloque se sostiene un poco después de la última palabra, pero
        # nunca invade el siguiente (si se solapan, ffmpeg los encima).
        fin = grupo[-1].fin + 0.08
        if gi + 1 < len(grupos):
            fin = min(fin, grupos[gi + 1][0].inicio - 0.01)
        fin = max(fin, grupo[-1].fin)

        # Una línea de diálogo por palabra activa: la activa en color de acento,
        # las demás del bloque en blanco. Así se lee el contexto y se sigue el ritmo.
        for idx, activa in enumerate(grupo):
            partes = []
            for k, p in enumerate(grupo):
                txt = p.texto.upper() if estilo.mayusculas else p.texto
                txt = txt.replace("{", "").replace("}", "")
                resaltable = _normalizar(p.texto) not in estilo.sin_resalte
                if k == idx and resaltable:
                    partes.append(f"{{\\c{estilo.color_activo}}}{txt}{{\\c{estilo.color_base}}}")
                else:
                    partes.append(txt)
            texto = " ".join(partes)

            a = activa.inicio
            b = grupo[idx + 1].inicio if idx + 1 < len(grupo) else fin
            if b <= a:
                b = a + 0.05

            efecto = ""
            if estilo.pop and idx == 0:
                # escala 108% → 100% en 120 ms al entrar el bloque
                efecto = "{\\fscx108\\fscy108\\t(0,120,\\fscx100\\fscy100)}"

            lineas.append(
                f"Dialogue: 0,{_t(a)},{_t(b)},Cap,,0,0,0,,{efecto}{texto}"
            )

    with open(destino, "w", encoding="utf-8") as f:
        f.write(cabecera + "\n".join(lineas) + "\n")

    print(f"[3/4] Subtítulos escritos: {destino} ({len(lineas)} eventos)")
    return destino


# ─────────────────────────────────────────────────────────────────────
#  QUEMADO
# ─────────────────────────────────────────────────────────────────────

def quemar(video_in: str, ass: str, video_out: str, crf: int = 18) -> str:
    ruta = ass.replace("\\", "/").replace(":", r"\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_in,
        "-vf", f"subtitles='{ruta}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-c:a", "copy",
        video_out,
    ]
    print(f"[4/4] Quemando subtítulos ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2500:], file=sys.stderr)
        raise RuntimeError("ffmpeg falló")
    print(f"      Listo: {video_out}")
    return video_out


def quemar_subtitulos(
    video_in: str,
    audio_voz: str,
    video_out: str,
    estilo: Estilo = ESTILO_SHORT,
    guion: str | None = None,
    modelo: str = "small",
) -> str:
    """Función principal. Es la que llamas desde tu pipeline."""
    palabras = transcribir(audio_voz, modelo=modelo)
    if not palabras:
        raise RuntimeError("No se detectaron palabras en el audio")

    if guion:
        palabras = alinear_con_guion(palabras, guion)

    ass = os.path.splitext(video_out)[0] + ".ass"
    generar_ass(palabras, estilo, ass)
    return quemar(video_in, ass, video_out)


# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Subtítulos palabra por palabra")
    ap.add_argument("video_in")
    ap.add_argument("audio_voz")
    ap.add_argument("video_out")
    ap.add_argument("--estilo", choices=["short", "largo"], default="short")
    ap.add_argument("--guion", help="archivo .txt con el guion original")
    ap.add_argument("--modelo", default="small",
                    help="tiny | base | small | medium (small basta para español)")
    a = ap.parse_args()

    texto = None
    if a.guion:
        with open(a.guion, encoding="utf-8") as f:
            texto = f.read()

    quemar_subtitulos(
        video_in=a.video_in,
        audio_voz=a.audio_voz,
        video_out=a.video_out,
        estilo=ESTILO_SHORT if a.estilo == "short" else ESTILO_LARGO,
        guion=texto,
        modelo=a.modelo,
    )


if __name__ == "__main__":
    main()
