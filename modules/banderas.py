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


if __name__ == "__main__":
    import sys
    for q in (sys.argv[1:] or ["Colombia", "Japon", "Estados Unidos", "Chile"]):
        print(q, "->", iso_de_pais(q), bandera(q))
