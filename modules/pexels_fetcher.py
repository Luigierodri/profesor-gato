"""
pexels_fetcher.py — Banco de imágenes/VIDEO royalty-free (Pexels) para el motor v2
Proyecto: Profesor Gato

Pexels: fotos Y video (b-roll) gratis, royalty-free, SIN Content ID. Ideal para lo
que Wikimedia hace mal: escenas, ambiente, conceptos ("campo abandonado", "urna de
votación", "ciudad al atardecer"). Para personas/eventos históricos con nombre se
sigue prefiriendo Wikimedia.

Requiere la variable de entorno PEXELS_API_KEY (gratis en https://www.pexels.com/api).
Si no está, las funciones devuelven None y el selector cae a su siguiente respaldo.

Las queries funcionan MEJOR en inglés (ej. "abandoned farmland aerial").
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path

import requests

log = logging.getLogger("pexels_fetcher")

_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
_PHOTO_URL = "https://api.pexels.com/v1/search"
_VIDEO_URL = "https://api.pexels.com/videos/search"

_FFDIR = (r"C:\Users\luigi\AppData\Local\Microsoft\WinGet\Packages"
          r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin")
FF = shutil.which("ffmpeg") or os.path.join(_FFDIR, "ffmpeg.exe")
W, H = 1920, 1080


def disponible() -> bool:
    return bool(_API_KEY)


def _headers():
    return {"Authorization": _API_KEY}


def _descargar(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return dest.exists() and dest.stat().st_size > 2000
    except Exception as e:
        log.warning(f"  [pexels] descarga falló: {e}")
        return False


def buscar_foto(query: str, out_jpg, por_pagina: int = 10):
    """Descarga una FOTO horizontal de Pexels y la deja en 16:9. Devuelve ruta o None."""
    if not _API_KEY:
        return None
    out_jpg = Path(out_jpg)
    try:
        r = requests.get(_PHOTO_URL, headers=_headers(), timeout=20, params={
            "query": query, "per_page": por_pagina, "orientation": "landscape"})
        r.raise_for_status()
        fotos = r.json().get("photos", [])
    except Exception as e:
        log.warning(f"  [pexels foto] '{query[:40]}': {e}")
        return None
    for foto in fotos:
        src = foto.get("src", {})
        url = src.get("large2x") or src.get("large") or src.get("original")
        if not url:
            continue
        tmp = out_jpg.with_suffix(".dl.jpg")
        if _descargar(url, tmp):
            try:
                _run([FF, "-y", "-loglevel", "error", "-i", str(tmp),
                      "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                             f"crop={W}:{H},setsar=1", "-frames:v", "1", str(out_jpg)])
                tmp.unlink(missing_ok=True)
                log.info(f"  [pexels] foto '{query[:40]}' → {out_jpg.name}")
                return str(out_jpg)
            except Exception as e:
                log.warning(f"  [pexels foto] cover falló: {e}")
    return None


def buscar_video(query: str, out_mp4, por_pagina: int = 8):
    """Descarga un CLIP horizontal HD de Pexels (b-roll, mudo al usarse). Ruta o None."""
    if not _API_KEY:
        return None
    out_mp4 = Path(out_mp4)
    try:
        r = requests.get(_VIDEO_URL, headers=_headers(), timeout=20, params={
            "query": query, "per_page": por_pagina, "orientation": "landscape",
            "size": "medium"})
        r.raise_for_status()
        videos = r.json().get("videos", [])
    except Exception as e:
        log.warning(f"  [pexels video] '{query[:40]}': {e}")
        return None
    for vid in videos:
        # elegir el archivo HD horizontal más cercano a 1080p
        files = [f for f in vid.get("video_files", [])
                 if (f.get("width") or 0) >= (f.get("height") or 1)]
        if not files:
            continue
        files.sort(key=lambda f: abs((f.get("height") or 0) - H))
        url = files[0].get("link")
        if url and _descargar(url, out_mp4):
            log.info(f"  [pexels] video '{query[:40]}' → {out_mp4.name}")
            return str(out_mp4)
    return None


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


if __name__ == "__main__":
    import sys, logging as _l
    _l.basicConfig(level=_l.INFO, format="%(message)s")
    try:
        import truststore; truststore.inject_into_ssl()
    except Exception:
        pass
    q = " ".join(sys.argv[1:]) or "abandoned farmland aerial"
    print("API key:", "OK" if disponible() else "FALTA (define PEXELS_API_KEY)")
    print("foto:", buscar_foto(q, "tmp/pexels_foto.jpg"))
    print("video:", buscar_video(q, "tmp/pexels_video.mp4"))
