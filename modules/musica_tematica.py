"""
musica_tematica.py — Cama musical que IDENTIFICA la escena (motor visual v2)
Proyecto: Profesor Gato

En vez de UNA cama genérica para todo el video, arma una secuencia que CAMBIA de
"sabor" por escena/capítulo: cumbia colombiana cuando se habla de Macondo, aire
andino solemne en lo histórico, tensión en el clímax… Cada sabor se GENERA una sola
vez con ElevenLabs Music (licencia comercial permanente, royalty-free → sin Content
ID como tendría el himno/cumbia comercial) y se CACHEA en assets/music/tematica/.
Reusos = $0 y no tocan la cuota de voz.

OJO: la melodía del Himno Nacional es de dominio público, pero una GRABACIÓN oficial
da strike. Por eso aquí se pide a ElevenLabs una interpretación propia instrumental
(p. ej. "solemn colombian patriotic anthem style, orchestral, instrumental").

Si MUSICA_TEMATICA=0, el ensamblador usa la despensa de moods de siempre.
"""
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("musica_tematica")

BASE_DIR = Path(__file__).parent.parent
TEMATICA_DIR = BASE_DIR / "assets" / "music" / "tematica"
_FFDIR = (r"C:\Users\luigi\AppData\Local\Microsoft\WinGet\Packages"
          r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin")
FF = shutil.which("ffmpeg") or os.path.join(_FFDIR, "ffmpeg.exe")

# Duración del bed base que se genera y cachea por sabor (se loopea/corta al vuelo).
BED_SEG = 45
_XFADE = 1.2        # crossfade entre sabores (s)


def _slug(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", (s or "").lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "_", s.strip())[:60] or "ambiente"


def _enriquecer(flavor: str) -> str:
    """El sabor del guion (a veces en español) → prompt instrumental para ElevenLabs."""
    f = flavor.strip()
    low = f.lower()
    if "instrument" not in low:
        f += ", instrumental"
    return f + ", background score, loopable, no vocals, no lyrics"


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


def _asegurar_bed(flavor: str, generar: bool) -> Path | None:
    """Devuelve el bed cacheado del sabor; lo genera (1 sola vez) si falta y se permite."""
    TEMATICA_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMATICA_DIR / f"{_slug(flavor)}.mp3"
    if path.exists() and path.stat().st_size > 2000:
        return path
    if not generar:
        return None
    try:
        from modules.eleven_music import generar_musica_eleven
        r = generar_musica_eleven(_enriquecer(flavor), BED_SEG, path,
                                  force_instrumental=True)
        return r if (r and path.exists()) else None
    except Exception as e:
        log.warning(f"  [MusTemática] no se pudo generar '{flavor}': {e}")
        return None


def _bed_a_duracion(bed: Path, dur: float, out: Path):
    """Loopea/corta un bed a `dur`, con fade in/out suave."""
    fo = max(0.1, dur - 0.8)
    _run([FF, "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(bed),
          "-t", f"{dur:.3f}",
          "-af", f"afade=t=in:st=0:d=0.6,afade=t=out:st={fo:.2f}:d=0.8",
          "-c:a", "libmp3lame", "-q:a", "4", str(out)])


def cama_por_escena(bloques, work: Path, generar: bool = True) -> Path | None:
    """
    Arma la cama musical temática.

    Args:
        bloques: lista de (flavor:str, dur:float) — un sabor por bloque de escena
                 (bloques consecutivos con el mismo sabor ya vienen fusionados).
        work:    carpeta de trabajo.
        generar: si True, genera con ElevenLabs los sabores que falten (1 vez c/u).

    Returns:
        Path del .mp3 continuo (sabores encadenados con crossfade), o None.
    """
    work = Path(work)
    partes = []
    for i, (flavor, dur) in enumerate(bloques):
        if dur <= 0.2:
            continue
        bed = _asegurar_bed(flavor, generar)
        if not bed:
            continue
        p = work / f"mus_bloque_{i:03d}.mp3"
        try:
            _bed_a_duracion(bed, dur + (_XFADE if i < len(bloques) - 1 else 0), p)
            partes.append(p)
        except Exception as e:
            log.warning(f"  [MusTemática] bloque {i} omitido: {e}")
    if not partes:
        return None
    if len(partes) == 1:
        return partes[0]

    # encadenar los sabores con crossfade (acrossfade en cadena)
    cmd = [FF, "-y", "-loglevel", "error"]
    for p in partes:
        cmd += ["-i", str(p)]
    fg, cur = [], "[0:a]"
    for i in range(1, len(partes)):
        out = f"[a{i}]"
        fg.append(f"{cur}[{i}:a]acrossfade=d={_XFADE:.2f}:c1=tri:c2=tri{out}")
        cur = out
    out_mp3 = work / "musica_tematica.mp3"
    cmd += ["-filter_complex", ";".join(fg), "-map", cur,
            "-c:a", "libmp3lame", "-q:a", "4", str(out_mp3)]
    try:
        _run(cmd)
        return out_mp3 if out_mp3.exists() else partes[0]
    except Exception as e:
        log.warning(f"  [MusTemática] encadenado falló ({e}); uso el primer bloque")
        return partes[0]
