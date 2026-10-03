"""
banderas.py — Banderas de países (motor visual v2)
Proyecto: Profesor Gato

Baja la bandera PNG de un país (flagcdn.com, gratis) y la cachea en assets/flags/.
Resuelve el código ISO a partir del nombre en español usando el GeoJSON del mundo
(el mismo de modules/mapa.py), con alias ES→EN. Pensado para poner banderas en vez
de burbujas de color en la gráfica de dispersión.

  iso_de_pais("Colombia") -> "co"
  bandera("Colombia")     -> Path a assets/flags/co_160.png  (o None)
"""
import logging
from pathlib import Path

import requests

log = logging.getLogger("banderas")

BASE_DIR = Path(__file__).parent.parent
FLAGS_DIR = BASE_DIR / "assets" / "flags"


def iso_de_pais(nombre: str) -> str | None:
    """Código ISO-2 (minúsculas) del país, vía el GeoJSON + alias de mapa.py."""
    try:
        from modules import mapa
    except ImportError:
        import mapa
    try:
        ft = mapa._buscar_pais(mapa._cargar(), nombre)
    except Exception as e:
        log.warning(f"  [bandera] no se pudo resolver ISO de '{nombre}': {e}")
        return None
    if not ft:
        return None
    p = ft["properties"]
    iso = p.get("ISO_A2") or p.get("ISO_A2_EH") or ""
    return iso.lower() if iso and iso not in ("-99", "") else None


def bandera(pais_o_iso: str, ancho: int = 160) -> Path | None:
    """Devuelve el Path de la bandera PNG (cacheada), o None. `ancho` ∈ flagcdn:
    20/40/80/160/320/640. Acepta nombre de país o código ISO-2."""
    s = (pais_o_iso or "").strip()
    iso = s.lower() if len(s) == 2 and s.isalpha() else iso_de_pais(s)
    if not iso:
        return None
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    dest = FLAGS_DIR / f"{iso}_{ancho}.png"
    if dest.exists() and dest.stat().st_size > 200:
        return dest
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass
    try:
        r = requests.get(f"https://flagcdn.com/w{ancho}/{iso}.png", timeout=25,
                         headers={"User-Agent": "ProfesorGatoBot/1.0"})
        if r.status_code == 200 and r.content:
            dest.write_bytes(r.content)
            return dest
        log.warning(f"  [bandera] {iso} HTTP {r.status_code}")
    except Exception as e:
        log.warning(f"  [bandera] {iso}: {e}")
    return None


def _rgb(hx: str) -> tuple:
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def bandera_circular(pais_o_iso: str, size: int = 240, aro: str = "#F2C56A") -> Path | None:
    """
    Badge CIRCULAR tipo moneda: la bandera recortada en círculo + aro dorado + glow
    suave, con esquinas transparentes. Se cachea. Devuelve Path (o None).
    `size` = diámetro de la bandera en px; `aro` = color del aro (hex).
    """
    src = bandera(pais_o_iso, ancho=320)
    if not src:
        return None
    iso = src.stem.split("_")[0]
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    dest = FLAGS_DIR / f"{iso}_coin_{size}.png"
    if dest.exists() and dest.stat().st_size > 400:
        return dest
    try:
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter, ImageChops
        flag = Image.open(src).convert("RGBA")
        w, h = flag.size
        s = min(w, h)
        flag = flag.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
        flag = flag.resize((size, size), Image.LANCZOS)

        R = size // 2
        aro_w = max(7, int(size * 0.095))     # aro más grueso para el metal
        pad = int(size * 0.26)                # espacio para aro + sombra
        S = size + 2 * pad
        c = S // 2

        canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))

        # 1) SOMBRA (oscura, desplazada y difuminada): hace que la moneda "flote"
        sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse(
            [c - R - aro_w, c - R - aro_w, c + R + aro_w, c + R + aro_w], fill=(0, 0, 0, 185))
        sh = sh.filter(ImageFilter.GaussianBlur(size * 0.075))
        canvas.alpha_composite(ImageChops.offset(sh, int(size * 0.03), int(size * 0.06)))

        # 2) ARO METÁLICO: degradado DIAGONAL (brillo arriba-izq → bronce abajo-der)
        yy, xx = np.mgrid[0:S, 0:S].astype(float)
        tdiag = np.clip(((xx / S) + (yy / S)) / 2.0, 0, 1)        # 0=arriba-izq, 1=abajo-der
        hi = np.array(_rgb("#FCEAB0"), float)
        mid = np.array(_rgb("#E7BC63"), float)
        lo = np.array(_rgb("#7A5A26"), float)
        seg = tdiag * 2
        col = np.where(seg[..., None] < 1,
                       hi + (mid - hi) * seg[..., None],
                       mid + (lo - mid) * (seg[..., None] - 1))
        grad = Image.fromarray(np.dstack([col.astype(np.uint8),
                                          np.full((S, S), 255, np.uint8)]), "RGBA")
        anillo_mask = Image.new("L", (S, S), 0)
        dm = ImageDraw.Draw(anillo_mask)
        dm.ellipse([c - R - aro_w // 2, c - R - aro_w // 2, c + R + aro_w // 2, c + R + aro_w // 2], fill=255)
        dm.ellipse([c - R + aro_w // 2, c - R + aro_w // 2, c + R - aro_w // 2, c + R - aro_w // 2], fill=0)
        canvas.paste(grad, (0, 0), anillo_mask)

        # 3) bandera recortada en círculo (dentro del aro)
        ri = R - aro_w // 2
        fmask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(fmask).ellipse([aro_w // 2, aro_w // 2, size - aro_w // 2, size - aro_w // 2], fill=255)
        flag_circ = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        flag_circ.paste(flag, (0, 0), fmask)
        canvas.alpha_composite(flag_circ, (c - R, c - R))

        # 4) filos finos (profundidad) + brillo especular arriba-izquierda
        dr = ImageDraw.Draw(canvas)
        dr.ellipse([c - ri, c - ri, c + ri, c + ri], outline=(20, 14, 8, 210), width=max(2, aro_w // 4))
        dr.arc([c - R - aro_w // 2, c - R - aro_w // 2, c + R + aro_w // 2, c + R + aro_w // 2],
               start=160, end=250, fill=(255, 248, 220, 230), width=max(2, aro_w // 3))
        canvas.save(dest)
        return dest
    except Exception as e:
        log.warning(f"  [bandera_circular] {iso}: {e}")
        return None


if __name__ == "__main__":
    import sys
    for q in (sys.argv[1:] or ["Colombia", "Japon", "Estados Unidos", "Chile"]):
        print(q, "->", iso_de_pais(q), bandera_circular(q))
