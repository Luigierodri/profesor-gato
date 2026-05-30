"""
wikimedia_fetcher.py — Imágenes reales de Wikimedia Commons (gratis, sin API key)
Proyecto: Profesor Gato

Busca y descarga imágenes históricas/enciclopédicas de Wikimedia Commons
para usar como fondos de panel, reemplazando la generación con gpt-image-2.
"""

import json
import logging
import time
import urllib.request
import urllib.parse
from pathlib import Path

log = logging.getLogger("wikimedia_fetcher")

_API = "https://commons.wikimedia.org/w/api.php"
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
_MIN_WIDTH = 800
_THUMB_WIDTH = 1200   # thumbnail size — Wikimedia allows this without 429
_DELAY = 0.5          # seconds between downloads


def _buscar_titulos(query: str, limit: int = 15) -> list[str]:
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,
        "srlimit": limit,
        "format": "json",
    })
    req = urllib.request.Request(
        f"{_API}?{params}", headers={"User-Agent": "ProfesorGatoBot/1.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return [item["title"] for item in data.get("query", {}).get("search", [])]


def _obtener_urls(titulos: list[str]) -> list[dict]:
    """
    Devuelve {url, mime, width} usando thumbnail URLs (evita 429 de Wikimedia).
    iiprop=url retorna la URL del thumbnail cuando se usa iiurlwidth.
    """
    if not titulos:
        return []
    titles_param = "|".join(titulos[:15])
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": titles_param,
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": _THUMB_WIDTH,   # solicita thumbnail, no original
        "format": "json",
    })
    req = urllib.request.Request(
        f"{_API}?{params}", headers={"User-Agent": "ProfesorGatoBot/1.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    candidatos = []
    for page in data.get("query", {}).get("pages", {}).values():
        for info in page.get("imageinfo") or []:
            mime = info.get("mime", "")
            # thumburl es la URL del thumbnail; url es el original (bloqueado)
            thumb_url = info.get("thumburl") or info.get("url", "")
            width = info.get("thumbwidth") or info.get("width", 0)
            if mime in _ALLOWED_MIME and thumb_url and width >= _MIN_WIDTH:
                candidatos.append({"url": thumb_url, "mime": mime, "width": width})
    return candidatos


def buscar_imagenes(tema: str, n: int = 6, carpeta: Path = None) -> list[Path]:
    """
    Descarga hasta `n` imágenes de Wikimedia Commons relacionadas con `tema`.

    Args:
        tema:    Tema de búsqueda (ej. "Milgram experiment psychology")
        n:       Cuántas imágenes necesitas (una por panel)
        carpeta: Directorio de descarga. Si None, usa un tmp propio.

    Returns:
        Lista de Paths descargados (puede ser < n si no hay suficientes resultados).
    """
    if carpeta is None:
        carpeta = Path("tmp") / "wikimedia"
    carpeta.mkdir(parents=True, exist_ok=True)

    # Intentar con el tema completo, luego con primeras 3 palabras si hay pocos resultados
    queries = [tema, " ".join(tema.split()[:3])]
    titulos: list[str] = []
    for q in queries:
        titulos = _buscar_titulos(q, limit=20)
        if len(titulos) >= n:
            break

    candidatos = _obtener_urls(titulos)

    # Ordenar por ancho (preferir imágenes más grandes)
    candidatos.sort(key=lambda c: c["width"], reverse=True)

    # Búsqueda en inglés como fallback (más cobertura en Wikimedia)
    if len(titulos) < n:
        en_query = " ".join(queries[0].split()[:4])
        titulos_en = _buscar_titulos(en_query + " history", limit=15)
        titulos = list(dict.fromkeys(titulos + titulos_en))  # deduplica preservando orden
        candidatos = _obtener_urls(titulos)
        candidatos.sort(key=lambda c: c["width"], reverse=True)

    descargados: list[Path] = []
    for i, c in enumerate(candidatos):
        if len(descargados) >= n:
            break
        ext = ".jpg" if "jpeg" in c["mime"] else ".png"
        dest = carpeta / f"wiki_{i:02d}{ext}"
        if dest.exists():
            descargados.append(dest)
            continue
        try:
            req = urllib.request.Request(c["url"], headers={"User-Agent": "ProfesorGatoBot/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                dest.write_bytes(r.read())
            size_kb = dest.stat().st_size // 1024
            log.info(f"  Wikimedia: {dest.name} ({size_kb} KB, {c['width']}px)")
            descargados.append(dest)
            time.sleep(_DELAY)  # respetar rate limits
        except Exception as e:
            log.warning(f"  Wikimedia: fallo {c['url'][:60]}: {e}")

    log.info(f"  {len(descargados)}/{n} imagenes de Wikimedia Commons para '{tema[:40]}'")
    return descargados
