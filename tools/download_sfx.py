"""
download_sfx.py — Descarga efectos de sonido de fallback via yt-dlp
Uso: python tools/download_sfx.py

Descarga a assets/sfx/ los efectos base que usa sound_generator como último fallback.
"""
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SFX_DIR = Path(__file__).parent.parent / "assets" / "sfx"

SFX_TRACKS = {
    "crowd_cheering.mp3":   "scsearch1:crowd cheering people chanting revolution sound effect no copyright",
    "battle_swords.mp3":    "scsearch1:battle swords clashing medieval fight sound effect no copyright",
    "explosion.mp3":        "scsearch1:explosion boom dramatic sound effect no copyright free",
    "coins.mp3":            "scsearch1:coins money jingling sound effect no copyright free",
    "clock_ticking.mp3":    "scsearch1:clock ticking timer countdown sound effect no copyright",
    "thunder.mp3":          "scsearch1:thunder storm dramatic sound effect no copyright free",
    "space_ambient.mp3":    "scsearch1:space ambient atmosphere sound effect no copyright free",
    "lab_bubbles.mp3":      "scsearch1:laboratory science bubbling ambient sound effect no copyright",
}


def descargar(nombre: str, query: str) -> bool:
    dest = SFX_DIR / nombre
    if dest.exists():
        print(f"  Ya existe: {nombre}")
        return True
    stem = nombre.replace(".mp3", "")
    out_tmpl = str(SFX_DIR / f"{stem}.%(ext)s")
    cmd = [
        "yt-dlp", query,
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "6",
        "--output", out_tmpl,
        "--no-playlist", "--quiet", "--no-warnings",
        "--match-filter", "duration < 120",
    ]
    print(f"  Descargando {nombre}...")
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=90)
    # yt-dlp puede cambiar el nombre — renombramos al esperado
    generados = list(SFX_DIR.glob(f"{stem}*.mp3"))
    if generados:
        if generados[0] != dest:
            generados[0].rename(dest)
        print(f"  OK  {dest.name} ({dest.stat().st_size // 1024} KB)")
        return True
    if result.stderr.strip():
        print(f"  ERR {result.stderr[:80]}")
    return False


def main():
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nDescargando SFX de fallback a {SFX_DIR}\n")
    ok = sum(descargar(n, q) for n, q in SFX_TRACKS.items())
    print(f"\n{ok}/{len(SFX_TRACKS)} efectos disponibles en assets/sfx/")


if __name__ == "__main__":
    main()
