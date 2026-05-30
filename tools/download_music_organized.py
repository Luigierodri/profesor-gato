"""
download_music_organized.py — Descarga tracks organizados por mood contextual
Uso: python tools/download_music_organized.py

Estructura:
  assets/music/clasica_dramatica/  — historia, política, guerras, revoluciones
  assets/music/epico_orquestal/    — imperios, batallas, civilizaciones antiguas
  assets/music/lofi_moderno/       — economía, finanzas, tecnología
  assets/music/ambient_misterioso/ — ciencia, espacio, fenómenos extraños
  assets/music/alegre_pop/         — cultura pop, deportes, curiosidades
"""

import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MUSIC_BASE = Path(__file__).parent.parent / "assets" / "music"
OBJETIVO_POR_CATEGORIA = 5

CATEGORIAS = {
    "clasica_dramatica": [
        "scsearch1:dramatic classical orchestra no copyright background music revolution",
        "scsearch1:french revolution dramatic classical music no copyright free",
        "scsearch1:historical drama classical background music no copyright",
        "scsearch1:baroque dramatic classical music no copyright background",
        "scsearch1:dramatic strings orchestra no copyright cinematic history",
    ],
    "epico_orquestal": [
        "scsearch1:epic orchestral battle music no copyright free background",
        "scsearch1:ancient rome epic music no copyright orchestral free",
        "scsearch1:heroic epic cinematic orchestra no copyright background",
        "scsearch1:powerful epic orchestral no copyright free dramatic",
        "scsearch1:epic war orchestral background music no copyright cinematic",
    ],
    "lofi_moderno": [
        "scsearch1:lofi hip hop chill study background music no copyright",
        "scsearch1:modern lofi beats no copyright background instrumental",
        "scsearch1:chill lofi hip hop no copyright free background music",
        "scsearch1:lofi piano beats study background no copyright free",
        "scsearch1:lofi chillhop background music no copyright instrumental",
    ],
    "ambient_misterioso": [
        "scsearch1:mysterious ambient science background music no copyright",
        "scsearch1:space ambient mysterious background no copyright free",
        "scsearch1:dark ambient mysterious instrumental no copyright background",
        "scsearch1:eerie mysterious ambient background music no copyright",
        "scsearch1:sci-fi mysterious ambient background no copyright instrumental",
    ],
    "alegre_pop": [
        "scsearch1:happy upbeat pop background music no copyright free",
        "scsearch1:cheerful fun upbeat music no copyright background",
        "scsearch1:energetic upbeat pop no copyright background music free",
        "scsearch1:positive happy background music no copyright instrumental",
        "scsearch1:fun playful upbeat music no copyright background free",
    ],
}


def descargar_track(query: str, carpeta: Path, idx: int) -> bool:
    out_tmpl = str(carpeta / f"track_{idx:02d}_%(title).35s.%(ext)s")
    cmd = [
        "yt-dlp", query,
        "--extract-audio", "--audio-format", "mp3",
        "--audio-quality", "5",
        "--output", out_tmpl,
        "--no-playlist", "--quiet", "--no-warnings",
        "--match-filter", "duration < 480",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    nuevos = sorted(carpeta.glob(f"track_{idx:02d}_*.mp3"))
    if nuevos:
        print(f"    OK  {nuevos[0].name}")
        return True
    stderr = result.stderr.strip()
    if stderr:
        print(f"    ERR {stderr[:80]}")
    return False


def main():
    print(f"\nDescargando tracks por categoria de mood...\n")
    MUSIC_BASE.mkdir(parents=True, exist_ok=True)

    total_ok = 0
    for mood, queries in CATEGORIAS.items():
        carpeta = MUSIC_BASE / mood
        carpeta.mkdir(exist_ok=True)

        existentes = list(carpeta.glob("*.mp3"))
        faltantes  = max(0, OBJETIVO_POR_CATEGORIA - len(existentes))
        if faltantes == 0:
            print(f"  [{mood}] Ya tiene {len(existentes)} tracks - ok")
            total_ok += len(existentes)
            continue

        print(f"  [{mood}] Descargando {faltantes} track(s)...")
        idx = len(existentes) + 1
        for query in queries[len(existentes):len(existentes) + faltantes]:
            if descargar_track(query, carpeta, idx):
                total_ok += 1
                idx += 1

    print(f"\nTotal: {total_ok} tracks")
    for mood in CATEGORIAS:
        carpeta = MUSIC_BASE / mood
        tracks  = list(carpeta.glob("*.mp3"))
        print(f"  {mood}/  ({len(tracks)} tracks)")


if __name__ == "__main__":
    main()
