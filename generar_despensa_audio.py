#!/usr/bin/env python3
"""
generar_despensa_audio.py — Crea la DESPENSA de audio reutilizable con ElevenLabs.
Proyecto: Profesor Gato  ·  Relanzamiento v2

IDEA (ver "Relanzamiento Profesor Gato v2"): lo que generas con ElevenLabs MIENTRAS
pagas conserva licencia comercial PARA SIEMPRE, aunque después canceles. Así que
generamos UNA sola vez, con el plan activo:

  • SFX de CONTENIDO realistas  → assets/sfx/                 (los que numpy/Lyria no
                                                               saben hacer)
  • Camas de MÚSICA por ánimo   → assets/music/despensa/<mood>/

Después el pipeline jala de estas carpetas GRATIS y sin tocar la cuota de voz. Los
SFX de EDICIÓN (whoosh, impacto, ding, pop, riser...) NO se generan aquí: ya salen
gratis del sintetizador numpy en modules/generar_pack_sfx.py.

Uso:
  python generar_despensa_audio.py              # SFX + música (salta lo ya existente)
  python generar_despensa_audio.py --dry-run    # muestra qué generaría, sin gastar
  python generar_despensa_audio.py --only sfx
  python generar_despensa_audio.py --only music
  python generar_despensa_audio.py --moods epico dramatico lofi
  python generar_despensa_audio.py --force      # regenera aunque ya exista

OJO CRÉDITOS: la música consume MUCHO del plan ElevenLabs (cuota compartida con la
voz). Este script es de UNA corrida e idempotente (salta lo que ya existe). El mejor
momento para correrlo es justo después del reset mensual de la cuota, con máximo aire.
"""
import argparse
import logging
import sys
from pathlib import Path

# Avast intercepta el TLS local y rompe la verificación de certificados de Python
# (mismo gotcha que CreditComex). truststore usa el almacén de Windows, que sí tiene
# la raíz de Avast. Opcional: si no está instalado (p. ej. en la nube), seguimos igual.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import requests

from config import ELEVENLABS_API_KEY
from modules.eleven_music import generar_musica_eleven
from modules.music_generator import _MOOD_TO_PROMPT

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("despensa")

BASE_DIR    = Path(__file__).parent
SFX_DIR     = BASE_DIR / "assets" / "sfx"
DESPENSA_M  = BASE_DIR / "assets" / "music" / "despensa"

ELEVEN_SFX_URL = "https://api.elevenlabs.io/v1/sound-generation"
MUSIC_LEN_SEG  = 32   # camas ~32 s; el ensamblador las loopea/corta a la duración real

# SFX de CONTENIDO (realistas). Los NOMBRES coinciden con el mapa de keywords de
# modules/sound_generator.py para que el fallback local los tome solo.
#   nombre_archivo: (prompt, duracion_seg)
SFX_CONTENIDO = {
    "battle_swords.mp3":   ("medieval battle, clashing steel swords, distant war cries and armor", 8),
    "crowd_cheering.mp3":  ("large crowd cheering, applause and excited voices at a political rally", 8),
    "explosion.mp3":       ("powerful deep explosion with debris and low rumble", 5),
    "coins.mp3":           ("gold coins clinking and dropping onto a pile, money sound", 5),
    "clock_ticking.mp3":   ("steady mechanical clock ticking, tense and rhythmic", 8),
    "thunder.mp3":         ("thunder crack and long rolling storm rumble with light rain", 8),
    "space_ambient.mp3":   ("deep space ambient drone, cosmic sci-fi atmosphere", 12),
    "lab_bubbles.mp3":     ("science laboratory bubbling liquids in glass beakers", 8),
    # Look de noticiero / prensa del v2
    "typewriter_news.mp3": ("vintage newsroom teletype and manual typewriter keys clacking", 6),
    "war_drums.mp3":       ("ominous tribal war drums building slow tension", 8),
}


class Stats:
    def __init__(self):
        self.ok = self.skip = self.fail = 0
        self.unauthorized = False


def _gen_sfx(nombre: str, prompt: str, dur: float, force: bool, dry: bool, st: Stats):
    ruta = SFX_DIR / nombre
    if ruta.exists() and not force:
        log.info(f"  · {nombre:22s} ya existe — salto")
        st.skip += 1
        return
    if dry:
        log.info(f"  ○ {nombre:22s} generaría ({dur:.0f}s)  «{prompt[:50]}…»")
        return
    try:
        r = requests.post(ELEVEN_SFX_URL, json={
            "text": prompt,
            "duration_seconds": float(dur),
            "prompt_influence": 0.5,
        }, headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }, timeout=90)
        if r.status_code == 200 and r.content:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(r.content)
            log.info(f"  ✓ {nombre:22s} ({len(r.content)//1024} KB)")
            st.ok += 1
            return
        if r.status_code in (401, 403):
            st.unauthorized = True
        log.warning(f"  ✗ {nombre:22s} {r.status_code}: {r.text[:120]}")
    except Exception as e:
        log.warning(f"  ✗ {nombre:22s} error: {e}")
    st.fail += 1


def _gen_music(mood: str, force: bool, dry: bool, st: Stats):
    destino = DESPENSA_M / mood / f"{mood}.mp3"
    if destino.exists() and not force:
        log.info(f"  · {mood:20s} ya existe — salto")
        st.skip += 1
        return
    base = _MOOD_TO_PROMPT.get(mood, "calm neutral instrumental background music")
    prompt = f"{base}, original instrumental, no vocals, loopable background bed"
    if dry:
        log.info(f"  ○ {mood:20s} generaría ({MUSIC_LEN_SEG}s)  «{base[:46]}…»")
        return
    res = generar_musica_eleven(prompt, MUSIC_LEN_SEG, destino, force_instrumental=True)
    if res:
        st.ok += 1
    else:
        st.fail += 1


def main():
    ap = argparse.ArgumentParser(description="Genera la despensa de audio (SFX + música) con ElevenLabs.")
    ap.add_argument("--only", choices=["sfx", "music"], help="Generar solo una parte.")
    ap.add_argument("--moods", nargs="*", help="Subconjunto de moods para la música.")
    ap.add_argument("--force", action="store_true", help="Regenerar aunque ya exista.")
    ap.add_argument("--dry-run", action="store_true", help="Mostrar qué haría, sin llamar la API.")
    args = ap.parse_args()

    if not ELEVENLABS_API_KEY and not args.dry_run:
        log.error("ERROR: falta ELEVENLABS_API_KEY en el entorno/config.")
        sys.exit(1)

    st = Stats()
    hacer_sfx   = args.only in (None, "sfx")
    hacer_music = args.only in (None, "music")
    moods = args.moods or list(_MOOD_TO_PROMPT.keys())

    log.info("=" * 64)
    log.info("DESPENSA DE AUDIO — ElevenLabs (licencia comercial permanente)")
    if args.dry_run:
        log.info("MODO DRY-RUN: no se gasta ni un crédito, solo te muestro el plan.")
    log.info("=" * 64)

    if hacer_sfx:
        log.info(f"\n[SFX de contenido] → {SFX_DIR}")
        for nombre, (prompt, dur) in SFX_CONTENIDO.items():
            _gen_sfx(nombre, prompt, dur, args.force, args.dry_run, st)
            if st.unauthorized:
                break

    if hacer_music and not st.unauthorized:
        log.info(f"\n[Camas de música por ánimo] → {DESPENSA_M}")
        for mood in moods:
            if mood not in _MOOD_TO_PROMPT:
                log.warning(f"  (mood desconocido, lo salto: {mood})")
                continue
            _gen_music(mood, args.force, args.dry_run, st)

    log.info("\n" + "=" * 64)
    log.info(f"Resumen:  OK={st.ok}   saltados={st.skip}   fallidos={st.fail}")
    if st.unauthorized:
        log.error(
            "\n⚠  La API key devolvió 401/403: el permiso de *Sound Generation* "
            "(y *Music*) NO está activo en la key.\n"
            "   Actívalo en el dashboard de ElevenLabs → tu API key → permisos, y "
            "vuelve a correr esto."
        )
    elif not args.dry_run and st.ok:
        log.info("Listo. El pipeline ya jala de assets/sfx/ y assets/music/despensa/ solo.")
    log.info("=" * 64)


if __name__ == "__main__":
    main()
