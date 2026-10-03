#!/usr/bin/env python3
"""
graficas_animadas.py — Gráficas de datos animadas para video.

Convierte una especificación simple en un clip MP4 listo para intercalar
en el video. Pensado para canal de economía/historia: pocas series, cifras
grandes, cero adorno.

Cuatro formas, elegidas por el trabajo que hace el dato:

    numero      → una sola cifra que ES el titular      ("1.8%")
    barras      → comparar magnitudes entre categorías
    linea       → cambio a lo largo del tiempo
    reparto     → cómo se divide un total (barra 100%)
    comparacion → dos casos enfrentados, con varias cifras cada uno
                  (Chile vs Haití, 1985 vs 2017, antes vs después)

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

# PALETA "MEZCLA" (relanzamiento v2, decidida con Luigi): fondo CAFÉ oscuro premium
# (adiós al azul-slate aburrido) + colores de datos VIVOS. Cálida con identidad.
FONDO = "#1b140d"            # café/espresso oscuro de marca Profesor Gato
TEXTO = "#F5EEE2"            # blanco cálido
TEXTO_2 = "#C9B89B"          # texto secundario cálido
TENUE = "#4a3f2e"            # rejilla/ejes tenues (cálidos)

# Colores de datos VIVOS sobre el café: dorado, teal, coral, violeta, lima.
# SERIES[0]=dorado (base/barras), SERIES[1]=teal (la RESALTADA); resto en multi-serie.
SERIES = ["#F2C56A", "#3FD3C2", "#FF6B5E", "#9B8CFF", "#B6E05A"]
APAGADO = "#5a4e3a"          # barras no resaltadas (café medio)
OTROS = "#6b5d45"            # el pliegue "Otros" (café claro)

FPS = 30
DUR_ENTRADA = 1.25           # segundos de animación
DUR_HOLD = 1.6               # segundos quieto al final


def _rgbf(hx: str):
    hx = hx.lstrip("#")
    return [int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4)]


# Colores del DEGRADADO del fondo (los cambia aplicar_tema según el tema del canal).
_LUZ = "#392b19"   # luz (arriba-izquierda)
_OSC = "#0e0a06"   # oscuro (abajo-derecha)


def pintar_fondo_gradiente(fig, c_luz: str = None, c_osc: str = None,
                           luz=(0.17, 0.14)):
    """Fondo con LUZ que entra de arriba-izquierda y se difumina a oscuro (profundidad
    premium). Usa los colores del TEMA activo (_LUZ/_OSC) si no se pasan. Devuelve el ax."""
    c_luz = c_luz or _LUZ
    c_osc = c_osc or _OSC
    H2, W2 = 240, 426          # baja resolución; imshow lo escala suave (rápido)
    yy, xx = np.mgrid[0:H2, 0:W2].astype(float)
    xn, yn = xx / W2, yy / H2
    d = np.sqrt((xn - luz[0]) ** 2 + (yn - luz[1]) ** 2)
    d /= d.max()
    t = np.clip(d ** 0.85, 0, 1)[..., None]
    a = np.array(_rgbf(c_luz)); b = np.array(_rgbf(c_osc))
    img = a * (1 - t) + b * t
    axb = fig.add_axes([0, 0, 1, 1], zorder=-100)
    axb.axis("off")
    axb.imshow(img, extent=[0, 1, 0, 1], aspect="auto", interpolation="bilinear")
    return axb


def _ease(t: float) -> float:
    """Ease-out cúbico. Entra rápido, se asienta. Sin rebote."""
    return 1 - (1 - t) ** 3


def _fmt(v: float, unidad: str = "", decimales: int | None = None) -> str:
    """
    `decimales` fuerza el formato. Importa para cosas como la magnitud de un
    sismo: 7.0 se escribe "7,0", nunca "7" — en esa escala el decimal es el
    dato, no un adorno.
    """
    if decimales is not None:
        s = f"{v:,.{decimales}f}".replace(",", " ").replace(".", ",")
    elif abs(v) >= 1000:
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


def _dibujar_comparacion(ax, spec, p, W, H):
    """
    Dos casos enfrentados. Para "Chile vs Haití", "1985 vs 2017", etc.

    Cada lado lleva su nombre y hasta tres cifras que suben contando. La
    cifra marcada como `clave` va en grande; las otras, de apoyo.

    Deliberadamente NO usa dos ejes ni barras comparadas: cuando las
    magnitudes son de órdenes distintos (8.8 contra 200,000) cualquier
    escala común miente. Aquí el contraste lo hace el número, no el largo.
    """
    izq, der = spec["datos"][0], spec["datos"][1]
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    e = _ease(p)

    # separador central
    ax.plot([0.5, 0.5], [0.06, 0.92], color=TENUE, linewidth=1.6, zorder=1)

    for lado, (caso, cx, color) in enumerate(
            ((izq, 0.25, SERIES[0]), (der, 0.75, SERIES[1]))):

        retraso = lado * 0.10
        pl = np.clip((p - retraso) / max(1e-6, 1 - retraso), 0, 1)
        el = _ease(pl)

        ax.text(cx, 0.90, caso["nombre"].upper(), ha="center", va="center",
                color=TEXTO, fontsize=34, fontweight="black")

        cifras = caso["cifras"]
        clave = caso.get("clave", len(cifras) - 1)

        y = 0.66
        for i, c in enumerate(cifras):
            val = float(c["valor"]) * el
            grande = (i == clave)

            ax.text(cx, y, _fmt(val, c.get("unidad", ""), c.get("decimales")),
                    ha="center", va="center",
                    color=color if grande else TEXTO,
                    fontsize=76 if grande else 40,
                    fontweight="black")
            ax.text(cx, y - (0.095 if grande else 0.070),
                    c["etiqueta"].upper(), ha="center", va="center",
                    color=TEXTO_2, fontsize=19, fontweight="bold")

            y -= 0.26 if grande else 0.20

    if spec.get("remate") and e > 0.75:
        ax.text(0.5, 0.115, spec["remate"], ha="center", va="center",
                color=TEXTO, fontsize=27, fontweight="bold")


FORMAS = {
    "numero": _dibujar_numero,
    "barras": _dibujar_barras,
    "linea": _dibujar_linea,
    "reparto": _dibujar_reparto,
    "comparacion": _dibujar_comparacion,
}


# ── TEMAS DE COLOR ────────────────────────────────────────────────────
# El color base VARÍA según el tema del video, pero la IDENTIDAD se mantiene:
# dorado (#F2C56A = series[0] siempre), luz cálida degradada, monedas, layout.

def _h2rgb(hx):
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


_ORO = "#F2C56A"   # dorado de marca (constante en todos los temas)

TEMAS = {
    # historia / cultura
    "cafe": dict(luz="#392b19", osc="#0e0a06", fondo="#1b140d", texto="#F5EEE2",
                 texto2="#C9B89B", tenue="#4a3f2e", apagado="#5a4e3a", otros="#6b5d45",
                 map_otros="#3a3022",
                 series=[_ORO, "#3FD3C2", "#FF6B5E", "#9B8CFF", "#B6E05A"]),
    # el de la referencia (gris/negro + amarillo)
    "negro_oro": dict(luz="#2d2a20", osc="#070707", fondo="#121212", texto="#F3EFE4",
                      texto2="#B8B4A6", tenue="#34312a", apagado="#3a382f", otros="#4a473e",
                      map_otros="#2a2a2a",
                      series=[_ORO, "#FFB23E", "#E8D58A", "#7FB8C9", "#D98C6A"]),
    # ciencia / espacio / misterio
    "azul_noche": dict(luz="#172a46", osc="#060912", fondo="#0c1526", texto="#EAF0FA",
                       texto2="#9FB0C8", tenue="#2a3952", apagado="#2c3a50", otros="#3a4a64",
                       map_otros="#22324a",
                       series=[_ORO, "#4FD6E8", "#7CA3FF", "#C77DFF", "#5AE0A0"]),
    # naturaleza / animales
    "verde_bosque": dict(luz="#1b3522", osc="#060f08", fondo="#0e1c12", texto="#EAF5EC",
                         texto2="#A6C2AC", tenue="#2a4432", apagado="#2c4634", otros="#3a5a44",
                         map_otros="#22402c",
                         series=[_ORO, "#5BE08A", "#FFB23E", "#4FD6E8", "#FF6B5E"]),
    # política / poder / drama
    "vino": dict(luz="#3d1a27", osc="#10060a", fondo="#22101a", texto="#F7E9EE",
                 texto2="#C9A6B2", tenue="#4a2634", apagado="#4a2a36", otros="#5a3444",
                 map_otros="#3a2230",
                 series=[_ORO, "#FF6B8A", "#FFB23E", "#C77DFF", "#5AE0A0"]),
}


def aplicar_tema(nombre: str = "cafe"):
    """Cambia la paleta del canal al tema dado (en graficas, mapas y estáticas),
    manteniendo el dorado y la luz. Devuelve el nombre aplicado."""
    import sys
    t = TEMAS.get(nombre, TEMAS["cafe"])
    objetivos = [sys.modules[__name__]]
    for mn in ("modules.graficas_extra", "graficas_extra"):
        if mn in sys.modules:
            objetivos.append(sys.modules[mn]); break
    for m in objetivos:
        m.FONDO, m.TEXTO, m.TEXTO_2, m.TENUE = t["fondo"], t["texto"], t["texto2"], t["tenue"]
        m.SERIES, m.APAGADO, m.OTROS = list(t["series"]), t["apagado"], t["otros"]
        m._LUZ, m._OSC = t["luz"], t["osc"]
        if hasattr(m, "SERIES_TODOS_PARES"):
            m.SERIES_TODOS_PARES = list(t["series"])[:3]
    for mn in ("modules.mapa", "mapa"):
        if mn in sys.modules:
            mp = sys.modules[mn]
            mp._BG, mp._BORDE, mp._OTROS = t["osc"], t["osc"], t["map_otros"]
            break
    for mn in ("modules.data_chart", "data_chart"):
        if mn in sys.modules:
            dc = sys.modules[mn]
            dc.BG, dc.BG_BANDA = _h2rgb(t["osc"]), _h2rgb(t["fondo"])
            dc.INK, dc.INK_SOFT, dc.TRACK = _h2rgb(t["texto"]), _h2rgb(t["texto2"]), _h2rgb(t["map_otros"])
            break
    return nombre


# ── render ───────────────────────────────────────────────────────────

def render_grafica(spec: dict, salida: str, vertical: bool = False) -> str:
    aplicar_tema(spec.get("tema", "cafe"))   # el spec puede elegir el tema del video
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

    # Formas de graficas_extra que ocupan el lienzo completo (pictograma, dona).
    # Import perezoso y tolerante: si graficas_extra no está, el set queda vacío
    # y todo se comporta como antes.
    try:
        from graficas_extra import PANTALLA_COMPLETA
    except ImportError:
        try:
            from modules.graficas_extra import PANTALLA_COMPLETA
        except ImportError:
            PANTALLA_COMPLETA = set()

    for f in range(total):
        p = 1.0 if f >= n_entrada else f / max(1, n_entrada - 1)
        fig.clear()
        fig.patch.set_facecolor(FONDO)
        pintar_fondo_gradiente(fig)   # luz cálida arriba-izq (profundidad premium)

        if forma in ("numero", "comparacion") or forma in PANTALLA_COMPLETA:
            ax = fig.add_axes([0.03, 0.10, 0.94, 0.78]
                              if forma in PANTALLA_COMPLETA else [0, 0, 1, 1])
        else:
            izq = 0.30 if forma == "barras" else 0.11
            ax = fig.add_axes([izq, 0.20, 0.94 - izq, 0.56])

        if spec.get("titulo") and forma not in ("numero", "comparacion"):
            fig.text(0.5, 0.88, spec["titulo"], ha="center", va="center",
                     color=TEXTO, fontsize=38, fontweight="black", wrap=True)

        dibujar(ax, spec, p, W, H)
        ax.patch.set_facecolor("none")   # deja ver el degradado del fondo

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
