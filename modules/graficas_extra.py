#!/usr/bin/env python3
"""
graficas_extra.py — Formas adicionales para graficas_animadas.py

Se registran solas al importar. En el pipeline basta con:

    import graficas_extra          # noqa: F401  (registra las formas)
    from graficas_animadas import render_grafica

Formas que agrega:

    pictograma  → 100 figuras, N resaltadas. Para proporciones humanas:
                  "3 de cada 5 viviendas", "52% de los edificios".
                  Es la más potente cuando el dato son PERSONAS o casas.
    dispersion  → nube de puntos con burbujas de tamaño variable.
                  Dos variables + una tercera en el área. Estilo Gapminder.
    cascada     → de dónde sale y a dónde se va un total, paso a paso.
                  El caballo de batalla de la economía.
    dona        → UNA proporción sobre el total. Ver la nota de abajo.

────────────────────────────────────────────────────────────────────
SOBRE EL PASTEL — léelo antes de pedirlo

El pastel de varias rebanadas es malo y no es opinión: el ojo humano
compara ángulos mucho peor que longitudes. Con 5 rebanadas parecidas,
nadie puede ordenarlas de memoria, y el espectador de video tiene 3
segundos, no 30.

Pero hay UN caso donde la forma circular sí funciona: **cuando hay una
sola comparación**, o sea una parte contra su todo ("58% de esto"). Ahí
no hay que ordenar nada, solo leer una fracción, y el círculo la comunica
bien e incluso mejor que una barra suelta.

Por eso `dona` acepta una sola cifra (o dos, parte y resto) y se niega a
más. No es capricho: con 3 o más, usa `reparto`, que dice exactamente lo
mismo y sí se lee.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Wedge, Rectangle

# Import robusto: SIEMPRE debe resolver al MISMO módulo que ve render_grafica
# (si no, FORMAS serían dos dicts distintos y las formas nuevas no se registran
# donde el pipeline las busca). En el pipeline se importa como
# `modules.graficas_animadas`; en uso suelto/CLI, como `graficas_animadas`.
try:
    from modules.graficas_animadas import (
        FORMAS, SERIES, APAGADO, OTROS, FONDO, TEXTO, TEXTO_2, TENUE,
        _ease, _fmt,
    )
except ImportError:
    from graficas_animadas import (
        FORMAS, SERIES, APAGADO, OTROS, FONDO, TEXTO, TEXTO_2, TENUE,
        _ease, _fmt,
    )

# Para nube de puntos el ojo compara TODOS los pares entre sí, no solo los
# vecinos. En ese modo la paleta solo valida hasta 3 series. Con más, se
# pliega a "Otros" o se hacen gráficas separadas.
SERIES_TODOS_PARES = SERIES[:3]


# ── PICTOGRAMA ───────────────────────────────────────────────────────

def _silueta(ax, cx, cy, s, color, alpha=1.0):
    """Figura humana simplificada. Cabeza + cuerpo, legible a 20 px."""
    ax.add_patch(Circle((cx, cy + s * 0.72), s * 0.26,
                        facecolor=color, edgecolor="none", alpha=alpha, zorder=3))
    cuerpo = plt.Polygon([
        (cx - s * 0.40, cy - s * 0.75),
        (cx - s * 0.40, cy + s * 0.20),
        (cx - s * 0.16, cy + s * 0.40),
        (cx + s * 0.16, cy + s * 0.40),
        (cx + s * 0.40, cy + s * 0.20),
        (cx + s * 0.40, cy - s * 0.75),
        (cx + s * 0.13, cy - s * 0.75),
        (cx + s * 0.13, cy - s * 0.10),
        (cx - s * 0.13, cy - s * 0.10),
        (cx - s * 0.13, cy - s * 0.75),
    ], closed=True, facecolor=color, edgecolor="none", alpha=alpha, zorder=3)
    ax.add_patch(cuerpo)


def _dibujar_pictograma(ax, spec, p, W, H):
    """
    N de cada M. `datos` = {"parte": 3, "total": 5} o {"parte": 52, "total": 100}.
    """
    d = spec["datos"]
    parte = float(d["parte"])
    total = int(d.get("total", 100))
    frac = parte / total

    cols = int(d.get("columnas", 10 if total > 20 else total))
    filas = int(np.ceil(total / cols))

    ax.axis("off")
    ax.set_xlim(-0.6, cols - 0.4)
    ax.set_ylim(-1.15, filas + 0.15)
    ax.set_aspect("equal")

    e = _ease(p)
    encendidas = frac * total * e

    # OJO: el eje NO se invierte. Se calcula la fila al derecho y se llena
    # de arriba hacia abajo a mano. Invertir el eje voltea las siluetas.
    for i in range(total):
        f, c = divmod(i, cols)
        y = (filas - 1) - f
        prendida = i < encendidas
        color = SERIES[1] if prendida else APAGADO
        alpha = 1.0 if prendida else 0.55
        _silueta(ax, c, y, 0.42, color, alpha)

    if e > 0.55:
        etiqueta = d.get("etiqueta", f"{_fmt(parte)} de cada {total}")
        ax.text((cols - 1) / 2, -0.95, etiqueta, ha="center", va="center",
                color=SERIES[1], fontsize=34, fontweight="black")


# ── DISPERSIÓN / BURBUJAS ────────────────────────────────────────────

def _dibujar_dispersion(ax, spec, p, W, H):
    """
    datos = [{"x":.., "y":.., "tam":.., "nombre":"..", "grupo":0}, ...]

    `tam` es opcional; si está, el ÁREA del punto es proporcional a él
    (nunca el radio: el área es lo que el ojo lee como cantidad).
    """
    puntos = spec["datos"]
    ax.set_facecolor(FONDO)

    for k, lado in ax.spines.items():
        lado.set_visible(k in ("bottom", "left"))
        lado.set_color(TENUE)
        lado.set_linewidth(1.2)

    ax.grid(color=TENUE, linewidth=0.7, alpha=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TEXTO_2, labelsize=18, length=0)

    xs = np.array([float(q["x"]) for q in puntos])
    ys = np.array([float(q["y"]) for q in puntos])

    log_x = bool(spec.get("log_x"))
    # Cuando un punto es 100 veces los demás (Haití entre países), la escala
    # lineal aplasta todo contra el eje y la gráfica deja de decir nada.
    log_y = bool(spec.get("log_y"))

    # La escala se fija ANTES que los límites. Al revés, matplotlib recibe
    # un límite inferior negativo y en log lo descarta: todos los puntos
    # terminan aplastados arriba.
    if log_x:
        ax.set_xscale("log")
    if log_y:
        ax.set_yscale("log")

    if log_x:
        ax.set_xlim(max(xs.min() / 2.2, 1e-9), xs.max() * 2.2)
    else:
        mx = (xs.max() - xs.min()) or 1
        ax.set_xlim(xs.min() - mx * 0.16, xs.max() + mx * 0.16)

    if log_y:
        ax.set_ylim(max(ys.min() / 3.5, 1e-9), ys.max() * 3.5)
    else:
        my = (ys.max() - ys.min()) or 1
        ax.set_ylim(ys.min() - my * 0.20, ys.max() + my * 0.22)

    if spec.get("eje_x"):
        ax.set_xlabel(spec["eje_x"] + ("  (escala logarítmica)" if log_x else ""),
                      color=TEXTO_2, fontsize=20, fontweight="bold", labelpad=12)
    if spec.get("eje_y"):
        # Avisar la escala log es obligatorio: si no, la gráfica miente.
        ax.set_ylabel(spec["eje_y"] + ("  (escala logarítmica)" if log_y else ""),
                      color=TEXTO_2, fontsize=20, fontweight="bold", labelpad=12)

    tams = [float(q.get("tam", 1)) for q in puntos]
    tmax = max(tams) or 1

    # Banderas: si el punto trae "iso" o un "nombre" de país, ponemos la BANDERA en vez
    # de la burbuja (mucho más vivo que un círculo de color). Import tolerante.
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    import matplotlib.image as mpimg
    try:
        from modules.banderas import bandera_circular as bandera
    except ImportError:
        try:
            from banderas import bandera_circular as bandera
        except ImportError:
            bandera = lambda *a, **k: None

    for i, q in enumerate(puntos):
        retraso = (i % 5) * 0.05
        pi = np.clip((p - retraso) / max(1e-6, 1 - retraso), 0, 1)
        ei = _ease(pi)

        g = int(q.get("grupo", 0))
        color = SERIES_TODOS_PARES[g % len(SERIES_TODOS_PARES)]
        area = 260 + 5200 * (tams[i] / tmax)   # área ∝ dato, no radio

        flag = None
        label_dy = 26          # cuánto sube la etiqueta (se ajusta a la bandera)
        if ei > 0.35:
            try:
                flag = bandera(q.get("iso") or q.get("nombre", ""))
            except Exception:
                flag = None

        if flag:
            try:
                img = mpimg.imread(str(flag))   # badge circular (ya trae aro + glow)
                zoom = max(0.08, (0.30 + 0.40 * (tams[i] / tmax)) * ei)
                oi = OffsetImage(img, zoom=zoom)
                ab = AnnotationBbox(oi, (q["x"], q["y"]), frameon=False, zorder=3)
                ax.add_artist(ab)
                # la etiqueta queda ARRIBA de la moneda (alto en puntos ≈ px*zoom)
                label_dy = int(12 + (img.shape[0] * zoom) / 2)
            except Exception:
                flag = None

        if not flag:   # respaldo: burbuja de color
            ax.scatter([q["x"]], [q["y"]], s=area * ei,
                       facecolor=color, alpha=0.72,
                       edgecolor=FONDO, linewidth=2.5, zorder=3)

        # etiqueta directa (en video no hay leyenda que valga)
        if q.get("nombre") and ei > 0.6:
            ax.annotate(q["nombre"], (q["x"], q["y"]),
                        textcoords="offset points", xytext=(0, label_dy),
                        ha="center", color=TEXTO, fontsize=19,
                        fontweight="bold", zorder=4)


# ── CASCADA ──────────────────────────────────────────────────────────

def _dibujar_cascada(ax, spec, p, W, H):
    """
    datos = [("Ingreso", 100), ("Insumos", -32), ("Sueldos", -28), ...]
    El último puede ser ("Queda", None) para que lo calcule solo.
    """
    datos = list(spec["datos"])
    unidad = spec.get("unidad", "")

    etiquetas, valores = [], []
    for et, v in datos:
        etiquetas.append(et)
        valores.append(v)

    if valores[-1] is None:
        valores[-1] = sum(v for v in valores[:-1] if v is not None)

    ax.set_facecolor(FONDO)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_yticks([])
    ax.tick_params(colors=TEXTO_2, labelsize=19, length=0)

    n = len(valores)
    acumulado, bases, altos = 0.0, [], []
    for i, v in enumerate(valores):
        if i == 0 or i == n - 1:
            bases.append(0.0)
            altos.append(v)
            acumulado = v if i == 0 else acumulado
        else:
            base = acumulado + min(v, 0)
            bases.append(base)
            altos.append(abs(v))
            acumulado += v

    techo = max(max(np.array(bases) + np.array(altos)), 0) * 1.28
    ax.set_ylim(0, techo)
    ax.set_xlim(-0.7, n - 0.3)

    e = _ease(p)
    for i in range(n):
        retraso = i * (0.75 / max(n, 1))
        pi = np.clip((p - retraso) / max(1e-6, 1 - retraso), 0, 1)
        ei = _ease(pi)

        if i == 0:
            color = SERIES[0]
        elif i == n - 1:
            color = SERIES[2]
        else:
            color = SERIES[1] if valores[i] < 0 else SERIES[2]

        alto = altos[i] * ei
        if alto > 0:
            ax.add_patch(Rectangle((i - 0.34, bases[i]), 0.68, alto,
                                   facecolor=color, linewidth=0, zorder=3))
        if ei > 0.3:
            signo = "" if i in (0, n - 1) else ("+" if valores[i] > 0 else "−")
            ax.text(i, bases[i] + alto + techo * 0.028,
                    f"{signo}{_fmt(abs(valores[i]), unidad)}",
                    ha="center", va="bottom", color=color,
                    fontsize=25, fontweight="black", zorder=4)
        # línea guía al siguiente escalón
        if 0 < i < n - 1 and ei > 0.85:
            ax.plot([i - 0.34, i - 0.66],
                    [bases[i] + (alto if valores[i] > 0 else 0)] * 2,
                    color=TENUE, linewidth=1.2, zorder=2)

    ax.set_xticks(range(n))
    ax.set_xticklabels(etiquetas, fontsize=19, fontweight="bold")
    for t in ax.get_xticklabels():
        t.set_color(TEXTO_2)


# ── DONA (una sola proporción) ───────────────────────────────────────

def _dibujar_dona(ax, spec, p, W, H):
    d = spec["datos"]
    if isinstance(d, dict):
        parte = float(d["parte"])
        total = float(d.get("total", 100))
        etiqueta = d.get("etiqueta", "")
    else:
        raise ValueError(
            "dona espera {'parte': .., 'total': .., 'etiqueta': '..'}. "
            "Para 3 o más categorías usa la forma 'reparto': el ojo compara "
            "ángulos mucho peor que longitudes."
        )

    frac = parte / total
    ax.axis("off")
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.25, 1.45)
    ax.set_aspect("equal")

    e = _ease(p)
    r_ext, r_int = 1.0, 0.66

    ax.add_patch(Wedge((0, 0), r_ext, 0, 360, width=r_ext - r_int,
                       facecolor=APAGADO, linewidth=0, zorder=2))
    if frac * e > 0.001:
        ax.add_patch(Wedge((0, 0), r_ext, 90 - 360 * frac * e, 90,
                           width=r_ext - r_int,
                           facecolor=SERIES[1], linewidth=0, zorder=3))

    ax.text(0, 0.02, _fmt(parte * e, spec.get("unidad", "%")),
            ha="center", va="center", color=TEXTO,
            fontsize=72, fontweight="black", zorder=4)

    if etiqueta:
        ax.text(0, -1.12, etiqueta, ha="center", va="center",
                color=TEXTO_2, fontsize=25, fontweight="bold")


# ── MAPA DE CALOR (heatmap) ──────────────────────────────────────────
def _dibujar_calor(ax, spec, p, W, H):
    """
    Matriz de intensidad con la paleta del canal (slate → dorado).
    spec = {"filas":["A","B"..], "columnas":["X","Y"..],
            "valores":[[..],[..]], "unidad":"", "titulo":"", "fuente":""}
    Para comparar DOS dimensiones a la vez (ej. países × décadas).
    """
    from matplotlib.colors import LinearSegmentedColormap
    filas = spec.get("filas", [])
    cols  = spec.get("columnas", [])
    M = np.array(spec["valores"], dtype=float)
    ax.set_facecolor(FONDO)

    cmap = LinearSegmentedColormap.from_list(
        "gato_calor", ["#1a2230", "#3b3a33", APAGADO, SERIES[0], SERIES[1]])
    vmin, vmax = float(np.nanmin(M)), float(np.nanmax(M))
    im = ax.imshow(M, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)
    im.set_alpha(_ease(p))  # entra con un fundido suave

    ax.set_xticks(range(len(cols)));  ax.set_xticklabels(cols,  color=TEXTO_2, fontsize=20)
    ax.set_yticks(range(len(filas))); ax.set_yticklabels(filas, color=TEXTO_2, fontsize=20)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)

    if p > 0.45:  # los números entran cuando ya se ven las celdas
        umbral = vmin + (vmax - vmin) * 0.62
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M[i, j]
                ax.text(j, i, _fmt(v, spec.get("unidad", "")), ha="center", va="center",
                        color=("#11151e" if v >= umbral else TEXTO),
                        fontsize=19, fontweight="bold", alpha=_ease(min(1.0, (p - 0.45) / 0.4)))


FORMAS.update({
    "pictograma": _dibujar_pictograma,
    "dispersion": _dibujar_dispersion,
    "cascada": _dibujar_cascada,
    "dona": _dibujar_dona,
    "calor": _dibujar_calor,
})

# Estas ocupan todo el lienzo (sin ejes a la izquierda; el título va arriba).
# El heatmap NO va aquí: necesita margen izquierdo para las etiquetas de fila.
PANTALLA_COMPLETA = {"pictograma", "dona"}
