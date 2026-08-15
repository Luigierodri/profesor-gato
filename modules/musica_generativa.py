#!/usr/bin/env python3
"""
musica_generativa.py — Cama musical generada, a la medida exacta del video.

Por qué existe:

  · CERO riesgo de copyright, para siempre. Nada de "esta música fue
    reclamada" tres meses después de publicar.
  · Dura EXACTAMENTE lo que el video. Sin loops que se notan, sin fundido
    torpe a la mitad de una frase.
  · Tiene ARCO. La intensidad sube en el giro y baja en el cierre, en vez de
    ser una pista pareja que aplana el video.
  · Es tuya. Con el tiempo, el mismo material armónico se vuelve el sonido
    reconocible del canal.

Dos ambientes:

    "ensayo"  → Profesor Gato. Pad sostenido, movimiento lento, mucho aire.
                No compite con la voz; sostiene el pensamiento.
    "juego"   → Partida Guardada. Más movimiento, arpegio suave, tono
                nostálgico. Acompaña sin volverse protagonista.

Uso:

    from musica_generativa import generar_cama

    generar_cama(180.5, "musica/cama.wav", ambiente="ensayo", giro=112.0)

    # y después, en el mezclador que ya tienes:
    aplicar_sonido(video, salida, musica="musica/cama.wav")

Terminal:

    python musica_generativa.py 180 cama.wav
    python musica_generativa.py 180 cama.wav --ambiente juego --giro 112
    python musica_generativa.py --del-video final.mp4 cama.wav

Requiere: numpy. (ffprobe solo si usas --del-video.)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import wave

import numpy as np

SR = 48_000

# La cama vive MUY por debajo de la voz. El mezclador además la agacha con
# sidechain; esto es el punto de partida.
NIVEL = 0.16

# Progresiones en grados de una escala menor natural. Sin acordes mayores
# brillantes: en contenido de economía e historia suenan a publicidad.
AMBIENTES = {
    "ensayo": {
        "raiz": 55.0,          # La1
        "compas": 8.0,         # segundos por acorde
        "grados": [0, 5, 3, 7],       # i - VI - iv - VII
        "arpegio": False,
        "pulso": True,
        "aire": 0.030,
    },
    "juego": {
        "raiz": 61.74,         # Si1
        "compas": 4.0,
        "grados": [0, 7, 5, 3],
        "arpegio": True,
        "pulso": True,
        "aire": 0.022,
    },
}

# Menor natural, en semitonos
ESCALA = [0, 2, 3, 5, 7, 8, 10, 12]


def _nota(raiz: float, semis: float) -> float:
    return raiz * (2 ** (semis / 12))


def _pasabajos(x: np.ndarray, corte: np.ndarray) -> np.ndarray:
    """Un polo, con frecuencia de corte variable. Suficiente y estable."""
    y = np.empty_like(x)
    a = np.clip(2 * np.pi * corte / SR, 0, 0.99)
    v = 0.0
    for i in range(len(x)):
        v += a[i] * (x[i] - v)
        y[i] = v
    return y


def _voz_pad(f: float, n: int, detune: float = 0.004) -> np.ndarray:
    """Una nota del pad: tres osciladores desafinados, sin ataque duro."""
    t = np.arange(n) / SR
    x = np.zeros(n)
    for k, d in enumerate((-detune, 0.0, detune)):
        ff = f * (1 + d)
        x += np.sin(2 * np.pi * ff * t + k * 1.7)
        x += 0.30 * np.sin(2 * np.pi * 2 * ff * t + k)
        x += 0.14 * np.sin(2 * np.pi * 3 * ff * t + k * 2.3)
    return x / 3


def _envolvente_acorde(n: int) -> np.ndarray:
    """Entra suave, se sostiene, sale suave. Los acordes se traslapan."""
    a = int(n * 0.28)
    d = int(n * 0.34)
    s = n - a - d
    return np.concatenate([
        np.linspace(0, 1, a) ** 1.6,
        np.ones(max(0, s)),
        np.linspace(1, 0, d) ** 1.2,
    ])[:n]


def _arco(n: int, giro: float | None, dur: float) -> np.ndarray:
    """
    Curva de intensidad del video:
      entrada baja → cuerpo estable → swell en el giro → cierre que decae.
    """
    t = np.linspace(0, dur, n)
    e = np.ones(n) * 0.72

    entrada = np.clip(t / max(dur * 0.06, 1e-6), 0, 1)
    e *= 0.45 + 0.55 * entrada

    salida = np.clip((dur - t) / max(dur * 0.10, 1e-6), 0, 1)
    e *= 0.25 + 0.75 * salida

    if giro is not None and 0 < giro < dur:
        ancho = max(dur * 0.05, 4.0)
        e += 0.42 * np.exp(-((t - giro) ** 2) / (2 * (ancho / 2.2) ** 2))

    return np.clip(e, 0, 1.35)


def _reverb(x: np.ndarray) -> np.ndarray:
    """Cola corta con tres retardos primos. Barato y no enturbia."""
    y = x.copy()
    for retardo_ms, g in ((37, 0.26), (61, 0.19), (113, 0.13)):
        d = int(SR * retardo_ms / 1000)
        y[d:] += g * x[:-d]
    return y


def generar_cama(duracion: float, salida: str,
                 ambiente: str = "ensayo",
                 giro: float | None = None,
                 semilla: int = 0) -> str:
    if ambiente not in AMBIENTES:
        sys.exit(f"Ambiente desconocido: {ambiente}. Usa: {', '.join(AMBIENTES)}")

    cfg = AMBIENTES[ambiente]
    rng = np.random.default_rng(semilla)
    n = int(SR * duracion)
    mezcla = np.zeros(n + SR)          # cola extra para las colas de reverb

    compas = int(SR * cfg["compas"])
    largo_acorde = int(compas * 1.55)  # se traslapan: nunca hay silencio entre acordes
    i = 0
    paso = 0

    while i < n:
        grado = cfg["grados"][paso % len(cfg["grados"])]
        base = _nota(cfg["raiz"], ESCALA[grado % len(ESCALA)] + 12 * (grado // len(ESCALA)))

        largo = min(largo_acorde, len(mezcla) - i)
        if largo <= 0:
            break
        env = _envolvente_acorde(largo)

        # triada + octava, en registro medio para no pelear con la voz
        for mult, gan in ((2, 0.55), (3, 0.34), (4, 0.22), (6, 0.12)):
            semis = ESCALA[(grado + [0, 2, 4][min(2, mult - 2)]) % len(ESCALA)]
            f = _nota(cfg["raiz"], semis) * (mult / 2)
            if f > 2200:
                continue
            mezcla[i:i + largo] += gan * _voz_pad(f, largo) * env

        # sub: la fundamental, muy grave, casi subliminal
        if cfg["pulso"]:
            t = np.arange(largo) / SR
            sub = np.sin(2 * np.pi * base * t)
            latido = 0.62 + 0.38 * (np.sin(2 * np.pi * (60 / 60) * t - np.pi / 2) ** 4)
            mezcla[i:i + largo] += 0.42 * sub * env * latido

        # arpegio suave (solo "juego")
        if cfg["arpegio"]:
            notas = [0, 2, 4, 6, 4, 2]
            paso_arp = int(SR * cfg["compas"] / len(notas))
            for j, g in enumerate(notas):
                off = i + j * paso_arp
                if off + paso_arp >= len(mezcla):
                    break
                f = _nota(cfg["raiz"], ESCALA[(grado + g) % len(ESCALA)]) * 4
                t = np.arange(paso_arp) / SR
                nota = np.sin(2 * np.pi * f * t) * np.exp(-5.5 * t)
                mezcla[off:off + paso_arp] += 0.085 * nota

        i += compas
        paso += 1

    # capa de aire: ruido filtrado, le quita lo sintético al conjunto
    aire = rng.normal(0, 1, len(mezcla))
    aire = _pasabajos(aire, np.full(len(mezcla), 900.0))
    mezcla += cfg["aire"] * aire / (np.abs(aire).max() + 1e-9)

    mezcla = _reverb(mezcla)[:n]

    # filtro que se abre con la intensidad: en el giro suena más presente
    arco = _arco(n, giro, duracion)
    mezcla = _pasabajos(mezcla, 700 + 1500 * arco)
    mezcla *= arco

    pico = np.abs(mezcla).max()
    if pico > 0:
        mezcla = mezcla / pico * NIVEL

    pcm = (np.repeat((mezcla * 32767).astype(np.int16)[:, None], 2, 1).ravel())
    with wave.open(salida, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    print(f"[música] {salida} · {duracion:.1f}s · {ambiente}"
          + (f" · giro en {giro:.1f}s" if giro else ""))
    return salida


def duracion_de(video: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", video],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description="Cama musical generada")
    ap.add_argument("duracion", nargs="?", type=float,
                    help="segundos (o usa --del-video)")
    ap.add_argument("salida")
    ap.add_argument("--del-video", help="toma la duración de este video")
    ap.add_argument("--ambiente", choices=list(AMBIENTES), default="ensayo")
    ap.add_argument("--giro", type=float, help="segundo del giro (swell)")
    ap.add_argument("--semilla", type=int, default=0,
                    help="cambia la variación aleatoria")
    a = ap.parse_args()

    dur = duracion_de(a.del_video) if a.del_video else a.duracion
    if not dur:
        sys.exit("Falta la duración: pásala como número o usa --del-video")

    generar_cama(dur, a.salida, ambiente=a.ambiente, giro=a.giro,
                 semilla=a.semilla)


if __name__ == "__main__":
    main()
