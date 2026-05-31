"""
PROFESOR GATO — Pipeline Principal v4
Genera automáticamente 1 video educativo por ejecución.

FLUJO:
  1. Detecta tema del día (Google Trends / NewsAPI)
  2. Genera guion con Claude — 6 paneles (Gato + Bastet)
  3. Sintetiza voz por panel con ElevenLabs
  4. Genera imagen pixel art por panel con gpt-image-2 (edit mode)
  5. Anima imágenes con fal.ai Kling 1.6 (parallax)
  5.5. Selecciona clip de personaje por panel (emotion-based)
  6. Genera ambiente sonoro contextual
  7. Ensambla: clip animado + personaje overlay + subtítulos + música → MP4 9:16

USO:
  python main.py                    # Detecta tema automáticamente
  python main.py "La Guerra Fría"   # Tema manual
  python main.py --audio-only       # Solo audio
  python main.py --ref img.png      # Imagen de referencia personalizada

COSTO ESTIMADO POR VIDEO:
  - Script   (Claude Haiku):     ~$0.001
  - Voz      (ElevenLabs × 6):  ~$0.010
  - Imágenes (gpt-image-2 × 6): ~$0.240
  - Animación (Kling × 6):       ~$0.480
  - Total:                       ~$0.731 por video
"""

import os
import sys
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

from modules.cost_monitor         import mostrar_saldo_inicial, registrar_run, mostrar_resumen_run
from modules.cost_tracker         import init_session, session_summary
from modules.trend_detector       import detectar_temas_del_dia, seleccionar_angulo_educativo
from modules.fact_checker         import generar_ficha_datos
from modules.script_generator     import generar_script
from modules.voice_synthesizer    import generar_audios_por_paneles, ajustar_duracion_total
from modules.background_generator import generar_imagenes_por_paneles
from modules.video_animator       import animar_paneles
from modules.video_assembler      import VideoAssemblerV4
from modules.sound_generator      import generar_ambiente
from modules.clip_selector        import elegir_clip_personaje
from modules.music_generator      import generar_musica_lyria

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

_REF_CANDIDATES = [
    BASE_DIR / "images" / "profesor_gato_fondo_negro.png",
    BASE_DIR / "images" / "comic_mar_aral.png",
    BASE_DIR / "images" / "profesor gato fondo negro.png",
    BASE_DIR / "assets"  / "profesor_gato.png",
]
REF_DEFAULT = next((p for p in _REF_CANDIDATES if p.exists()), None)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def banner(texto: str):
    log.info("=" * 60)
    log.info(f"  {texto}")
    log.info("=" * 60)


def guardar_log(datos: dict):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = LOGS_DIR / f"run_{ts}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    log.info(f"Log guardado: {ruta.name}")


def script_a_paneles(script: dict) -> dict:
    """
    Claude genera los paneles directamente en el JSON (campo 'paneles').
    Fallback: divide 'guion' en 3 partes iguales para logs viejos.
    """
    if script.get("paneles"):
        paneles = script["paneles"]
        for i, p in enumerate(paneles, 1):
            p.setdefault("numero", i)
            p.setdefault("speaker", "gato")
            p.setdefault("visual_pizarron", "educational blackboard with diagrams")
            p["duracion_aprox"] = max(4, round(len(p["narracion"].split()) / 3))
        log.info(f"  Paneles: {len(paneles)} (generados por Claude)")
        for p in paneles:
            log.info(f"    Panel {p['numero']} [{p['speaker'].upper()}]: ~{p['duracion_aprox']}s — {p['narracion'][:55]}...")
        return {
            "titulo":      script["titulo"],
            "paneles":     paneles,
            "leccion":     script.get("leccion", ""),
            "musica_mood": script.get("musica_mood", "lofi"),
        }

    # Fallback legacy
    guion = script.get("guion", "").strip()
    pv    = script.get("prompt_visual", "educational blackboard with diagrams")
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", guion) if o.strip()]
    n = len(oraciones)
    base, extra = divmod(n, 3)
    grupos, idx = [], 0
    for g in range(3):
        tam = base + (1 if g < extra else 0)
        grupos.append(oraciones[idx: idx + tam])
        idx += tam
    paneles = [
        {
            "numero": i, "speaker": "gato",
            "narracion": " ".join(gr),
            "visual_pizarron": f"{pv} panel {i}",
            "duracion_aprox": max(4, round(len(" ".join(gr).split()) / 3)),
        }
        for i, gr in enumerate([g for g in grupos if g], start=1)
    ]
    log.info(f"  Paneles: {len(paneles)} (fallback desde guion)")
    return {
        "titulo":      script["titulo"],
        "paneles":     paneles,
        "leccion":     script.get("leccion", ""),
        "musica_mood": script.get("musica_mood", "lofi"),
    }


# ─── PIPELINE PRINCIPAL ───────────────────────────────────────────────────────

def correr_pipeline(
    tema_manual:     str = None,
    skip_video:      bool = False,
    ruta_referencia: str = None,
) -> dict:
    banner("PROFESOR GATO — Pipeline v4")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    mostrar_saldo_inicial()

    # Iniciar registro de costos (escribe en tmp/cost_log.txt)
    init_session(tema=tema_manual or "(tema auto)")

    run_log = {
        "timestamp": datetime.now().isoformat(),
        "version":   "4.0",
        "status":    "running",
        "costos":    {},
    }

    # ── PASO 1: DETECTAR TEMA ─────────────────────────────────────────────────
    banner("PASO 1 — Detectando tema del dia")
    trend_hook = None
    if tema_manual:
        tema = tema_manual
        log.info(f"  Tema manual: {tema}")
    else:
        temas = detectar_temas_del_dia()
        if not temas:
            _TEMAS_RESPALDO = [
                # Historia
                "¿Por qué el Imperio Romano realmente cayó?",
                "La historia de la Conquista de México que no te contaron en la escuela",
                "¿Qué pasó realmente en la noche de Tlatelolco de 1968?",
                "El Imperio Azteca: por qué desapareció en solo 2 años",
                "¿Por qué Napoleón realmente perdió en Waterloo?",
                "La historia de Cleopatra: lo que el cine nunca te mostró",
                "¿Por qué la URSS colapsó en una sola noche?",
                "El Cerro Rico de Potosí: la montaña que financió toda Europa",
                "¿Por qué España perdió todos sus imperios en menos de 100 años?",
                # Ciencia y naturaleza
                "La paradoja de Fermi: ¿dónde están todos los extraterrestres?",
                "¿Por qué se hunde la Ciudad de México y nadie lo detiene?",
                "¿Cómo funciona realmente el cerebro cuando te enamoras?",
                "¿Por qué los dinosaurios eran en realidad muy distintos a como los imaginamos?",
                "El efecto mariposa: cómo un pequeño evento cambia todo",
                "¿Por qué dormimos? La ciencia todavía no lo sabe bien",
                "¿Qué tan cerca estuvimos de extinguirnos como especie?",
                "¿Por qué el agua dulce será la próxima guerra mundial?",
                "Los agujeros negros: lo que realmente sabemos y lo que inventamos",
                # Psicología
                "El experimento de Milgram: por qué la gente obedece órdenes crueles",
                "El experimento de Stanford: cómo el poder corrompe en 6 días",
                "El efecto Dunning-Kruger: por qué los ignorantes se creen expertos",
                "¿Por qué somos tan malos recordando nuestro pasado?",
                "El sesgo de supervivencia: por qué aprendemos de los que ganaron",
                "¿Por qué las redes sociales están diseñadas para hacerte infeliz?",
                "La psicología detrás de los cultos: cómo atrapan a gente inteligente",
                "¿Por qué el miedo vende más que la esperanza?",
                # Deportes y cultura pop
                "¿Por qué México nunca pasa de cuartos de final en Mundiales?",
                "La historia de cómo el fútbol se convirtió en la religión del mundo",
                "¿Por qué los conciertos cuestan cada vez más y nadie puede dejar de ir?",
                "La trampa de los videojuegos: por qué no puedes parar de jugar",
                "¿Cómo se fabrica un hit musical? La fórmula que usan todos",
                "Netflix vs. Hollywood: quién está ganando realmente",
                # Geografía y sociedad
                "¿Por qué los países más felices del mundo están en el norte?",
                "¿Por qué África siendo tan rica tiene tanta pobreza?",
                "¿Por qué Japón tiene los trenes más puntuales del mundo?",
                "La historia de cómo las ciudades matan a sus habitantes sin que lo noten",
                "¿Por qué hay países que simplemente no pueden salir de la pobreza?",
                "¿Por qué India va a ser la próxima superpotencia del mundo?",
                # Tecnología
                "¿Por qué las ciudades inteligentes más avanzadas están en Asia?",
                "La historia de cómo internet casi no existió",
                "¿Por qué tu teléfono sabe más de ti que tú mismo?",
                "El algoritmo que decide lo que piensas sin que lo sepas",
                "¿Quién controla realmente el internet?",
                # Alimentación y salud
                "¿Por qué el azúcar es tan adictiva como la cocaína?",
                "La historia de cómo Coca-Cola conquistó el mundo",
                "¿Por qué la comida rápida es más barata que comer sano?",
                "El negocio detrás de las dietas: por qué ninguna funciona a largo plazo",
                # Arte, música e idiomas
                "¿Por qué el español es el idioma que más crece en el mundo?",
                "La historia de cómo el reggaetón tomó el control del mundo",
                "¿Por qué el arte moderno vale millones y nadie lo entiende?",
                "¿Cómo una canción puede cambiar el curso de una guerra?",
                # Filosofía y pensamiento
                "¿Existe el libre albedrío o todo está determinado?",
                "La trampa de la felicidad: por qué nunca llegamos a ser felices",
                "¿Qué pasaría si todos los robots hicieran nuestro trabajo?",
                "El problema del tranvía: por qué la ética no tiene respuestas fáciles",
                # Economía (variado)
                "¿Por qué Colombia tiene tantas constituciones?",
                "La maldición del petróleo: por qué el oro negro destruye países",
                "La guerra del agua de Bolivia: cuando privatizaron la lluvia",
                "¿Por qué el Titanic realmente se hundió? (no fue el iceberg)",
                "¿Por qué Argentina entra en crisis económica cada 10 años?",
            ]
            import datetime as _dt
            _dia = _dt.date.today().timetuple().tm_yday
            tema = _TEMAS_RESPALDO[_dia % len(_TEMAS_RESPALDO)]
            log.warning(f"Sin temas detectados. Usando respaldo rotativo (día {_dia}): {tema}")
        else:
            log.info("  Seleccionando angulo educativo a partir de tendencias...")
            try:
                angulo = seleccionar_angulo_educativo(temas)
                tema = angulo["angulo_educativo"] or temas[0]["tema"]
                trend_hook = angulo.get("trend_conectado")
                log.info(f"  Trend viral:      {trend_hook}")
                log.info(f"  Angulo educativo: {tema}")
                log.info(f"  Razon:            {angulo.get('razon', '')}")
            except Exception as e:
                log.warning(f"  seleccionar_angulo_educativo fallo ({e}) — usando top trend directo")
                tema = temas[0]["tema"]
    run_log["tema"] = tema
    run_log["trend_hook"] = trend_hook

    # ── PASO 2: VERIFICAR HECHOS (web search) ─────────────────────────────────
    banner("PASO 2 — Verificando hechos (web search)")
    ficha_datos = generar_ficha_datos(tema)
    if ficha_datos:
        log.info(f"  Ficha de datos verificados:\n{ficha_datos[:400]}...")
    else:
        log.warning("  Sin ficha verificada — el guion se genera sin verificación web")
    run_log["ficha_datos"] = ficha_datos

    # ── PASO 2b: GENERAR SCRIPT ───────────────────────────────────────────────
    banner("PASO 2b — Generando script (Claude)")
    contexto_trend = (
        f"Hoy está trending en México/LATAM: '{trend_hook}'. "
        "El video debe conectarse naturalmente a ese momento sin ser una noticia directa."
        if trend_hook else ""
    )
    script = generar_script(tema, contexto_extra=contexto_trend, datos_verificados=ficha_datos)
    log.info(f"  Titulo:  {script['titulo']}")
    log.info(f"  Leccion: {script['leccion']}")
    total_w = (
        sum(len(p["narracion"].split()) for p in script["paneles"])
        if script.get("paneles")
        else len(script.get("guion", "").split())
    )
    log.info(f"  Palabras: {total_w}")
    run_log["script"] = script
    run_log["costos"]["script_usd"] = 0.001

    # ── PASO 3: ESTRUCTURAR PANELES ───────────────────────────────────────────
    banner("PASO 3 — Estructurando paneles")
    datos_comic = script_a_paneles(script)
    run_log["paneles"] = len(datos_comic["paneles"])

    # ── PASO 4: SINTETIZAR VOZ ────────────────────────────────────────────────
    banner("PASO 4 — Sintetizando voz (ElevenLabs)")
    resultados_audio = generar_audios_por_paneles(datos_comic)
    # Garantizar que el video sea un Short válido (< 60s): si la narración se
    # pasa, se aceleran los audios ligeramente para no superar MAX_SHORT_DURATION.
    from config import MAX_SHORT_DURATION
    resultados_audio = ajustar_duracion_total(resultados_audio, MAX_SHORT_DURATION)
    run_log["costos"]["audio_usd"] = 0.010
    run_log["audios"] = [r["ruta_audio"] for r in resultados_audio]
    run_log["duracion_audio_s"] = round(sum(r["duracion_real"] for r in resultados_audio), 1)
    log.info(f"  {len(resultados_audio)} audios generados ({run_log['duracion_audio_s']}s total)")

    if skip_video:
        run_log["status"] = "success_audio_only"
        guardar_log(run_log)
        return run_log

    slug = (
        script["titulo"][:35]
        .replace(" ", "_")
        .replace("?", "").replace("¿", "")
        .replace("!", "").replace("¡", "")
        .replace(":", "").replace(",", "")
    )
    output_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug}"

    # ── PASO 5: GENERAR IMAGENES (gpt-image-2) ────────────────────────────────
    banner("PASO 5 — Generando imagenes pixel art (gpt-image-2)")
    ref = Path(ruta_referencia) if ruta_referencia else REF_DEFAULT
    if ref is None or not ref.exists():
        raise FileNotFoundError(
            "No se encontro imagen de referencia del Profesor Gato.\n"
            "Coloca una imagen en: images/profesor_gato_fondo_negro.png"
        )
    log.info(f"  Referencia: {ref.name}")
    resultados_img = generar_imagenes_por_paneles(datos_comic, str(ref))
    run_log["costos"]["imagenes_usd"] = round(0.040 * len(datos_comic["paneles"]), 3)
    run_log["imagenes"] = [r["ruta_imagen"] for r in resultados_img]
    log.info(f"  {len(resultados_img)} imagenes generadas")

    # ── PASO 5.5: ANIMAR CON KLING ────────────────────────────────────────────
    banner("PASO 5.5 — Animando paneles (fal.ai Kling 1.6)")
    resultados_anim = animar_paneles(resultados_img, datos_comic)
    animados = sum(1 for r in resultados_anim if r["ruta_video"])
    run_log["costos"]["animacion_usd"] = round(0.08 * animados, 3)
    run_log["clips_animados"] = animados
    log.info(f"  {animados}/{len(resultados_anim)} paneles animados")

    # ── PASO 5.7: SELECCIONAR CLIPS DE PERSONAJE ──────────────────────────────
    banner("PASO 5.7 — Seleccionando clips de personaje")
    clips_personaje = []
    for panel in datos_comic["paneles"]:
        clip = elegir_clip_personaje(panel["numero"], panel.get("speaker", "gato"))
        clips_personaje.append(clip)
        log.info(f"  Panel {panel['numero']} [{panel.get('speaker','gato').upper()}]: {clip.name}")

    # ── PASO 5.8: AMBIENTE SONORO ─────────────────────────────────────────────
    banner("PASO 5.8 — Generando ambiente sonoro")
    ambiente_desc = script.get("ambiente_sonoro", "")
    musica_path = None
    if ambiente_desc:
        duracion_total_audio = sum(r["duracion_real"] for r in resultados_audio)
        ruta_ambiente = BASE_DIR / "tmp" / f"ambiente_{output_name}.mp3"
        try:
            musica_path = generar_ambiente(ambiente_desc, duracion_total_audio,
                                           ruta_ambiente, tema=tema)
            log.info(f"  Ambiente: {musica_path.name}")
        except Exception as e:
            log.warning(f"  No se pudo generar ambiente: {e}")
    else:
        log.info("  Sin ambiente_sonoro en script — usando assets/music/")

    # ── PASO 5.9: MÚSICA LYRIA 3 ─────────────────────────────────────────────
    banner("PASO 5.9 — Generando música contextual (Lyria 3)")
    musica_mood = datos_comic.get("musica_mood", "lofi")
    duracion_total_audio = sum(r["duracion_real"] for r in resultados_audio)
    lyria_path = generar_musica_lyria(musica_mood, tema, duracion_total_audio)
    if lyria_path:
        log.info(f"  Lyria 3: {lyria_path.name}")
    else:
        log.info(f"  Lyria 3 no disponible — se usarán tracks estáticos [{musica_mood}]")

    # ── PASO 6: ENSAMBLAR VIDEO ───────────────────────────────────────────────
    banner("PASO 6 — Ensamblando video final")
    paneles = [
        {
            "numero":         audio_r["numero"],
            "speaker":        audio_r.get("speaker", "gato"),
            "ruta_audio":     audio_r["ruta_audio"],
            "ruta_imagen":    anim_r["ruta_imagen"],
            "ruta_video":     anim_r["ruta_video"],
            "clip_personaje": str(clip),
        }
        for audio_r, anim_r, clip in zip(resultados_audio, resultados_anim, clips_personaje)
    ]

    assembler  = VideoAssemblerV4(musica_mood=musica_mood)
    ruta_video = assembler.ensamblar(paneles, output_name=output_name,
                                     musica_path=musica_path, lyria_path=lyria_path)
    run_log["ruta_video"] = str(ruta_video)
    size_mb = ruta_video.stat().st_size / 1024 / 1024
    log.info(f"  Video: {ruta_video.name} ({size_mb:.1f} MB)")

    # ── PASO 7: PUBLICACION ───────────────────────────────────────────────────
    banner("PASO 7 — Publicacion [PROXIMAMENTE]")
    log.info(f"  Titulo:      {script['titulo']}")
    log.info(f"  Descripcion: {script.get('descripcion_social', '')[:80]}")
    log.info(f"  Hashtags:    {' '.join(script.get('hashtags', []))}")
    log.info("  -> TikTok / YouTube Shorts / Instagram Reels")

    # ── RESUMEN ───────────────────────────────────────────────────────────────
    costo_total = sum(run_log["costos"].values())
    run_log["costos"]["total_usd"] = round(costo_total, 4)
    run_log["status"] = "success"

    banner("PIPELINE COMPLETADO")
    log.info(f"  Tema:    {tema[:55]}")
    log.info(f"  Titulo:  {script['titulo']}")
    log.info(f"  Video:   {ruta_video.name} ({size_mb:.1f} MB)")
    log.info(f"  Leccion: {script['leccion']}")
    log.info(f"  Costo:   ~${costo_total:.3f} USD")
    log.info("=" * 60)

    # Cerrar sesión de costos — escribe totales al log
    costos_reales = session_summary()
    run_log["costos"]["total_real_usd"] = costos_reales["total_usd"]
    run_log["costos"]["desglose"]       = costos_reales["por_tipo"]
    log.info(f"  Cost log: tmp/cost_log.txt")

    guardar_log(run_log)
    registrar_run(run_log)
    mostrar_resumen_run(run_log)
    return run_log


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = list(sys.argv[1:])

    skip_video = "--audio-only" in args
    if skip_video:
        args.remove("--audio-only")

    ruta_ref = None
    if "--ref" in args:
        i = args.index("--ref")
        ruta_ref = args[i + 1]
        args = args[:i] + args[i + 2:]

    tema = " ".join(args) if args else None

    resultado = correr_pipeline(
        tema_manual=tema,
        skip_video=skip_video,
        ruta_referencia=ruta_ref,
    )
    sys.exit(0 if resultado.get("status", "").startswith("success") else 1)
