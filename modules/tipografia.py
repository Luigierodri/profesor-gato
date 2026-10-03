"""
tipografia.py — Palabra/cifra CINÉTICA (motor visual v2)
Proyecto: Profesor Gato

Genera un overlay transparente (.mov con alfa) de una palabra o cifra que aparece
LETRA POR LETRA con un resplandor dorado y un pop suave. Se superpone en el
ensamblador SOLO cuando el dato de verdad vale la pena (no en cada toma).
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_FFDIR = (r"C:\Users\luigi\AppData\Local\Microsoft\WinGet\Packages"
          r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin")
FF = shutil.which("ffmpeg") or os.path.join(_FFDIR, "ffmpeg.exe")

_ORO = (242, 197, 106)
_GLOW = (248, 222, 150)
_FILO = (22, 16, 8)

_FUENTES = ["C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf"]


def _fuente(px):
    from PIL import ImageFont
    for fp in _FUENTES:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, px)
    return ImageFont.load_default()


def render_palabra_cinetica(texto: str, out_mov, dur: float = 2.4, W: int = 1920,
                            H: int = 1080, fontsize: int = 150, y_frac: float = 0.14,
                            fps: int = 30) -> str:
    """Overlay .mov (alfa) de `texto` apareciendo letra por letra con resplandor."""
    from PIL import Image, ImageDraw, ImageFilter
    texto = str(texto).upper()
    font = _fuente(fontsize)
    out_mov = str(out_mov)

    # medir para centrar
    tmp = Image.new("RGBA", (10, 10))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), texto, font=font, stroke_width=fontsize // 26)
    tw = bbox[2] - bbox[0]
    x0 = (W - tw) // 2 - bbox[0]
    y0 = int(H * y_frac)

    total = max(2, int(dur * fps))
    reveal = max(1, int(0.55 * fps))        # frames para revelar todas las letras
    n = len(texto)
    carpeta = Path(tempfile.mkdtemp())
    try:
        for f in range(total):
            k = n if f >= reveal else min(n, int((f / reveal) * n) + 1)
            sub = texto[:k]
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            # resplandor (texto dorado difuminado, doble pasada)
            gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((x0, y0), sub, font=font, fill=_GLOW + (255,))
            gl = gl.filter(ImageFilter.GaussianBlur(fontsize * 0.11))
            img.alpha_composite(gl)
            img.alpha_composite(gl)
            # texto nítido con filo oscuro
            ImageDraw.Draw(img).text((x0, y0), sub, font=font, fill=_ORO + (255,),
                                     stroke_width=max(2, fontsize // 26), stroke_fill=_FILO + (255,))
            img.save(carpeta / f"{f:04d}.png")
        subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", str(fps),
                        "-i", str(carpeta / "%04d.png"), "-c:v", "qtrle",
                        "-pix_fmt", "argb", out_mov],
                       check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    return out_mov


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "1948"
    out = sys.argv[2] if len(sys.argv) > 2 else "tmp/key.mov"
    print(render_palabra_cinetica(t, out))
