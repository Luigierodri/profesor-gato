"""
openverse_fetcher.py — Imágenes Creative Commons vía Openverse (SIN API key)
Proyecto: Profesor Gato

Openverse (de WordPress) agrega imágenes Creative Commons de muchas fuentes (museos,
Flickr, etc.). API pública SIN key (con límite de tasa razonable para uso bajo). Buen
respaldo cuando Wikimedia no tiene y no hay key de Pexels/Pixabay.

Queries MEJOR en inglés.
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path

import requests

log = logging.getLogger("openverse_fetcher")

_API = "https://api.openverse.org/v1/images/"
_UA = "ProfesorGatoBot/1.0 (educational video automation; luigiebass@gmail.com)"

_FFDIR = (r"C:\Users\luigi\AppData\Local\Microsoft\WinGet\Packages"
          r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin")
FF = shutil.which("ffmpeg") or os.path.join(_FFDIR, "ffmpeg.exe")
W, H = 1920, 1080


def disponible() -> bool:
    return True                       # no necesita key


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


def _descargar(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=40, stream=True, headers={"User-Agent": _UA})
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return dest.exists() and dest.stat().st_size > 2000
    except Exception as e:
        log.info(f"  [openverse] descarga falló: {e}")
        return False


def buscar_foto(query: str, out_jpg, por_pagina: int = 10):
    """Descarga una imagen CC horizontal de Openverse y la deja en 16:9. Ruta o None."""
    out_jpg = Path(out_jpg)
    try:
        r = requests.get(_API, timeout=20, headers={"User-Agent": _UA}, params={
            "q": query, "page_size": por_pagina, "aspect_ratio": "wide",
            "mature": "false"})
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as e:
        log.info(f"  [openverse] '{query[:40]}': {e}")
        return None
    for it in results:
        url = it.get("url") or it.get("thumbnail")
        if not url:
            continue
        tmp = out_jpg.with_suffix(".dl.img")
        if _descargar(url, tmp):
            try:
                _run([FF, "-y", "-loglevel", "error", "-i", str(tmp),
                      "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                             f"crop={W}:{H},setsar=1", "-frames:v", "1", str(out_jpg)])
                tmp.unlink(missing_ok=True)
                log.info(f"  [openverse] foto '{query[:40]}' → {out_jpg.name}")
                return str(out_jpg)
            except Exception as e:
                log.info(f"  [openverse] cover falló: {e}")
    return None


if __name__ == "__main__":
    import sys, logging as _l
    _l.basicConfig(level=_l.INFO, format="%(message)s")
    try:
        import truststore; truststore.inject_into_ssl()
    except Exception:
        pass
    q = " ".join(sys.argv[1:]) or "colombian countryside"
    print("foto:", buscar_foto(q, "tmp/openverse_foto.jpg"))
