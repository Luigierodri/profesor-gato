"""
download_music.py — Descarga tracks lofi/ambient gratuitos via yt-dlp
Uso: python tools/download_music.py

Descarga 5 tracks de lofi/ambient a assets/music/ usando SoundCloud y
YouTube Audio Library (búsquedas de contenido libre de derechos).
"""

import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MUSIC_DIR = Path(__file__).parent.parent / "assets" / "music"
OBJETIVO   = 5

# Búsquedas en SoundCloud — tracks lofi/ambient con licencia libre
SEARCHES = [
    "scsearch1:lofi hip hop chill no copyright study",
    "scsearch1:ambient relaxing background music no copyright free",
    "scsearch1:lofi beats instrumental no copyright calm",
    "scsearch1:chill lofi music background creative commons",
    "scsearch1:ambient piano no copyright relaxing background",
]


def descargar_track(query: str, destino: Path, idx: int) -> bool:
    out_tmpl = str(destino / f"lofi_{idx:02d}_%(title).40s.%(ext)s")
    cmd = [
        "yt-dlp",
        query,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",      # ~128kbps, suficiente para fondo
        "--output", out_tmpl,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--match-filter", "duration < 400",   # max ~6 min
    ]
    print(f"  Buscando: {query.replace('scsearch1:', '')[:60]}...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    nuevos = list(destino.glob(f"lofi_{idx:02d}_*.mp3"))
    if nuevos:
        print(f"  OK {nuevos[0].name} ({nuevos[0].stat().st_size // 1024} KB)")
        return True
    if result.stderr:
        print(f"  WARN: {result.stderr[:120]}")
    return False


def main():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    existentes = [f for f in MUSIC_DIR.iterdir()
                  if f.is_file() and f.suffix.lower() in {".mp3",".wav",".ogg",".m4a",".flac",".aac"}]
    faltantes = max(0, OBJETIVO - len(existentes))

    print(f"\nMusica en assets/music/: {len(existentes)} track(s). Objetivo: {OBJETIVO}")
    if faltantes == 0:
        print("Ya hay suficientes tracks.")
        for f in existentes:
            print(f"  {f.name}")
        return

    print(f"Descargando {faltantes} track(s) de SoundCloud via yt-dlp...\n")
    idx = len(existentes) + 1
    descargados = 0
    for query in SEARCHES:
        if descargados >= faltantes:
            break
        if descargar_track(query, MUSIC_DIR, idx):
            descargados += 1
            idx += 1

    total = [f for f in MUSIC_DIR.iterdir()
             if f.is_file() and f.suffix.lower() in {".mp3",".wav",".ogg",".m4a",".flac",".aac"}]
    print(f"\nTotal en assets/music/: {len(total)} tracks")
    for f in total:
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
