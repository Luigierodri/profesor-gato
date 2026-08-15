#!/usr/bin/env python3
"""
graficas_animadas.py — Gráficas de datos animadas para video.

Convierte una especificación simple en un clip MP4 listo para intercalar
en el video. Pensado para canal de economía/historia: pocas series, cifras
grandes, cero adorno.

Cuatro formas, elegidas por el trabajo que hace el dato:

    numero   → una sola cifra que ES el titular      ("1.8%")
    barras   → comparar magnitudes entre categorías
    linea    → cambio a lo largo del tiempo
    reparto  → cómo se divide un total (barra 100%)

Uso:

    from graficas_animadas import render_grafica

    render_grafica({
        "forma": "barras",
        "titulo": "¿Quién se queda el valor de un iPhone?",
        "unidad": "%",
        "datos": [("Apple", 58), ("Componentes", 14), ("Ensamblaje", 1.8)],
        "resaltar": 2,
        "fuente": "Kraemer, Linden y Dedrick — UC Irvine",
    }, "grafica.mp4", vertical=False)

Desde terminal:

    python graficas_animadas.py spec.json salida.mp4
    python graficas_animadas.py spec.json salida.mp4 --vertical

Requiere: matplotlib, numpy, ffmpeg.

────────────────────────────────────────────────────────────────────
Decisiones de diseño (no cambiar sin razón):

 · Paleta validada para fondo oscuro con el validador de color del
   sistema de diseño: separación para daltonismo ΔE 9.4, visión normal
   26.5, contraste ≥3:1 contra el fondo. Los tres colores están en orden
   fijo — nunca se ciclan ni se reasignan por ranking.
 · Etiqueta de valor directa sobre cada marca. En video no hay leyenda:
   el ojo no tiene tiempo de ir y volver a un cuadrito.
 · Rejilla recesiva o ausente. En barras estorba; en línea va tenue.
 · Nunca dos ejes Y. Si hay dos magnitudes distintas, son dos gráficas.
 · Nada de pastel/dona: el ojo compara ángulos peor que longitudes.
 · La animación entra con ease-out y se detiene. Nada rebota.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


# ── sistema visual ───────────────────────────────────────────────────

FONDO = "#11151e"            # slate de marca Profesor Gato (data_chart BG)
TEXTO = "#eef0f5"
TEXTO_2 = "#c3c2b7"
TENUE = "#3a3a37"

# ALINEADO A LA MARCA (dorado/slate del canal, igual que data_chart). SERIES[0] =
# dorado apagado (barras normales), SERIES[1] = dorado brillante (la barra RESALTADA);
# los otros dos (teal/coral) solo aparecen en "reparto" multi-categoría. Contraste alto
# sobre el slate. No ciclar; si hay más de 4 categorías se pliegan en "Otros".
SERIES = ["#c9a45a", "#f2c56a", "#78bab9", "#dc6e5f"]
APAGADO = "#4a4a46"          # para las barras que no se resaltan
OTROS = "#6b6b64"            # el pliegue "Otros", fuera de la paleta de series

FPS = 30
DUR_ENTRADA = 1.25           # segundos de animación
DUR_HOLD = 1.6               # segundos quieto al final


def _ease(t: float) -> float:
    """Ease-out cúbico. Entra rápido, se asienta. Sin rebote."""
    return 1 - (1 - t) ** 3


def _fmt(v: float, unidad: str = "") -> str:
    if abs(v) >= 1000:
        s = f"{v:,.0f}".replace(",", " ")
    elif v == int(v):
        s = f"{int(v)}"
    else:
        s = f"{v:.1f}".replace(".", ",")
    return f"{s}{unidad}"


# ── formas ───────────────────────────────────────────────────────────

def _dibujar_numero(ax, spec, p, W, H):
    valor = float(spec["datos"])
    unidad = spec.get("unidad", "")
    ax.axis("off")

    mostrado = valor * _ease(p)
    ax.text(0.5, 0.55, _fmt(mostrado, unidad), transform=ax.transAxes,
            ha="center", va="center", color=SERIES[0],
            fontsize=190 if W > H else 165, fontweight="black")

    if spec.get("titulo"):
        # espaciado entre letras a mano: matplotlib no lo soporta
        titulo = " ".join(spec["titulo"].upper())
        ax.text(0.5, 0.80, titulo, transform=ax.transAxes,
                ha="center", va="center", color=TEXTO_2,
                fontsize=26, fontweight="bold")

    if spec.get("pie"):
        ax.text(0.5, 0.30, spec["pie"], transform=ax.transAxes,
                ha="center", va="center", color=TEXTO,
                fontsize=34, fontweight="semibold", wrap=True)


def _dibujar_barras(ax, spec, p, W, H):
    datos = spec["datos"]
    unidad = spec.get("unidad", "")
    resaltar = spec.get("resaltar")
    etiquetas = [d[0] for d in datos]
    valores = [float(d[1]) for d in datos]
    n = len(datos)

    ax.set_facecolor(FONDO)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_xticks([])
    ax.tick_params(left=False)

    vmax = max(valores) * 1.24
    ax.set_xlim(0, vmax)
    ax.set_ylim(-0.55, n - 0.45)
    ax.invert_yaxis()

    # Grosor de barra en PUNTOS: así el extremo redondeado sale exacto
    # sin pelear con la relación de aspecto de los ejes.
    alto_datos = 0.52
    caja = ax.get_window_extent()
    pts_por_dato = (caja.height / (n + 0.1)) * 72 / ax.figure.dpi
    grosor = alto_datos * pts_por_dato
    radio_x = (grosor / 2) / caja.width * vmax     # medio grosor, en unidades x

    for i, (et, v) in enumerate(zip(etiquetas, valores)):
        # cada barra entra escalonada
        retraso = i * 0.09
        pi = np.clip((p - retraso) / max(1e-6, 1 - retraso), 0, 1)
        largo = v * _ease(pi)

        color = SERIES[0]
        if resaltar is not None:
            color = SERIES[1] if i == resaltar else APAGADO

        if largo > radio_x * 0.6:
            # línea con punta redonda = barra con extremo redondeado
            x0 = min(radio_x, largo / 2)
            x1 = max(largo - radio_x, x0 + 1e-6)
            ax.plot([x0, x1], [i, i], color=color, linewidth=grosor,
                    solid_capstyle="round", zorder=3)
            # el arranque se cuadra contra el eje
            ax.add_patch(plt.Rectangle(
                (0, i - alto_datos / 2), x0, alto_datos,
                facecolor=color, linewidth=0, zorder=3))
        elif largo > 1e-6:
            ax.add_patch(plt.Rectangle(
                (0, i - alto_datos / 2), largo, alto_datos,
                facecolor=color, linewidth=0, zorder=3))

        ax.text(-vmax * 0.018, i, et, ha="right", va="center",
                color=TEXTO if (resaltar is None or i == resaltar) else TEXTO_2,
                fontsize=27, fontweight="bold")

        if pi > 0.08:
            ax.text(largo + vmax * 0.02, i, _fmt(largo, unidad),
                    ha="left", va="center",
                    color=color if color != APAGADO else TEXTO_2,
                    fontsize=30, fontweight="black")

    ax.set_yticks([])


def _dibujar_linea(ax, spec, p, W, H):
    datos = spec["datos"]
    unidad = spec.get("unidad", "")
    xs = [str(d[0]) for d in datos]
    ys = np.array([float(d[1]) for d in datos])

    ax.set_facecolor(FONDO)
    for k, lado in ax.spines.items():
        lado.set_visible(k == "bottom")
        if k == "bottom":
            lado.set_color(TENUE)
            lado.set_linewidth(1.2)

    ax.grid(axis="y", color=TENUE, linewidth=0.8, alpha=0.55)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TEXTO_2, labelsize=20, length=0)

    lo, hi = float(ys.min()), float(ys.max())
    margen = (hi - lo) * 0.30 or 1.0
    ax.set_ylim(lo - margen, hi + margen)
    ax.set_xlim(-0.35, len(ys) - 0.65)

    # la línea se dibuja progresivamente
    corte = _ease(p) * (len(ys) - 1)
    k = int(np.floor(corte))
    frac = corte - k

    px = list(range(k + 1))
    py = list(ys[: k + 1])
    if k + 1 < len(ys) and frac > 0:
        px.append(k + frac)
        py.append(ys[k] + (ys[k + 1] - ys[k]) * frac)

    if len(px) > 1:
        ax.plot(px, py, color=SERIES[0], linewidth=4.5,
                solid_capstyle="round", zorder=3)
        ax.fill_between(px, ax.get_ylim()[0], py,
                        color=SERIES[0], alpha=0.13, zorder=2)

    if px:
        ax.plot([px[-1]], [py[-1]], "o", markersize=15, color=SERIES[0],
                markeredgecolor=FONDO, markeredgewidth=3.5, zorder=4)
        ax.text(px[-1], py[-1] + margen * 0.34, _fmt(py[-1], unidad),
                ha="center", va="bottom", color=TEXTO,
                fontsize=32, fontweight="black", zorder=5)

    paso = max(1, len(xs) // 7)
    ax.set_xticks(range(0, len(xs), paso))
    ax.set_xticklabels([xs[i] for i in range(0, len(xs), paso)])


def _dibujar_reparto(ax, spec, p, W, H):
    datos = list(spec["datos"])

    # Nunca se genera un color nuevo: si hay más categorías que slots,
    # las más chicas se pliegan en "Otros" (gris, fuera de la paleta).
    plegado = False
    if len(datos) > len(SERIES):
        datos.sort(key=lambda d: -float(d[1]))
        cabeza = datos[: len(SERIES) - 1]
        resto = sum(float(d[1]) for d in datos[len(SERIES) - 1:])
        datos = cabeza + [("Otros", resto)]
        plegado = True

    etiquetas = [d[0] for d in datos]
    valores = np.array([float(d[1]) for d in datos])
    pct = valores / valores.sum() * 100

    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)

    y, alto = 0.42, 0.30
    x = 0.0
    e = _ease(p)

    for i, (et, v) in enumerate(zip(etiquetas, pct)):
        w = v * e
        es_otros = plegado and i == len(datos) - 1
        color = OTROS if es_otros else SERIES[i]
        if w > 0.2:
            # 2px de separación entre segmentos: se resuelve dejando hueco
            ax.add_patch(plt.Rectangle((x, y), max(w - 0.35, 0.01), alto,
                                       facecolor=color, linewidth=0, zorder=3))
        if v > 6 and e > 0.35:
            ax.text(x + w / 2, y + alto / 2, f"{v:.0f}%", ha="center",
                    va="center", color="#ffffff", fontsize=30,
                    fontweight="black", zorder=4)
            ax.text(x + w / 2, y - 0.09, et, ha="center", va="top",
                    color=TEXTO_2, fontsize=22, fontweight="bold", zorder=4)
        elif e > 0.6:
            # segmento delgado: etiqueta arriba, anclada para no salirse
            cx = x + w / 2
            if cx > 88:
                ha, tx = "right", 100.0
            elif cx < 12:
                ha, tx = "left", 0.0
            else:
                ha, tx = "center", cx
            ax.text(tx, y + alto + 0.05, f"{et} {v:.1f}%",
                    ha=ha, va="bottom", color=color,
                    fontsize=21, fontweight="bold", zorder=4)
        x += w


FORMAS = {
    "numero": _dibujar_numero,
    "barras": _dibujar_barras,
    "linea": _dibujar_linea,
    "reparto": _dibujar_reparto,
}


# ── render ───────────────────────────────────────────────────────────

def render_grafica(spec: dict, salida: str, vertical: bool = False) -> str:
    forma = spec.get("forma", "barras")
    if forma not in FORMAS:
        sys.exit(f"Forma desconocida: {forma}. Usa: {', '.join(FORMAS)}")

    W, H = (1080, 1920) if vertical else (1920, 1080)
    dpi = 100
    dibujar = FORMAS[forma]

    n_entrada = int(FPS * DUR_ENTRADA)
    n_hold = int(FPS * DUR_HOLD)
    total = n_entrada + n_hold

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-",
         "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "medium",
         "-crf", "16", salida],
        stdin=subprocess.PIPE,
    )

    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi, facecolor=FONDO)

    for f in range(total):
        p = 1.0 if f >= n_entrada else f / max(1, n_entrada - 1)
        fig.clear()
        fig.patch.set_facecolor(FONDO)

        if forma == "numero":
            ax = fig.add_axes([0, 0, 1, 1])
        else:
            izq = 0.30 if forma == "barras" else 0.11
            ax = fig.add_axes([izq, 0.20, 0.94 - izq, 0.56])

        if spec.get("titulo") and forma != "numero":
            fig.text(0.5, 0.88, spec["titulo"], ha="center", va="center",
                     color=TEXTO, fontsize=38, fontweight="black", wrap=True)

        dibujar(ax, spec, p, W, H)

        if spec.get("fuente"):
            fig.text(0.5, 0.055, f"Fuente: {spec['fuente']}", ha="center",
                     va="center", color=TEXTO_2, fontsize=18)

        fig.canvas.draw()
        proc.stdin.write(np.asarray(fig.canvas.buffer_rgba()).tobytes())

    plt.close(fig)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falló al escribir la gráfica")

    print(f"  gráfica: {salida}  ({total/FPS:.1f}s, {forma})")
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description="Gráficas animadas para video")
    ap.add_argument("spec", help="archivo .json con la especificación")
    ap.add_argument("salida")
    ap.add_argument("--vertical", action="store_true", help="9:16 para shorts")
    a = ap.parse_args()

    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    render_grafica(spec, a.salida, vertical=a.vertical)


if __name__ == "__main__":
    main()
