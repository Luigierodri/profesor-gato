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
    # La API devuelve las páginas DESORDENADAS (por pageid), perdiendo el ranking de
    # relevancia de la búsqueda. Mapeamos por título y luego devolvemos EN EL ORDEN
    # de `titulos` (relevancia) — así la 1a foto de "Gabriel García Márquez" es la de
    # él, no una imagen grande e irrelevante que se colaba por tamaño.
    por_titulo: dict[str, dict] = {}
    for page in data.get("query", {}).get("pages", {}).values():
        t = page.get("title")
        for info in page.get("imageinfo") or []:
            mime = info.get("mime", "")
            thumb_url = info.get("thumburl") or info.get("url", "")   # thumburl=thumbnail; url=original (bloqueado)
            width = info.get("thumbwidth") or info.get("width", 0)
            if mime in _ALLOWED_MIME and thumb_url and width >= _MIN_WIDTH and t not in por_titulo:
                por_titulo[t] = {"url": thumb_url, "mime": mime, "width": width, "title": t}
            break
    return [por_titulo[t] for t in titulos if t in por_titulo]


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

    # NO reordenar por tamaño: perdía la relevancia (una imagen enorme irrelevante se
    # colaba de primera). Respetamos el orden de la búsqueda (más relevante primero);
    # _MIN_WIDTH ya descarta las muy chicas.
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


def _detectar_caras(im_rgb) -> list[tuple]:
    """Caras (x,y,w,h) en la imagen PIL dada, o [] si no hay cv2/no detecta."""
    try:
        import cv2, numpy as np
        gris = cv2.cvtColor(np.array(im_rgb), cv2.COLOR_RGB2GRAY)
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        caras = casc.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=6,
                                      minSize=(max(40, gris.shape[0] // 12),) * 2)
        return [tuple(int(v) for v in c) for c in caras]
    except Exception:
        return []


def _cover_16x9(src: Path, dest: Path, w: int = 1920, h: int = 1080) -> str:
    """Escala para CUBRIR 16:9 (sin deformar) y recorta. Si hay CARAS, encuadra para
    NO cortarlas (deja aire arriba); si no, recorta al centro."""
    from PIL import Image
    with Image.open(src) as im:
        im = im.convert("RGB")
        sw, sh = im.size
        escala = max(w / sw, h / sh)
        nw, nh = int(sw * escala + 0.5), int(sh * escala + 0.5)
        im = im.resize((nw, nh), Image.LANCZOS)

        x0, y0 = (nw - w) // 2, (nh - h) // 2  # default: centro
        caras = _detectar_caras(im)
        if caras:
            fx0 = min(c[0] for c in caras)
            fy0 = min(c[1] for c in caras)
            fx1 = max(c[0] + c[2] for c in caras)
            fy1 = max(c[1] + c[3] for c in caras)
            mh = int(h * 0.14)   # aire sobre las cabezas
            # vertical: deja aire arriba; si no caben todas, prioriza las cabezas
            y0 = fy0 - mh
            if y0 + h < fy1:
                y0 = (fy0 + fy1) // 2 - h // 2
            # horizontal: centra en el grupo de caras
            x0 = (fx0 + fx1) // 2 - w // 2
            x0 = max(0, min(x0, nw - w))
            y0 = max(0, min(y0, nh - h))

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
