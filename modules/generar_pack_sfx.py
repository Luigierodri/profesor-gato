#!/usr/bin/env python3
"""
generar_pack_sfx.py — Sintetiza un pack de efectos de sonido usable.

Se corre UNA sola vez y deja los .wav en pack_sfx/.

Existe para que el pipeline funcione hoy, sin depender de descargar nada ni
de licencias de terceros. Los sonidos son sintetizados aquí mismo, así que
son libres de uso sin atribución.

Cuando quieras subir de nivel, reemplaza los archivos por otros del mismo
nombre (Pixabay Audio, Mixkit, Freesound CC0) y el resto del pipeline no
se entera.

    python generar_pack_sfx.py
"""

from __future__ import annotations

import os
import wave

import numpy as np

SR = 48_000
DESTINO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pack_sfx")


# ── utilidades ───────────────────────────────────────────────────────

def _guardar(nombre: str, x: np.ndarray) -> None:
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.89          # normaliza
    pcm = (x * 32767).astype(np.int16)
    estereo = np.repeat(pcm[:, None], 2, axis=1).ravel()

    ruta = os.path.join(DESTINO, nombre)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(estereo.tobytes())
    print(f"  {nombre:22s} {len(x)/SR:.2f}s")


def _t(dur: float) -> np.ndarray:
    return np.linspace(0, dur, int(SR * dur), endpoint=False)


def _env(n: int, ataque: float = 0.01, caida: float = 0.9, curva: float = 2.5) -> np.ndarray:
    """Envolvente ataque rápido / caída exponencial."""
    a = max(1, int(n * ataque))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    d = n - a
    e[a:] = np.exp(-curva * np.linspace(0, 1, d) / max(caida, 1e-3))
    return e


def _bandpass(x: np.ndarray, f0: np.ndarray, q: float = 2.0) -> np.ndarray:
    """Filtro pasa-banda de un polo, con frecuencia variable en el tiempo."""
    y = np.zeros_like(x)
    lp = 0.0
    bp = 0.0
    for i in range(len(x)):
        f = 2 * np.sin(np.pi * min(f0[i], SR * 0.45) / SR)
        hp = x[i] - lp - q * bp
        bp += f * hp
        lp += f * bp
        y[i] = bp
    return y


# ── los sonidos ──────────────────────────────────────────────────────

def whoosh(subiendo: bool = True, dur: float = 0.34) -> np.ndarray:
    """Transición de corte. Ruido filtrado barriendo en frecuencia."""
    n = int(SR * dur)
    rng = np.random.default_rng(7 if subiendo else 11)
    ruido = rng.normal(0, 1, n)
    f = np.linspace(380, 4200, n) if subiendo else np.linspace(4200, 380, n)
    x = _bandpass(ruido, f, q=1.4)
    curva = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6      # entra y sale
    return x * curva


def pop(dur: float = 0.085) -> np.ndarray:
    """Entrada de dato o de texto. Blip corto y limpio."""
    t = _t(dur)
    n = len(t)
    f = np.linspace(1150, 620, n)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x += 0.25 * np.sin(2 * np.pi * 2 * np.cumsum(f) / SR)
    return x * _env(n, ataque=0.004, curva=6.0)


def ding(dur: float = 0.55) -> np.ndarray:
    """Confirmación / dato positivo. Campana corta."""
    t = _t(dur)
    n = len(t)
    x = (
        1.00 * np.sin(2 * np.pi * 1318 * t)
        + 0.45 * np.sin(2 * np.pi * 1975 * t)
        + 0.22 * np.sin(2 * np.pi * 2637 * t)
    )
    return x * _env(n, ataque=0.002, curva=4.2)


def impacto(dur: float = 0.85) -> np.ndarray:
    """El giro, la revelación. Golpe grave con cuerpo."""
    t = _t(dur)
    n = len(t)
    f = np.linspace(150, 42, n)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR)

    rng = np.random.default_rng(23)
    golpe = rng.normal(0, 1, n) * np.exp(-38 * np.linspace(0, 1, n))
    golpe = _bandpass(golpe, np.linspace(2600, 500, n), q=1.1)

    x = sub * _env(n, ataque=0.002, curva=3.0) + 0.32 * golpe
    return x


def thud(dur: float = 0.30) -> np.ndarray:
    """Dato negativo, error, algo que sale mal. Seco, sin cola."""
    t = _t(dur)
    n = len(t)
    f = np.linspace(210, 70, n)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return x * _env(n, ataque=0.002, curva=9.0)


def sparkle(dur: float = 0.75) -> np.ndarray:
    """Adorno para remates positivos. Notas altas escalonadas."""
    n = int(SR * dur)
    x = np.zeros(n)
    for k, fr in enumerate([2093, 2637, 3136, 4186]):
        off = int(SR * 0.055 * k)
        largo = n - off
        if largo <= 0:
            break
        tt = np.arange(largo) / SR
        x[off:] += (0.85 ** k) * np.sin(2 * np.pi * fr * tt) * np.exp(-7.5 * tt)
    return x


def swoosh_out(dur: float = 0.55) -> np.ndarray:
    """Salida / cierre del video."""
    n = int(SR * dur)
    rng = np.random.default_rng(31)
    x = _bandpass(rng.normal(0, 1, n), np.linspace(3200, 220, n), q=1.6)
    return x * np.exp(-3.2 * np.linspace(0, 1, n))


# ── main ─────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(DESTINO, exist_ok=True)
    print(f"Generando pack en {DESTINO}/")
    _guardar("whoosh.wav", whoosh(True))
    _guardar("whoosh_down.wav", whoosh(False))
    _guardar("pop.wav", pop())
    _guardar("ding.wav", ding())
    _guardar("impacto.wav", impacto())
    _guardar("thud.wav", thud())
    _guardar("sparkle.wav", sparkle())
    _guardar("swoosh_out.wav", swoosh_out())
    print("Listo.")


if __name__ == "__main__":
    main()
