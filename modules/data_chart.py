"""
data_chart.py — Gráficas de datos VERIFICADOS como fondo 16:9 (Profesor Gato)

Renderiza una infografía limpia (barras horizontales) con PIL — SIN matplotlib.
Identidad del canal: fondo slate oscuro, barras y acentos DORADOS, texto claro.

Por qué esto existe: en el ensayo, cuando el guion dice "los millones del Mundial",
no basta el fondo pixel-art ni una tarjeta con una sola cifra: hace falta una GRÁFICA
que compare los números reales y "explique todo". El personaje (Gato/Bastet) se
superpone en el assembler en la esquina inferior derecha, por eso el contenido de la
gráfica vive en el ~62% IZQUIERDO y deja aire a la derecha/abajo (char + subtítulos).

REGLA DURA: solo debe recibir cifras que salieron de la ficha verificada. Este módulo
NO inventa números; solo dibuja los que le pasan.

Spec:
  {
    "titulo": "Quién se queda con el dinero del Mundial",
    "unidad": "millones de USD",                 # opcional, se muestra bajo el título
    "series": [
       {"label": "Ingresos FIFA", "valor": 7500, "valor_txt": "$7,500 M", "resaltar": true},
       {"label": "Derrama prometida a la sede", "valor": 3000},
       ...
    ],
    "fuente": "FIFA, informe financiero 2022",
    "tipo": "barras"                             # opcional (barras horizontales por defecto)
  }
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("data_chart")

W, H = 1920, 1080

# ── Identidad visual del canal ────────────────────────────────────────────────
BG        = (17, 21, 30)       # slate oscuro
BG_BANDA  = (24, 30, 42)       # banda superior del título
GOLD      = (242, 197, 106)    # dorado de marca (igual al del assembler)
GOLD_SOFT = (150, 124, 74)     # dorado apagado (barras no resaltadas)
INK       = (238, 240, 245)    # texto principal
INK_SOFT  = (150, 158, 172)    # texto secundario / fuente
TRACK     = (34, 40, 54)       # riel de fondo de cada barra

# Zona segura: el personaje ocupa la esquina inf. der. (~470px de ancho anclado abajo)
# y los subtítulos van abajo-centro. Dejamos margen a la derecha y abajo.
MARGIN_L   = 96
CONTENT_R  = 1200              # las barras no pasan de aquí (aire para el personaje)
TOP        = 60

_FONT_CANDIDATES_BOLD = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_CANDIDATES_REG = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, bold: bool = False):
    for path in (_FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REG):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fmt_num(v) -> str:
    """Formatea un número con separadores de miles; deja enteros como enteros."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return f"{int(f):,}".replace(",", ",")
    return f"{f:,.1f}"


def _wrap(draw, text, font, max_w):
    """Parte `text` en líneas que caben en `max_w` px."""
    palabras = str(text).split()
    lineas, actual = [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if draw.textlength(prueba, font=font) <= max_w or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def render_chart(spec: dict, output_path) -> str:
    """Renderiza la gráfica a un PNG 16:9 y devuelve la ruta (str).

    Nunca lanza por datos raros: si la serie viene vacía/rota, dibuja igual el
    título y una nota — el pipeline decide el fallback antes de llamar aquí.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    titulo = (spec.get("titulo") or "").strip()
    unidad = (spec.get("unidad") or "").strip()
    fuente = (spec.get("fuente") or "").strip()
    series = [s for s in (spec.get("series") or []) if isinstance(s, dict)]

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Banda superior + título
    f_titulo = _font(64, bold=True)
    f_unidad = _font(34, bold=False)
    banda_h = 190 if unidad else 150
    d.rectangle([0, 0, W, banda_h], fill=BG_BANDA)
    d.rectangle([0, banda_h, W, banda_h + 5], fill=GOLD)   # filo dorado

    ty = TOP
    for i, linea in enumerate(_wrap(d, titulo, f_titulo, W - MARGIN_L - 340)[:2]):
        d.text((MARGIN_L, ty), linea, font=f_titulo, fill=INK)
        ty += 70
    if unidad:
        d.text((MARGIN_L, banda_h - 46), f"en {unidad}", font=f_unidad, fill=GOLD)

    # Barras horizontales
    f_label = _font(38, bold=True)
    f_valor = _font(44, bold=True)

    if series:
        valores = []
        for s in series:
            try:
                valores.append(abs(float(s.get("valor", 0))))
            except (TypeError, ValueError):
                valores.append(0.0)
        vmax = max(valores) or 1.0

        top_barras = banda_h + 70
        bottom_barras = H - 130                     # deja el pie de fuente / subtítulos
        n = len(series)
        gap = 34
        alto_fila = (bottom_barras - top_barras - gap * (n - 1)) / n
        alto_fila = max(72, min(alto_fila, 150))
        bar_h = min(alto_fila - 46, 70)             # la barra, más chica que la fila (deja el label arriba)
        riel_x0 = MARGIN_L
        riel_x1 = CONTENT_R
        riel_w = riel_x1 - riel_x0

        y = top_barras
        for s, v in zip(series, valores):
            label = str(s.get("label", "")).strip()
            resaltar = bool(s.get("resaltar"))
            valor_txt = str(s.get("valor_txt") or _fmt_num(s.get("valor", "")))
            color = GOLD if resaltar else GOLD_SOFT

            # Etiqueta arriba de la barra
            d.text((riel_x0, y), label[:60], font=f_label, fill=INK if resaltar else INK_SOFT)
            by = y + 44
            # Riel + barra
            d.rounded_rectangle([riel_x0, by, riel_x1, by + bar_h], radius=8, fill=TRACK)
            w = int(riel_w * (v / vmax))
            if w > 0:
                d.rounded_rectangle([riel_x0, by, riel_x0 + max(w, 12), by + bar_h],
                                    radius=8, fill=color)
            # Valor al final de la barra (o justo afuera si la barra es corta)
            tw = d.textlength(valor_txt, font=f_valor)
            vx = riel_x0 + w - tw - 18
            vfill = (17, 21, 30)
            if vx < riel_x0 + 20:                     # barra muy corta: valor por fuera
                vx = riel_x0 + w + 18
                vfill = INK
            d.text((vx, by + (bar_h - 44) / 2), valor_txt, font=f_valor, fill=vfill)

            y += alto_fila + gap
    else:
        d.text((MARGIN_L, banda_h + 90), "(sin datos para graficar)",
               font=_font(40), fill=INK_SOFT)

    # Pie de fuente (obligatorio: es dato verificado)
    if fuente:
        f_fuente = _font(28)
        d.text((MARGIN_L, H - 58), f"Fuente: {fuente}", font=f_fuente, fill=INK_SOFT)

    img.save(output_path, "PNG")
    log.info(f"  Gráfica renderizada: {output_path.name} ({len(series)} barras)")
    return str(output_path)


if __name__ == "__main__":
    import tempfile, os
    demo = {
        "titulo": "Quién se queda con el dinero del Mundial 2022",
        "unidad": "millones de dólares",
        "series": [
            {"label": "Ingresos totales de la FIFA", "valor": 7500, "valor_txt": "$7,500 M", "resaltar": True},
            {"label": "Premios repartidos a selecciones", "valor": 440, "valor_txt": "$440 M"},
            {"label": "Costo de estadios (Qatar)", "valor": 6500, "valor_txt": "$6,500 M"},
            {"label": "Derrama real vs. prometida a la sede", "valor": 1200, "valor_txt": "≈ $1,200 M"},
        ],
        "fuente": "FIFA, informe financiero 2022",
    }
    out = os.path.join(tempfile.gettempdir(), "demo_chart.png")
    render_chart(demo, out)
    print("OK ->", out)
