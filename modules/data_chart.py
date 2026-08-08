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


def _cover(im: "Image.Image", tw: int, th: int) -> "Image.Image":
    """Redimensiona tipo CSS 'cover' (llena tw×th recortando el excedente centrado)."""
    w, h = im.size
    escala = max(tw / w, th / h)
    im = im.resize((max(int(w * escala), tw), max(int(h * escala), th)))
    x = (im.width - tw) // 2
    y = (im.height - th) // 2
    return im.crop((x, y, x + tw, y + th))


def _base_canvas(spec: dict):
    """Devuelve (canvas_RGBA, usa_fondo). Si el spec trae 'fondo' (imagen situacional
    de Imagen), la usa oscurecida como base; si no, el slate plano de siempre."""
    fondo = (spec.get("fondo") or "").strip()
    if fondo and Path(fondo).exists():
        try:
            base = _cover(Image.open(fondo).convert("RGB"), W, H)
            # Oscurecer hacia el slate de marca para que el dato mande sobre la foto.
            base = Image.blend(base, Image.new("RGB", (W, H), BG), 0.55)
            img = base.convert("RGBA")
            # Panel/scrim a la izquierda (zona de la gráfica) para contraste del texto.
            scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ds = ImageDraw.Draw(scrim)
            ds.rectangle([0, 0, CONTENT_R + 150, H], fill=(*BG, 165))
            return Image.alpha_composite(img, scrim), True
        except Exception as e:
            log.warning(f"  [data_chart] fondo situacional falló ({e}); uso slate plano")
    return Image.new("RGBA", (W, H), (*BG, 255)), False


def render_chart(spec: dict, output_path) -> str:
    """Renderiza la gráfica a un PNG 16:9 y devuelve la ruta (str).

    Nunca lanza por datos raros: si la serie viene vacía/rota, dibuja igual el
    título y una nota — el pipeline decide el fallback antes de llamar aquí.

    Fondo situacional: si spec['fondo'] apunta a una imagen (pixel-art de Imagen del
    tema real), se usa oscurecida como base y los datos REALES se dibujan encima.
    """
    if spec.get("forma") == "torta":
        return _render_pie(spec, output_path)
    if spec.get("estilo") == "poster":
        return _render_poster(spec, output_path)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    titulo = (spec.get("titulo") or "").strip()
    unidad = (spec.get("unidad") or "").strip()
    fuente = (spec.get("fuente") or "").strip()
    series = [s for s in (spec.get("series") or []) if isinstance(s, dict)]

    img, _usa_fondo = _base_canvas(spec)
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

    img.convert("RGB").save(output_path, "PNG")
    log.info(f"  Gráfica renderizada: {output_path.name} ({len(series)} barras)")
    return str(output_path)


# ══════════════════════════════════════════════════════════════════════════════
#  ESTILO "POSTER" — barras VERTICALES temáticas (look de la referencia de Luigi:
#  fondo situacional + barras bicolor + rejilla con eje Y + topes + título grueso).
#  El personaje lo pone el assembler abajo-derecha, por eso las barras van a la izq.
# ══════════════════════════════════════════════════════════════════════════════
CREMA = (245, 230, 200)
GRID  = (140, 148, 164)

# Paletas de acento para las BARRAS (el título/marco siguen dorados = marca). Se elige
# una determinista por título → cada gráfica varía, pero la misma gráfica es estable.
# Evita que "todas las gráficas se vean iguales".
_PALETAS = [
    {"hi_top": (255, 214, 130), "hi_bot": (122, 88, 52),  "top": GOLD,            "bot": (78, 58, 36),  "mark": GOLD},            # dorado
    {"hi_top": (120, 230, 220), "hi_bot": (40, 110, 110), "top": (90, 190, 185),  "bot": (30, 80, 80),  "mark": (120, 230, 220)}, # teal
    {"hi_top": (255, 150, 130), "hi_bot": (140, 60, 50),  "top": (220, 110, 95),  "bot": (100, 45, 38), "mark": (255, 150, 130)}, # coral
    {"hi_top": (160, 225, 140), "hi_bot": (70, 120, 55),  "top": (120, 185, 100), "bot": (55, 90, 42),  "mark": (160, 225, 140)}, # verde
    {"hi_top": (200, 160, 255), "hi_bot": (95, 65, 150),  "top": (160, 125, 215), "bot": (70, 50, 110), "mark": (200, 160, 255)}, # violeta
]


def _paleta_de(titulo: str) -> dict:
    import hashlib
    h = int(hashlib.md5((titulo or "chart").encode("utf-8")).hexdigest(), 16)
    return _PALETAS[h % len(_PALETAS)]

_FONT_HEAVY = [r"C:\Windows\Fonts\impact.ttf", r"C:\Windows\Fonts\ariblk.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _font_heavy(size: int):
    for p in _FONT_HEAVY:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return _font(size, bold=True)


def _dashed_h(d, x0, x1, y, fill=GRID, dash=22, gap=16, width=3):
    x = x0
    while x < x1:
        d.line([x, y, min(x + dash, x1), y], fill=fill, width=width)
        x += dash + gap


def _nice_step(vmax: float, target: int = 4) -> float:
    import math
    if vmax <= 0:
        return 1.0
    raw = vmax / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            return m * mag
    return 10 * mag


def _text_out(d, xy, text, font, fill, w=4, anchor=None, outline=(22, 17, 10)):
    x, y = xy
    for dx in range(-w, w + 1):
        for dy in range(-w, w + 1):
            if dx * dx + dy * dy <= w * w:
                d.text((x + dx, y + dy), text, font=font, fill=outline, anchor=anchor)
    d.text((x, y), text, font=font, fill=fill, anchor=anchor)


def _render_poster(spec: dict, output_path) -> str:
    import math
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    titulo = (spec.get("titulo") or "").strip()
    unidad = (spec.get("unidad") or "").strip()
    fuente = (spec.get("fuente") or "").strip()
    series = [s for s in (spec.get("series") or []) if isinstance(s, dict)]

    img, _ = _base_canvas(spec)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD_SOFT, width=7)   # marco cartucho

    # Título centrado, grueso, con contorno
    f_tit = _font_heavy(92)
    ty = 40
    for ln in _wrap(d, titulo.upper(), f_tit, W - 280)[:2]:
        wln = d.textlength(ln, font=f_tit)
        _text_out(d, ((W - wln) / 2, ty), ln, f_tit, CREMA, w=5)
        ty += 100
    if unidad:
        _text_out(d, (W / 2, ty + 2), f"en {unidad}", _font(40, bold=True), GOLD, w=3, anchor="ma")
        ty += 56

    # Área de plot (aire a la derecha para el personaje del assembler)
    PL_X0, PL_X1, base_y = 210, 1380, 905
    top_y = max(ty + 46, 340)
    plot_h = base_y - top_y
    valores = [abs(float(s.get("valor", 0) or 0)) for s in series] or [1.0]
    vmax = max(valores) or 1.0
    step = _nice_step(vmax)
    top_val = math.ceil(vmax / step) * step or step

    # Ejes + rejilla + etiquetas de valor
    d.line([PL_X0, top_y - 24, PL_X0, base_y], fill=CREMA, width=4)
    d.line([PL_X0, base_y, PL_X1 + 26, base_y], fill=CREMA, width=4)
    d.polygon([(PL_X0 - 13, top_y - 22), (PL_X0 + 13, top_y - 22), (PL_X0, top_y - 46)], fill=CREMA)
    f_grid = _font(34, bold=True)
    t = step
    while t <= top_val + 1e-6:
        gy = base_y - (t / top_val) * plot_h
        _dashed_h(d, PL_X0 + 6, PL_X1 + 18, int(gy))
        _text_out(d, (PL_X0 - 20, gy - 20), _fmt_num(t), f_grid, CREMA, w=2, anchor="ra")
        t += step

    # Barras verticales bicolor + tope + valor + etiqueta
    n = len(series)
    slot = (PL_X1 - PL_X0) / max(n, 1)
    bw = min(slot * 0.52, 148)
    f_val = _font_heavy(48)
    f_lab = _font(34, bold=True)
    pal = _paleta_de(titulo)
    for i, s in enumerate(series):
        v = valores[i]
        cx = PL_X0 + slot * (i + 0.5)
        bh = (v / top_val) * plot_h
        x0, x1, y0 = cx - bw / 2, cx + bw / 2, base_y - bh
        hi = bool(s.get("resaltar"))
        top_c = pal["hi_top"] if hi else pal["top"]
        bot_c = pal["hi_bot"] if hi else pal["bot"]
        d.rounded_rectangle([x0, y0, x1, base_y], radius=10, fill=bot_c)
        d.rounded_rectangle([x0, y0, x1, y0 + min(bh * 0.5, plot_h)], radius=10, fill=top_c)
        d.rectangle([x0, y0, x1, base_y], outline=CREMA, width=3)
        r = 15
        d.ellipse([cx - r, y0 - 2 * r - 8, cx + r, y0 - 8], fill=pal["mark"], outline=(60, 44, 24), width=3)
        vtxt = str(s.get("valor_txt") or _fmt_num(s.get("valor", "")))
        _text_out(d, (cx, y0 - 2 * r - 18), vtxt, f_val, CREMA, w=3, anchor="ms")
        _text_out(d, (cx, base_y + 14), str(s.get("label", ""))[:22], f_lab, CREMA, w=2, anchor="ma")

    if fuente:
        _text_out(d, (PL_X0, H - 54), f"Fuente: {fuente}", _font(28), INK_SOFT, w=2)

    img.convert("RGB").save(output_path, "PNG")
    log.info(f"  Gráfica POSTER: {output_path.name} ({n} barras)")
    return str(output_path)


# ── PIE / TORTA (referencia3): rebanadas de colores sobre fondo temático ──────
_PIE_COLORS = [
    (242, 197, 106), (120, 190, 185), (220, 110, 95), (150, 190, 110),
    (170, 140, 215), (235, 170, 90), (110, 170, 220), (230, 130, 160),
]


def _render_pie(spec: dict, output_path) -> str:
    """Gráfica de TORTA sobre fondo temático: rebanadas de colores, % dentro,
    etiqueta afuera. Deja aire a la derecha para el personaje del assembler."""
    import math
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    titulo = (spec.get("titulo") or "").strip()
    fuente = (spec.get("fuente") or "").strip()
    series = [s for s in (spec.get("series") or []) if isinstance(s, dict)]
    vals = [abs(float(s.get("valor", 0) or 0)) for s in series]
    total = sum(vals) or 1.0

    img, _ = _base_canvas(spec)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=GOLD_SOFT, width=7)

    f_tit = _font_heavy(84)
    ty = 40
    for ln in _wrap(d, titulo.upper(), f_tit, W - 220)[:2]:
        wln = d.textlength(ln, font=f_tit)
        _text_out(d, ((W - wln) / 2, ty), ln, f_tit, CREMA, w=5)
        ty += 92

    cx, cy, R = 620, 640, 320
    bbox = [cx - R, cy - R, cx + R, cy + R]
    f_pct = _font_heavy(52)
    f_lab = _font(36, bold=True)
    ang = -90.0                                  # arranca arriba (12 en punto)
    for i, s in enumerate(series):
        sweep = (vals[i] / total) * 360.0
        a0, a1 = ang, ang + sweep
        col = _PIE_COLORS[i % len(_PIE_COLORS)]
        d.pieslice(bbox, a0, a1, fill=col, outline=(26, 20, 12), width=6)
        mid = math.radians((a0 + a1) / 2)
        px, py = cx + math.cos(mid) * R * 0.62, cy + math.sin(mid) * R * 0.62
        pct = s.get("valor_txt") or f"{round(vals[i] / total * 100)}%"
        _text_out(d, (px, py), str(pct), f_pct, (26, 20, 12), w=3, anchor="mm", outline=CREMA)
        lx, ly = cx + math.cos(mid) * (R + 46), cy + math.sin(mid) * (R + 46)
        anc = "lm" if math.cos(mid) >= 0 else "rm"
        lines = _wrap(d, str(s.get("label", ""))[:26], f_lab, 300)[:2]
        for k, ln in enumerate(lines):
            _text_out(d, (lx, ly + k * 40 - (20 if len(lines) > 1 else 0)),
                      ln, f_lab, CREMA, w=2, anchor=anc)
        ang = a1

    if fuente:
        _text_out(d, (60, H - 54), f"Fuente: {fuente}", _font(28), INK_SOFT, w=2)

    img.convert("RGB").save(output_path, "PNG")
    log.info(f"  Gráfica TORTA: {output_path.name} ({len(series)} rebanadas)")
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
