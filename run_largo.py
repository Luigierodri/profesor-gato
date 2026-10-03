"""
run_largo.py — Pipeline del LARGO formato NARRADOR ÚNICO (motor visual v2)
Proyecto: Profesor Gato

Une todo lo construido: ficha de datos VERIFICADOS (fact_checker) → guion narrador
(narrador_generator, con system_prompt_narrador) → video (ensamblador_narrador:
voz paleta + visual real/mapa/moneda/gráfica + palabra cinética + Gato en poses +
música + karaoke). Escribe a videos_largos/. NO publica (Luigi revisa).

NO toca el pipeline viejo (run_essay dúo Gato/Bastet, ni los Shorts).

USO:
  python run_largo.py "¿Colombia vive en Macondo?"                 # ficha + guion + video
  python run_largo.py "¿Colombia vive en Macondo?" --script-only   # solo ficha + guion (barato)
  python run_largo.py "..." --reuse-script videos_largos/X/guion.json   # re-render del guion
  python run_largo.py "..." --sin-ficha        # salta la búsqueda web (sin verificar)
  python run_largo.py "..." --tema azul_noche  # fuerza un tema de color
  python run_largo.py "..." --no-musica --no-karaoke
"""

import sys
import json
import logging
import re
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Avast bloquea el TLS local; truststore usa el almacén de Windows (gotcha recurrente).
try:
    import truststore; truststore.inject_into_ssl()
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("run_largo")

BASE_DIR = Path(__file__).parent
SALIDA_DIR = BASE_DIR / "videos_largos"


def _slug(t: str) -> str:
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return re.sub(r"\s+", "_", t.strip())[:60]


def _banner(t):
    log.info("=" * 60); log.info(f"  {t}"); log.info("=" * 60)


def _arg(flag: str, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # el valor de --reuse-script/--tema no es "el tema"
    for consumidor in ("--reuse-script", "--tema"):
        v = _arg(consumidor)
        if v in args:
            args.remove(v)
    tema = args[0] if args else "¿Por qué Colombia parece vivir en Macondo?"

    reuse = _arg("--reuse-script")
    tema_color = _arg("--tema")                      # negro_oro | azul_noche | ...
    script_only = "--script-only" in sys.argv
    sin_ficha = "--sin-ficha" in sys.argv
    con_musica = "--no-musica" not in sys.argv
    con_karaoke = "--no-karaoke" not in sys.argv

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = SALIDA_DIR / f"{stamp}_{_slug(tema)}"
    carpeta.mkdir(parents=True, exist_ok=True)

    # 1) GUION (reusar o generar con ficha verificada)
    if reuse:
        _banner("Reusando guion aprobado")
        script = json.loads(Path(reuse).read_text(encoding="utf-8"))
        log.info(f"  Guion: {reuse} — {len(script.get('segmentos', []))} segmentos")
    else:
        from modules import fact_checker
        from modules.narrador_generator import generar_largo

        ficha = ""
        if not sin_ficha:
            _banner("Ficha de datos verificados (web search)")
            ficha = fact_checker.generar_ficha_datos(
                tema, max_uses=6, max_vinetas=20, max_tokens=2000)
            (carpeta / "ficha.txt").write_text(ficha or "[sin ficha]", encoding="utf-8")

        _banner("Escribiendo el guion (narrador)")
        script = generar_largo(tema, ficha_datos=ficha)
        (carpeta / "guion.json").write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"  Guion guardado: {carpeta / 'guion.json'}")

    if tema_color:
        script["tema"] = tema_color

    if script_only:
        _banner("LISTO (solo guion)")
        log.info(f"  Revisa: {carpeta / 'guion.json'}")
        log.info(f"  Para renderizar: python run_largo.py \"{tema}\" "
                 f"--reuse-script \"{carpeta / 'guion.json'}\"")
        return

    # 2) VIDEO (ensamblador: voz + visual + Gato + palabra cinética + música + karaoke)
    _banner("Armando el video")
    from modules.ensamblador_narrador import armar_video
    out = carpeta / f"{_slug(tema)}.mp4"
    ruta = armar_video(script, out, tema=script.get("tema"),
                       con_karaoke=con_karaoke, con_musica=con_musica)
    _banner("LISTO")
    log.info(f"  🎬 {ruta}")
    print(ruta)


if __name__ == "__main__":
    main()
