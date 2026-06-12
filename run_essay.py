"""
run_essay.py — Pipeline de VIDEO-ENSAYO LARGO de ECONOMÍA (Profesor Gato)

Formato YouTube horizontal 16:9, 8-10 min. Dúo Gato/Bastet + tarjetas de datos
verificados (fact_checker con web search). MANUAL: NO va al scheduler; por defecto
GENERA y NO publica (Luigi revisa; se publica con --publish o ad-hoc).

NO toca el pipeline de Shorts en producción. Solo usa módulos compartidos en modo
lectura (fact_checker, background_generator, music_generator — extendidos de forma
aditiva) y escribe a videos_largos/.

USO:
  python run_essay.py "el negocio del mundial" --script-only   # ficha + guion (barato, para revisar)
  python run_essay.py "el negocio del mundial"                 # genera el video completo
  python run_essay.py "el negocio del mundial" --reuse-script audio/ESSAY_X   # guion ya aprobado → voz+render
  python run_essay.py "el negocio del mundial" --reuse-audio  audio/ESSAY_X   # re-render sin re-pagar voz
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

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("run_essay")

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _slug(t: str) -> str:
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return re.sub(r"[\s]+", "_", t.strip())


# ── OUTLINES CURADOS (flujo híbrido: Claude propone → Luigi aprueba) ──────────
OUTLINES = {
    # El negocio del Mundial. Validado por el video TOP del canal ("boletos
    # imposibles", 756 vistas + comentarios de rabia). Indignación CON datos:
    # cada cifra sale de la ficha verificada; lo no verificado se narra como
    # pregunta. Cuidado EVERGREEN: el Mundial 2026 se menciona en presente
    # histórico (nada de "la próxima semana" ni resultados de partidos).
    "el negocio del mundial": {
        "nota": ("La promesa del título se empieza a responder en el PRIMER minuto. "
                 "Tono: indignación LEGÍTIMA con datos — nunca amargura ni 'no veas el "
                 "Mundial': el espectador AMA el fútbol, y justo por eso merece saber "
                 "quién factura con esa emoción. Cierre lúcido, no derrotista. "
                 "EVERGREEN: prohibido 'mañana'/'esta semana'/resultados de partidos; "
                 "el Mundial 2026 en México/Azteca se narra como hecho histórico."),
        "capitulos": [
            {"capitulo": "La fiesta que pagas tú",
             "notas": ("el contraste fundador: la FIFA organiza la fiesta y se lleva la "
                       "ganancia; el país anfitrión pone estadios, seguridad e "
                       "infraestructura con dinero público; cifras de ingresos del ciclo "
                       "mundialista de la FIFA vs. gasto público del anfitrión (las que "
                       "confirme la ficha)")},
            {"capitulo": "El boleto imposible",
             "notas": ("el ángulo que ya indignó a la audiencia del canal: precios "
                       "dinámicos de boletos del Mundial 2026, cuántos salarios mínimos "
                       "mexicanos cuesta ir a un partido, la reventa oficializada; el "
                       "aficionado de toda la vida viendo el estadio de su ciudad por "
                       "TV porque entrar cuesta lo que no gana en un mes")},
            {"capitulo": "La derrama que no llega",
             "notas": ("el mito de la 'derrama económica': qué prometen los gobiernos y "
                       "qué encuentran los estudios después; elefantes blancos (estadios "
                       "de mundiales pasados abandonados o subutilizados, los casos que "
                       "la ficha confirme, ej. Brasil 2014 / Sudáfrica 2010); quién paga "
                       "el mantenimiento cuando la fiesta se va; CTA de mitad al cerrar "
                       "este capítulo")},
            {"capitulo": "Los dueños del negocio",
             "notas": ("a dónde va cada peso: derechos de TV, patrocinadores, hospitalidad "
                       "corporativa; la exención de impuestos que la FIFA exige a los "
                       "países sede (si la ficha lo confirma, es LA tarjeta de datos del "
                       "video); Bastet pregunta lo que todos: '¿y por qué los países "
                       "aceptan?' — la respuesta política/emocional")},
            {"capitulo": "Tu Mundial de todos modos",
             "notas": ("aterrizaje personal: qué significa para TI — verlo claro no te "
                       "quita la fiesta, te quita la ingenuidad; la emoción es tuya y "
                       "esa no factura nadie; pregunta final para comentar (¿irías a un "
                       "partido a ese precio?)")},
        ],
    },
}

# Enfoque de búsqueda del fact_checker por tema (qué cifras necesita el guion).
FICHA_ENFOQUE = {
    "el negocio del mundial": (
        "- Ingresos de la FIFA en el ciclo del Mundial 2026 (proyección o cifra oficial)\n"
        "- Ingresos reales de la FIFA en el ciclo de Qatar 2022\n"
        "- Precios de boletos del Mundial 2026 (rango, precios dinámicos) y salario "
        "mínimo mensual en México 2026\n"
        "- Gasto público de México/sedes en estadios e infraestructura para 2026\n"
        "- Exención de impuestos que la FIFA exige a países sede (¿aplica en México 2026?)\n"
        "- Estudios sobre 'derrama económica' real de mundiales pasados vs. lo prometido\n"
        "- Elefantes blancos: estadios de Brasil 2014 / Sudáfrica 2010 hoy\n"
        "- Reparto: cuánto de los ingresos viene de derechos de TV y patrocinios"
    ),
}


def banner(t):
    log.info("=" * 60); log.info(f"  {t}"); log.info("=" * 60)


def _cargar_audios_existentes(carpeta: str, segmentos: list[dict]) -> list[dict]:
    """Reusa voz ya generada (bloque_*.mp3 + palabras.json) sin re-pagar ElevenLabs."""
    from modules.essay_voice import obtener_duracion_audio
    carpeta = Path(carpeta)
    mp3s = sorted(carpeta.glob("bloque_*.mp3"))
    if not mp3s:
        raise RuntimeError(f"No hay bloque_*.mp3 en {carpeta}")
    palabras_map = {}
    pj = carpeta / "palabras.json"
    if pj.exists():
        try:
            palabras_map = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            palabras_map = {}
    audios = []
    for i, p in enumerate(mp3s, 1):
        speaker = segmentos[i - 1].get("speaker", "gato") if i <= len(segmentos) else "gato"
        audios.append({"numero": i, "speaker": speaker, "ruta_audio": str(p),
                       "duracion_real": obtener_duracion_audio(str(p)),
                       "palabras": palabras_map.get(str(i), [])})
    log.info(f"  Reusando {len(audios)} audios de {carpeta}")
    return audios


def _generar_fondos(segmentos: list[dict], carpeta: Path) -> list[str]:
    """Un fondo 16:9 por LOCATION única (cache: segmentos consecutivos con la misma
    location comparten imagen → menos costo y más continuidad visual)."""
    from modules.background_generator import generar_imagen_essay
    carpeta.mkdir(parents=True, exist_ok=True)
    cache: dict[str, str] = {}
    rutas = []
    for s in segmentos:
        loc = s["location"]
        if loc not in cache:
            idx = len(cache) + 1
            log.info(f"  [bg {idx}] {loc[:70]}")
            cache[loc] = generar_imagen_essay(loc, carpeta / f"bg_{idx:02d}.png")
        rutas.append(cache[loc])
    log.info(f"  {len(cache)} fondos únicos para {len(segmentos)} segmentos")
    return rutas


def _fmt_ts(seg: float) -> str:
    m = int(seg // 60); s = int(seg % 60)
    return f"{m}:{s:02d}"


def correr_essay(tema: str, publicar: bool = False, reuse_audio: str = "",
                 reuse_script: str = "", script_only: bool = False) -> dict:
    banner(f"VIDEO-ENSAYO DE ECONOMÍA — {tema}")
    clave = tema.strip().lower()
    outline = OUTLINES.get(clave)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if reuse_audio or reuse_script:
        carpeta_audio = reuse_audio or reuse_script
        banner(f"PASO 1 — Reusando guion de {carpeta_audio}")
        script = json.loads((Path(carpeta_audio) / "script.json").read_text(encoding="utf-8"))
        segmentos = script["segmentos"]
    else:
        # ── 1a. FICHA DE DATOS VERIFICADOS (web search — el alma del formato) ──
        banner("PASO 1a — Fact-check con búsqueda web")
        from modules.fact_checker import generar_ficha_datos
        ficha = generar_ficha_datos(tema, max_uses=6, max_vinetas=20, max_tokens=2000,
                                    enfoque=FICHA_ENFOQUE.get(clave, ""))
        if ficha:
            log.info(f"  Ficha verificada:\n{ficha}")
        else:
            log.warning("  ⚠ Sin ficha — el guion NO afirmará cifras (revisar antes de publicar)")

        # ── 1b. GUION ──────────────────────────────────────────────────────
        banner("PASO 1b — Guion del ensayo (Claude, dúo + tarjetas de datos)")
        from modules.essay_script_generator import generar_essay
        script = generar_essay(tema, outline=outline, ficha_datos=ficha)
        segmentos = script["segmentos"]
        carpeta_audio = f"audio/ESSAY_{_slug(script['titulo'])[:30]}_{ts}"
        Path(carpeta_audio).mkdir(parents=True, exist_ok=True)
        Path(carpeta_audio, "script.json").write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        if ficha:
            Path(carpeta_audio, "ficha_datos.txt").write_text(ficha, encoding="utf-8")
        log.info(f"  Guion + ficha guardados en {carpeta_audio}")

    titulo = script["titulo"]

    if script_only:
        banner("GUION LISTO (modo --script-only, no se gastó voz/imágenes)")
        log.info(f"  Título: {titulo}")
        for s in segmentos:
            d = f"  [💳 {s['dato']['cifra']}]" if s.get("dato") else ""
            log.info(f"  {s['numero']:02d} [{s['speaker']:6s}] ({s.get('capitulo','')}) "
                     f"{s['narracion'][:70]}...{d}")
        log.info(f"\n  Revisa {carpeta_audio}/script.json y luego corre:\n"
                 f"  python run_essay.py \"{tema}\" --reuse-script {carpeta_audio}")
        return {"status": "script_only", "carpeta": str(carpeta_audio), "titulo": titulo}

    # ── 2. VOZ (dúo, timestamps exactos) ───────────────────────────────────
    if reuse_audio:
        audios = _cargar_audios_existentes(reuse_audio, segmentos)
    else:
        banner("PASO 2 — Voz (ElevenLabs: Gato + Bastet, timestamps)")
        from modules.essay_voice import generar_audios_essay
        audios = generar_audios_essay(segmentos, carpeta_salida=carpeta_audio)

    # ── 3. FONDOS 16:9 (Imagen, cache por location) ────────────────────────
    banner("PASO 3 — Fondos pixel art 16:9 (Imagen, cache por location)")
    carpeta_imgs = BASE_DIR / "images" / f"ESSAY_{_slug(titulo)[:30]}_{ts}"
    fondos = _generar_fondos(segmentos, carpeta_imgs)

    # ── 4. MÚSICA por capítulo (Lyria, identidad situacional del guion) ────
    banner("PASO 4 — Música por capítulo (Lyria)")
    mood = script.get("musica_mood", "economia")
    caps = []
    for s in segmentos:
        c = s.get("capitulo", "") or "Capítulo"
        if not caps or caps[-1] != c:
            if c not in caps:
                caps.append(c)
    palette = [mood, "tension", "ambient_misterioso", "dramatico", "lofi"]
    palette = list(dict.fromkeys(palette))
    sin_musica_idx = len(caps) // 2 if len(caps) >= 4 else -1
    musica_por_capitulo = {}
    try:
        from modules.music_generator import generar_musica_lyria
        beds = {}
        for i, c in enumerate(caps):
            if i == sin_musica_idx:
                musica_por_capitulo[c] = None
                log.info(f"  Capítulo '{c}': SIN música (contraste)")
                continue
            mm = palette[i % len(palette)]
            if mm not in beds:
                beds[mm] = generar_musica_lyria(
                    mm, f"{tema} — {mm}", 45,
                    prompt_situacional=script.get("musica_prompt", ""))
                log.info(f"  Bed '{mm}': {beds[mm].name if beds[mm] else 'falló'}")
            musica_por_capitulo[c] = beds.get(mm)
    except Exception as e:
        log.warning(f"  Lyria falló ({e}) — ensayo sin música.")
        musica_por_capitulo = {}

    # ── 5. ENSAMBLE 16:9 ───────────────────────────────────────────────────
    banner("PASO 5 — Ensamble 16:9 (tarjetas de datos + personajes + subtítulos)")
    from modules.essay_assembler import EssayAssembler
    bloques = []
    for a, s, img in zip(audios, segmentos, fondos):
        bloques.append({"numero": a["numero"], "ruta_audio": a["ruta_audio"],
                        "ruta_imagen": img, "palabras": a.get("palabras", []),
                        "speaker": s.get("speaker", "gato"), "pose": s.get("pose"),
                        "dato": s.get("dato"), "capitulo": s.get("capitulo", "")})
    output_name = f"{ts}_ESSAY_{_slug(titulo)[:35]}"
    assembler = EssayAssembler()
    ruta_video, capitulos = assembler.ensamblar(bloques, titulo=titulo,
                                                musica_por_capitulo=musica_por_capitulo,
                                                output_name=output_name)

    chap_lines = "\n".join(f"{_fmt_ts(c['t'])} {c['titulo']}" for c in capitulos)
    descripcion = (f"{script.get('descripcion','')}\n\n⏱️ Capítulos:\n{chap_lines}\n\n"
                   + " ".join(h for h in script.get("hashtags", []) if h.lower() != "#shorts"))

    run_log = {"timestamp": datetime.now().isoformat(), "tipo": "ensayo_largo",
               "tema": tema, "titulo": titulo, "ruta_video": str(ruta_video),
               "carpeta_audio": str(carpeta_audio), "capitulos": capitulos,
               "descripcion": descripcion, "status": "success"}
    (LOGS_DIR / f"essay_{ts}.json").write_text(
        json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")

    banner("ENSAYO LISTO")
    log.info(f"  Título: {titulo}")
    log.info(f"  Video:  {ruta_video}")
    log.info(f"  Capítulos:\n{chap_lines}")

    # ── 6. PUBLICAR (solo con --publish; manual) ───────────────────────────
    if publicar:
        banner("PASO 6 — Publicar en YouTube (video normal, NO Short)")
        from publisher import subir_a_youtube, publicar_comentario
        tags = list(dict.fromkeys(
            [t for t in tema.split() if len(t) > 3]
            + [h.lstrip("#") for h in script.get("hashtags", []) if h.lower() != "#shorts"]
        ))[:30]
        metadata = {"titulo": titulo[:100], "descripcion": descripcion,
                    "tags": tags, "tema": tema}
        res = subir_a_youtube(Path(ruta_video), metadata, dry_run=False)
        if res.get("_youtube"):
            publicar_comentario(res["_youtube"], res["video_id"], metadata, {"script": script})
        run_log["url"] = res.get("url", "")
        log.info(f"  ✅ Publicado: {res.get('url','')}")
    else:
        log.info("  (sin --publish) — video en videos_largos/. Revísalo y publica "
                 "con --reuse-audio + --publish, o ad-hoc con publisher.subir_a_youtube.")
    return run_log


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    publicar = "--publish" in args
    if publicar:
        args.remove("--publish")
    script_only = "--script-only" in args
    if script_only:
        args.remove("--script-only")
    reuse_audio = reuse_script = ""
    if "--reuse-audio" in args:
        i = args.index("--reuse-audio")
        reuse_audio = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    if "--reuse-script" in args:
        i = args.index("--reuse-script")
        reuse_script = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    tema = " ".join(args).strip() or "el negocio del mundial"
    correr_essay(tema, publicar=publicar, reuse_audio=reuse_audio,
                 reuse_script=reuse_script, script_only=script_only)
