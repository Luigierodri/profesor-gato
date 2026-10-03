"""
movimiento.py — Anima una FOTO en un clip con movimiento (Ken Burns dinámico)
Proyecto: Profesor Gato (motor visual v2)

Convierte una imagen fija en un clip con zoom/paneo suave para que NADA quede
quieto. Las fotos ya vienen encuadradas a la cara (wikimedia_fetcher._cover_16x9),
así que el zoom al centro cae bien.

NOTA: el parallax 2.5D real (Depth Anything) es un upgrade futuro (modelo pesado,
mejor en la nube). Aquí un Ken Burns con aceleración suave ya mata el "estático".
Usa ffmpeg zoompan sobre UNA imagen (d=frames) para que el zoom ACUMULE bien.
"""
import os
import shutil
import subprocess
from pathlib import Path

_FFMPEG_FALLBACK = (r"C:\Users\luigi\AppData\Local\Microsoft\WinGet\Packages"
                    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
                    r"\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe")


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or os.getenv("FFMPEG_BIN") or _FFMPEG_FALLBACK


def foto_a_clip(img: str, out: str, dur: float = 4.0,
                movimiento: str = "zoom_in", w: int = 1920, h: int = 1080,
                fps: int = 30, zmax: float = 1.14) -> str:
    """
    Anima `img` en un clip de `dur` s con movimiento. Devuelve la ruta del .mp4.
      movimiento: "zoom_in" (default) · "zoom_out" · "paneo_der" · "paneo_izq" ·
                  "parallax" (por ahora = zoom_in suave hasta tener profundidad real)
    """
    img = str(img)
    out = str(out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    frames = max(2, int(round(dur * fps)))
    inc = (zmax - 1.0) / frames  # incremento de zoom por frame (acumula en zoompan)

    # Sobre-escalar a ~2x para que el zoom no pixele, cubriendo 16:9 sin deformar.
    base = f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},setsar=1"

    cx = f"iw/2-(iw/zoom/2)"
    cy = f"ih/2-(ih/zoom/2)"
    if movimiento in ("zoom_in", "parallax", "zoom"):
        z = f"min(zoom+{inc:.6f},{zmax})"
        x, y = cx, cy
    elif movimiento == "zoom_out":
        # arranca en zmax y baja hacia 1 (on = frame de salida 0..frames-1)
        z = f"max({zmax}-{inc:.6f}*on,1.0)"
        x, y = cx, cy
    elif movimiento in ("paneo_der", "paneo", "paneo_izq"):
        z = f"{1.0 + (zmax-1.0)/2:.4f}"  # zoom fijo leve para dejar margen de paneo
        avance = f"(iw-iw/zoom)*on/{frames}"
        x = avance if movimiento != "paneo_izq" else f"(iw-iw/zoom)-({avance})"
        y = cy
    else:
        z, x, y = f"min(zoom+{inc:.6f},{zmax})", cx, cy

    vf = (f"{base},zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
          f"format=yuv420p")

    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-i", img,
           "-vf", vf, "-frames:v", str(frames),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", out]
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    return out


if __name__ == "__main__":
    import sys
    img = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "tmp/clip_demo.mp4"
    mov = sys.argv[3] if len(sys.argv) > 3 else "zoom_in"
    print(foto_a_clip(img, out, dur=4.0, movimiento=mov))
