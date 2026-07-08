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
        f"{_API}?{params}", headers={"User-Agent": "ProfesorGatoBot/1.1 (https://www.youtube.com/@Gatoprofesor; luigiebass@gmail.com)"}
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
        f"{_API}?{params}", headers={"User-Agent": "ProfesorGatoBot/1.1 (https://www.youtube.com/@Gatoprofesor; luigiebass@gmail.com)"}
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

    # Variantes de query, de específica a genérica: las queries "de fotógrafo" con
    # 6+ palabras (AND) suelen dar 0; recortar palabras rescata casi siempre.
    palabras = tema.split()
    variantes = list(dict.fromkeys(
        [" ".join(palabras[:k]) for k in (len(palabras), 5, 4, 3, 2) if k >= 2]))

    # 2 rondas: la API de Wikimedia a veces rate-limitea SILENCIOSAMENTE (HTTP 200
    # con resultado vacío) — una pausa corta y reintento rescatan la foto.
    candidatos: list[dict] = []
    for ronda in range(3):
        for q in variantes:
            try:
                titulos = _buscar_titulos(q, limit=20)
            except Exception as e:
                log.warning(f"  Wikimedia search '{q[:40]}': {e}")
                continue
            if not titulos:
                continue
            candidatos = _obtener_urls(titulos)
            if candidatos:
                break
            time.sleep(1.0)          # entre variantes: no martillar la API
        if candidatos:
            break
        log.info("  Wikimedia sin candidatos (¿ratelimit silencioso?) — pausa y reintento")
        time.sleep(8)

    # Ordenar por ancho (preferir imágenes más grandes)
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
            req = urllib.request.Request(c["url"], headers={"User-Agent": "ProfesorGatoBot/1.1 (https://www.youtube.com/@Gatoprofesor; luigiebass@gmail.com)"})
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


def _cover_16x9(src: Path, dest: Path, w: int = 1920, h: int = 1080) -> str:
    """Escala una imagen para CUBRIR 16:9 y recorta al centro (sin deformar)."""
    from PIL import Image
    with Image.open(src) as im:
        im = im.convert("RGB")
        sw, sh = im.size
        escala = max(w / sw, h / sh)
        nw, nh = int(sw * escala + 0.5), int(sh * escala + 0.5)
        im = im.resize((nw, nh), Image.LANCZOS)
        x0 = (nw - w) // 2
        y0 = (nh - h) // 2
        im = im.crop((x0, y0, x0 + w, y0 + h))
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "PNG")
    return str(dest)


def fondo_16x9(query: str, output_path, carpeta_tmp: Path = None) -> str | None:
    """Devuelve UNA foto real de Wikimedia recortada a 16:9 (1920x1080), o None.

    Pensado para fondos de ensayo: 'FIFA World Cup stadium crowd', 'Mexico City
    skyline aerial', 'crude oil refinery'. Usa consultas EN INGLÉS y genéricas
    (mejor cobertura en Commons). None → el pipeline cae al fondo pixel-art.
    """
    output_path = Path(output_path)
    tmp = carpeta_tmp or (output_path.parent / "_wiki_src")
    candidatas = buscar_imagenes(query, n=4, carpeta=tmp)
    for src in candidatas:
        try:
            return _cover_16x9(src, output_path)
        except Exception as e:
            log.warning(f"  fondo_16x9: no se pudo procesar {src.name}: {e}")
    log.warning(f"  fondo_16x9: sin foto usable para '{query[:50]}'")
    return None
