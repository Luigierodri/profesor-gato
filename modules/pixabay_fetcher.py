"""
pixabay_fetcher.py — Banco de imágenes/VIDEO royalty-free (Pixabay) para el motor v2
Proyecto: Profesor Gato

Alternativa a Pexels (que pausó la emisión de keys). Pixabay: fotos Y video gratis,
royalty-free, SIN Content ID. Key instantánea y gratis en https://pixabay.com/api/docs/
(aparece al iniciar sesión). Requiere la variable de entorno PIXABAY_API_KEY.

Queries MEJOR en inglés (ej. "abandoned farmland aerial").
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path

import requests

log = logging.getLogger("pixabay_fetcher")

_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()
_PHOTO_URL = "https://pixabay.com/api/"
_VIDEO_URL = "https://pixabay.com/api/videos/"

_FFDIR = (r"C:\Users\luigi\AppData\Local\Microsoft\WinGet\Packages"
          r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin")
FF = shutil.which("ffmpeg") or os.path.join(_FFDIR, "ffmpeg.exe")
W, H = 1920, 1080


def disponible() -> bool:
    return bool(_API_KEY)


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


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
        log.warning(f"  [pixabay] descarga falló: {e}")
        return False


def buscar_foto(query: str, out_jpg, por_pagina: int = 12):
    """Descarga una FOTO horizontal de Pixabay y la deja en 16:9. Ruta o None."""
    if not _API_KEY:
        return None
    out_jpg = Path(out_jpg)
    try:
        r = requests.get(_PHOTO_URL, timeout=20, params={
            "key": _API_KEY, "q": query, "image_type": "photo",
            "orientation": "horizontal", "per_page": por_pagina, "safesearch": "true"})
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception as e:
        log.warning(f"  [pixabay foto] '{query[:40]}': {e}")
        return None
    for h in hits:
        url = h.get("largeImageURL") or h.get("webformatURL")
        if not url:
            continue
        tmp = out_jpg.with_suffix(".dl.jpg")
        if _descargar(url, tmp):
            try:
                _run([FF, "-y", "-loglevel", "error", "-i", str(tmp),
                      "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                             f"crop={W}:{H},setsar=1", "-frames:v", "1", str(out_jpg)])
                tmp.unlink(missing_ok=True)
                log.info(f"  [pixabay] foto '{query[:40]}' → {out_jpg.name}")
                return str(out_jpg)
            except Exception as e:
                log.warning(f"  [pixabay foto] cover falló: {e}")
    return None


def buscar_video(query: str, out_mp4, por_pagina: int = 8):
    """Descarga un CLIP horizontal de Pixabay (b-roll). Ruta o None."""
    if not _API_KEY:
        return None
    out_mp4 = Path(out_mp4)
    try:
        r = requests.get(_VIDEO_URL, timeout=20, params={
            "key": _API_KEY, "q": query, "per_page": por_pagina, "safesearch": "true"})
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception as e:
        log.warning(f"  [pixabay video] '{query[:40]}': {e}")
        return None
    for h in hits:
        vids = h.get("videos", {})
        # preferir 'large' (≈1080p), luego 'medium'
        for size in ("large", "medium", "small"):
            url = (vids.get(size) or {}).get("url")
            if url and _descargar(url, out_mp4):
                log.info(f"  [pixabay] video '{query[:40]}' → {out_mp4.name}")
                return str(out_mp4)
    return None


if __name__ == "__main__":
    import sys, logging as _l
    _l.basicConfig(level=_l.INFO, format="%(message)s")
    try:
        import truststore; truststore.inject_into_ssl()
    except Exception:
        pass
    q = " ".join(sys.argv[1:]) or "abandoned farmland aerial"
    print("API key:", "OK" if disponible() else "FALTA (define PIXABAY_API_KEY)")
    print("foto:", buscar_foto(q, "tmp/pixabay_foto.jpg"))
    print("video:", buscar_video(q, "tmp/pixabay_video.mp4"))
