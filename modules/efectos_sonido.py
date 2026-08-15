#!/usr/bin/env python3
"""
efectos_sonido.py — Diseño de sonido automático para el pipeline de video.

Hace tres cosas:
  1. Detecta los cortes de escena del video ya renderizado.
  2. Arma un plan de efectos (whoosh en los cortes, pop en los datos,
     impacto en el giro) respetando reglas anti-saturación.
  3. Lo mezcla todo con ffmpeg, con la música agachándose bajo la voz.

Uso dentro del pipeline:

    from efectos_sonido import aplicar_sonido

    aplicar_sonido(
        video_in="videos/con_subs.mp4",
        video_out="videos/final.mp4",
        guion="guion.txt",            # opcional, mejora la colocación
        musica="musica/cama.mp3",     # opcional
        marcas={12.4: "impacto"},     # opcional: el giro del video
    )

Desde terminal:

    python efectos_sonido.py con_subs.mp4 final.mp4
    python efectos_sonido.py con_subs.mp4 final.mp4 --musica cama.mp3 --giro 12.4

Requiere: ffmpeg. Nada más.
Antes de la primera corrida: python generar_pack_sfx.py
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass

AQUI = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(AQUI, "pack_sfx")


# ─────────────────────────────────────────────────────────────────────
#  REGLAS (todo lo ajustable vive aquí)
# ─────────────────────────────────────────────────────────────────────

VOLUMEN_DB = {
    "whoosh":      -18,
    "whoosh_down": -18,
    "pop":         -15,
    "ding":        -16,
    "impacto":     -12,
    "thud":        -14,
    "sparkle":     -16,
    "swoosh_out":  -18,
}

# El efecto entra un pelín ANTES del corte visual. Se siente natural;
# si cae exactamente encima o después, se siente pegado y barato.
ADELANTO_S = 0.06

# Los whoosh de corte NO se limitan: son suaves, van pegados al movimiento
# visual y el oído los lee como parte de la edición.
# Lo que satura son los acentos fuertes (pop, ding, impacto). Esos sí se topan.
MAX_ACENTOS_POR_MINUTO = 6
ACENTOS = {"pop", "ding", "impacto", "thud", "sparkle"}

# Separación mínima entre dos efectos cualesquiera.
SEPARACION_MIN_S = 0.7

UMBRAL_ESCENA = 0.30      # sensibilidad del detector de cortes
MUSICA_DB = -26           # cama musical
DUCK_DB = -8              # cuánto se agacha la música bajo la voz


@dataclass
class Marcador:
    tiempo: float
    sonido: str

    @property
    def archivo(self) -> str:
        return os.path.join(PACK, f"{self.sonido}.wav")


# ─────────────────────────────────────────────────────────────────────
#  1. DETECCIÓN DE CORTES
# ─────────────────────────────────────────────────────────────────────

def detectar_cortes(video: str, umbral: float = UMBRAL_ESCENA) -> list[float]:
    """Devuelve los segundos donde cambia la escena, usando ffmpeg."""
    cmd = [
        "ffmpeg", "-i", video,
        "-filter:v", f"select='gt(scene,{umbral})',showinfo",
        "-f", "null", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    tiempos = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    tiempos = [t for t in tiempos if t > 0.4]      # ignora el primer frame
    print(f"  cortes detectados: {len(tiempos)}")
    return sorted(tiempos)


def duracion(video: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", video],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────────────────────────────
#  2. PLAN DE EFECTOS
# ─────────────────────────────────────────────────────────────────────

def _momentos_de_dato(guion: str, dur_video: float) -> list[float]:
    """
    Estima en qué segundo caen las cifras del guion, para poner un 'pop'.

    Aproximación por posición proporcional de la palabra dentro del texto.
    No es exacta al frame, pero para un efecto de 85 ms es suficiente y no
    requiere volver a transcribir nada.
    """
    palabras = [p for p in re.split(r"\s+", guion.strip()) if p]
    if not palabras:
        return []

    momentos = []
    for i, p in enumerate(palabras):
        if re.search(r"\d", p) or re.fullmatch(r"[A-ZÁÉÍÓÚÑ]{3,}", p):
            momentos.append(dur_video * (i / len(palabras)))
    return momentos


def armar_plan(
    cortes: list[float],
    dur_video: float,
    guion: str | None = None,
    marcas: dict[float, str] | None = None,
) -> list[Marcador]:
    """
    Junta todas las fuentes de efectos y aplica las reglas anti-saturación.

    Prioridad cuando dos efectos compiten por el mismo instante:
        marcas manuales > pop de dato > whoosh de corte
    """
    candidatos: list[tuple[int, Marcador]] = []

    for t, s in (marcas or {}).items():
        candidatos.append((0, Marcador(float(t), s)))

    if guion:
        for t in _momentos_de_dato(guion, dur_video):
            candidatos.append((1, Marcador(t, "pop")))

    for t in cortes:
        candidatos.append((2, Marcador(t, "whoosh")))

    if dur_video > 3:
        candidatos.append((0, Marcador(dur_video - 0.55, "swoosh_out")))

    # Orden: por tiempo, y a igual tiempo gana la prioridad más alta
    candidatos.sort(key=lambda c: (c[1].tiempo, c[0]))

    # Separación mínima. Si dos chocan, se queda el de MÁS prioridad
    # (un impacto marcado a mano nunca lo tumba un whoosh automático).
    plan_p: list[tuple[int, Marcador]] = []
    for pri, m in candidatos:
        if plan_p and m.tiempo - plan_p[-1][1].tiempo < SEPARACION_MIN_S:
            if pri < plan_p[-1][0]:
                plan_p[-1] = (pri, m)
            continue
        plan_p.append((pri, m))

    # Tope de acentos fuertes. Los whoosh y el cierre pasan siempre;
    # las marcas manuales (prioridad 0) tampoco se tocan nunca.
    acentos = [(p, m) for p, m in plan_p if m.sonido in ACENTOS]
    tope = max(2, round(MAX_ACENTOS_POR_MINUTO * dur_video / 60))
    if len(acentos) > tope:
        manuales = [(p, m) for p, m in acentos if p == 0]
        auto = [(p, m) for p, m in acentos if p != 0]
        cupo = max(0, tope - len(manuales))
        if cupo and auto:
            paso = max(1, round(len(auto) / cupo))
            auto = auto[::paso][:cupo]
        else:
            auto = []
        conservar = {id(m) for _, m in manuales + auto}
        plan_p = [
            (p, m) for p, m in plan_p
            if m.sonido not in ACENTOS or id(m) in conservar
        ]

    plan = [m for _, m in plan_p]

    # Aplica el adelanto y descarta lo que se salga del video
    plan = [
        Marcador(max(0.0, m.tiempo - ADELANTO_S), m.sonido)
        for m in plan
        if 0 <= m.tiempo <= dur_video
    ]

    print(f"  efectos colocados: {len(plan)}")
    for m in plan[:12]:
        print(f"    {m.tiempo:7.2f}s  {m.sonido}")
    if len(plan) > 12:
        print(f"    ... y {len(plan)-12} más")
    return plan


# ─────────────────────────────────────────────────────────────────────
#  3. MEZCLA
# ─────────────────────────────────────────────────────────────────────

def mezclar(
    video_in: str,
    plan: list[Marcador],
    video_out: str,
    musica: str | None = None,
) -> str:
    faltantes = sorted({m.archivo for m in plan if not os.path.exists(m.archivo)})
    if faltantes:
        sys.exit(
            "Faltan sonidos del pack:\n  "
            + "\n  ".join(faltantes)
            + "\n\nCorre primero:  python generar_pack_sfx.py"
        )

    entradas = ["-i", video_in]
    for m in plan:
        entradas += ["-i", m.archivo]
    if musica:
        entradas += ["-i", musica]

    filtros: list[str] = []
    etiquetas: list[str] = []

    # La voz del video original es siempre la referencia
    filtros.append("[0:a]aformat=sample_rates=48000:channel_layouts=stereo[voz]")

    for i, m in enumerate(plan, start=1):
        ms = int(round(m.tiempo * 1000))
        db = VOLUMEN_DB.get(m.sonido, -18)
        filtros.append(
            f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"volume={db}dB,adelay={ms}:all=1[s{i}]"
        )
        etiquetas.append(f"[s{i}]")

    if musica:
        idx = len(plan) + 1
        filtros.append(
            f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"volume={MUSICA_DB}dB,aloop=loop=-1:size=2e9[mus_raw]"
        )
        # La música se agacha automáticamente cuando habla la voz
        filtros.append(
            f"[mus_raw][voz]sidechaincompress="
            f"threshold=0.03:ratio=6:attack=12:release=320:makeup=1[mus]"
        )
        etiquetas.append("[mus]")

    n = len(etiquetas) + 1
    filtros.append(
        "[voz]" + "".join(etiquetas)
        + f"amix=inputs={n}:normalize=0:dropout_transition=0,"
          "alimiter=limit=0.97[mezcla]"
    )

    cmd = (
        ["ffmpeg", "-y"] + entradas
        + ["-filter_complex", ";".join(filtros),
           "-map", "0:v", "-map", "[mezcla]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-shortest", video_out]
    )

    print("  mezclando ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:], file=sys.stderr)
        raise RuntimeError("ffmpeg falló en la mezcla")
    print(f"  listo: {video_out}")
    return video_out


# ─────────────────────────────────────────────────────────────────────

def aplicar_sonido(
    video_in: str,
    video_out: str,
    guion: str | None = None,
    musica: str | None = None,
    marcas: dict[float, str] | None = None,
) -> str:
    """Función principal. Es la que llamas desde tu pipeline."""
    print(f"[sonido] {os.path.basename(video_in)}")
    dur = duracion(video_in)
    cortes = detectar_cortes(video_in)

    texto = None
    if guion:
        if os.path.exists(guion):
            with open(guion, encoding="utf-8") as f:
                texto = f.read()
        else:
            texto = guion

    plan = armar_plan(cortes, dur, texto, marcas)
    return mezclar(video_in, plan, video_out, musica)


def main() -> None:
    ap = argparse.ArgumentParser(description="Diseño de sonido automático")
    ap.add_argument("video_in")
    ap.add_argument("video_out")
    ap.add_argument("--guion", help="archivo .txt del guion")
    ap.add_argument("--musica", help="cama musical (mp3/wav)")
    ap.add_argument("--giro", type=float,
                    help="segundo del giro/revelación (pone el impacto)")
    a = ap.parse_args()

    aplicar_sonido(
        video_in=a.video_in,
        video_out=a.video_out,
        guion=a.guion,
        musica=a.musica,
        marcas={a.giro: "impacto"} if a.giro is not None else None,
    )


if __name__ == "__main__":
    main()
