"""
selector_visual.py — Selector de VISUAL REAL por segmento (motor visual v2, largos)
Proyecto: Profesor Gato

Por cada segmento del guion-narrador (ver prompts/system_prompt_narrador.txt) elige
la MEJOR imagen o clip REAL, con cadena de respaldo para que NUNCA quede un hueco:

  tipo "foto_persona/foto_evento/foto_lugar/cuadro" → Wikimedia Commons (foto real)
  tipo "footage"                                    → topical_footage (clip CC muteado)
  tipo "mapa"                                       → mapa real de Wikimedia (TODO: animado)
  tipo "grafica"                                    → la dibuja el ensamblador desde `datos`
  tipo "gato_bumper"                                → sprite del Profesor Gato (sello)
  tipo "escena_ia"                                  → Nano Banana (SOLO si no hay nada real)

Respaldo general: foto → footage → escena_ia → foto del tema. Devuelve un dict con la
ruta y metadatos para que el ensamblador sepa cómo moverla (parallax/zoom) y qué palabra
dorada mostrar.
"""
import logging
import shutil
from pathlib import Path

from modules import wikimedia_fetcher, topical_footage, background_generator
try:
    from modules import pexels_fetcher
except Exception:
    pexels_fetcher = None
try:
    from modules import pixabay_fetcher
except Exception:
    pixabay_fetcher = None
try:
    from modules import openverse_fetcher
except Exception:
    openverse_fetcher = None


def _stock_video(query: str, out_mp4) -> str | None:
    """B-roll de los bancos (Pexels → Pixabay), el primero que tenga key y resultado."""
    for mod in (pexels_fetcher, pixabay_fetcher):
        if mod and mod.disponible():
            r = mod.buscar_video(query, out_mp4)
            if r:
                return r
    return None


def _stock_foto(query: str, out_jpg) -> tuple[str | None, str]:
    """Foto de los bancos (Pexels → Pixabay → Openverse). Devuelve (ruta, fuente)."""
    for mod, nombre in ((pexels_fetcher, "pexels_foto"),
                        (pixabay_fetcher, "pixabay_foto"),
                        (openverse_fetcher, "openverse_cc")):
        if mod and mod.disponible():
            r = mod.buscar_foto(query, out_jpg)
            if r:
                return r, nombre
    return None, ""

log = logging.getLogger("selector_visual")

BASE_DIR = Path(__file__).parent.parent
GATO_PNG = BASE_DIR / "assets" / "profesor_gato.png"

# Tipos que se resuelven buscando una FOTO real en Wikimedia.
_TIPOS_FOTO = {"foto_persona", "foto_evento", "foto_lugar", "cuadro"}

_CONECTORES = {"de", "del", "la", "las", "los", "y", "da", "van", "von", "e"}


def _nombre_limpio(query: str) -> str:
    """Extrae el NOMBRE PROPIO (tokens capitalizados iniciales) de una query, para
    que Wikimedia no traiga a otra persona por las palabras extra. Ej.: 'Gabriel
    García Márquez joven escritor' → 'Gabriel García Márquez'."""
    out = []
    for t in (query or "").split():
        if t[:1].isupper():
            out.append(t)
        elif t.lower() in _CONECTORES and out:
            out.append(t)
        else:
            break
    while out and out[-1].lower() in _CONECTORES:
        out.pop()
    nombre = " ".join(out)
    return nombre if len(out) >= 2 else query


# ─── Fuentes ──────────────────────────────────────────────────────────────────

def _via_wikimedia(query: str, out_jpg: Path) -> str | None:
    try:
        # Carpeta temporal ÚNICA por segmento: evita que un segmento reuse la foto
        # descargada por otro (wikimedia_fetcher cachea como wiki_00.jpg).
        tmp = Path(out_jpg).parent / f"_wiki_{Path(out_jpg).stem}"
        return wikimedia_fetcher.fondo_16x9(query, out_jpg, carpeta_tmp=tmp)
    except Exception as e:
        log.warning(f"  [wiki] '{query[:40]}': {e}")
        return None


def _via_footage(query: str, out_dir: Path) -> str | None:
    try:
        return str(topical_footage.descargar_footage_cc(query, dest_dir=out_dir))
    except Exception as e:
        log.info(f"  [footage] sin clip para '{query[:40]}': {e}")
        return None


def _via_escena(query: str, out_jpg: Path) -> str | None:
    try:
        return background_generator.generar_imagen_essay(query, out_jpg)
    except Exception as e:
        log.warning(f"  [escena_ia] '{query[:40]}': {e}")
        return None


# ─── Selector ─────────────────────────────────────────────────────────────────

def obtener_visual(visual: dict, tema: str, out_dir: Path, idx: int) -> dict:
    """
    Resuelve el visual de UN segmento. Devuelve:
      {ruta, es_video, tipo_pedido, tipo_real, fuente, movimiento, clave, query}
    `ruta` None solo en 'grafica' (la dibuja el ensamblador) o si todo falló.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    visual = visual or {}
    tipo = visual.get("tipo") or "foto_lugar"
    query = (visual.get("query") or tema).strip()
    img_out = out_dir / f"seg_{idx:03d}.jpg"

    def R(ruta, fuente, es_video=False, tipo_real=None):
        return {
            "ruta":        str(ruta) if ruta else None,
            "es_video":    es_video,
            "tipo_pedido": tipo,
            "tipo_real":   tipo_real or (tipo if ruta else "sin_visual"),
            "fuente":      fuente if ruta else None,
            "movimiento":  visual.get("movimiento", "parallax"),
            "clave":       visual.get("clave"),
            "query":       query,
        }

    # 1) Gato como sello
    if tipo == "gato_bumper":
        if GATO_PNG.exists():
            dest = out_dir / f"seg_{idx:03d}_gato.png"
            shutil.copy(GATO_PNG, dest)
            return R(dest, "gato_sprite", tipo_real="gato_bumper")
        # sin sprite → sigue a escena_ia abajo

    # 2) Gráfica: la renderiza el ensamblador desde `datos`; aquí no bajamos imagen.
    if tipo == "grafica":
        return R(None, None, tipo_real="grafica")

    # 3) Footage / b-roll real. Bancos de stock (Pexels/Pixabay video) PRIMERO.
    if tipo == "footage":
        r = _stock_video(query, out_dir / f"seg_{idx:03d}.mp4")
        if r:
            return R(r, "stock_video", es_video=True)
        rf, fuente = _stock_foto(query, img_out)
        if rf:
            return R(rf, fuente)
        r = _via_footage(query, out_dir)
        if r:
            return R(r, "topical_footage_cc", es_video=True)
        r = _via_wikimedia(query, img_out)
        if r:
            return R(r, "wikimedia", tipo_real="foto_lugar")
        return R(_via_escena(query, img_out), "escena_ia", tipo_real="escena_ia")

    # 4) Mapa ESTILIZADO con identidad del canal (modules/mapa.py). Respaldo: foto del lugar.
    if tipo == "mapa":
        from modules import mapa as _mapa
        # La query puede venir sucia ("Colombia municipios masacres"); probamos el
        # texto completo y luego el/los nombres propios, para que SIEMPRE salga el
        # mapa estilizado del PAÍS y no un mapa regional feo de Wikimedia.
        caps = " ".join(t for t in query.split() if t[:1].isupper())
        intentos = [q for q in (query, caps, query.split()[0] if query.split() else "") if q]
        r = None
        for q in dict.fromkeys(intentos):           # sin duplicados, en orden
            try:
                r = _mapa.generar_mapa(q, str(img_out.with_suffix(".png")))
            except Exception as e:
                log.warning(f"  [mapa] {q[:40]}: {e}")
                r = None
            if r:
                return R(r, "mapa_identidad", tipo_real="mapa")
        # sin mapa estilizado: NO traemos un mapa random de Wikimedia (sale feo) →
        # mejor una escena generada coherente del lugar.
        return R(_via_escena(f"map of {query}, clean stylized", img_out),
                 "escena_ia", tipo_real="escena_ia")

    # 4a) NOVELA: personaje/escena de la obra (Aureliano, Pilar Ternera, Macondo, las
    #     bananeras) con estilo CINE. Primero un asset generado por Luigi en
    #     assets/novela/<slug>.(png|jpg); si no existe, se GENERA cinematográfico.
    if tipo == "novela":
        import re as _re
        qlow = (query or "").lower()
        slug = _re.sub(r"[^\w]+", "_", qlow).strip("_")[:50]
        nov_dir = BASE_DIR / "assets" / "novela"
        nov_dir.mkdir(parents=True, exist_ok=True)
        # 1) match EXACTO por slug de la query
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            cand = nov_dir / f"{slug}{ext}"
            if cand.exists():
                dest = out_dir / f"seg_{idx:03d}{ext}"
                shutil.copy(cand, dest)
                return R(dest, "novela_asset", tipo_real="novela")
        # 2) match por KEYWORD: si guardas 'aureliano.png', cualquier query con
        #    'aureliano' lo usa (nombres simples, sin copiar el slug largo).
        for f in sorted(nov_dir.glob("*.*")):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                clave = f.stem.lower().replace("_", " ").strip()
                if clave and clave in qlow:
                    dest = out_dir / f"seg_{idx:03d}{f.suffix}"
                    shutil.copy(f, dest)
                    return R(dest, "novela_asset", tipo_real="novela")
        prompt = (f"{query}, One Hundred Years of Solitude Netflix series style, "
                  f"cinematic film still, dramatic warm lighting, photorealistic, "
                  f"Colombian magical realism, shallow depth of field")
        return R(_via_escena(prompt, img_out), "escena_ia", tipo_real="escena_ia")

    # 4b) Cultura pop (personaje de serie/película/juego): Wikimedia (actor/obra) →
    #     si no hay, se GENERA un "film still" cinematográfico coherente con la escena.
    if tipo == "foto_cultura":
        r = _via_wikimedia(query, img_out)
        if r:
            return R(r, "wikimedia", tipo_real="foto_cultura")
        prompt = (f"{query}, cinematic film still, dramatic cinematic lighting, "
                  f"photorealistic, movie scene, shallow depth of field")
        return R(_via_escena(prompt, img_out), "escena_ia", tipo_real="escena_ia")

    # 5) Fotos / cuadros (lo más común): Wikimedia → bancos stock → footage → escena_ia.
    if tipo in _TIPOS_FOTO:
        # Para una PERSONA famosa, busca solo el nombre propio (las palabras extra
        # tipo "joven escritor" hacen que Wikimedia traiga a otro señor).
        q_wiki = _nombre_limpio(query) if tipo == "foto_persona" else query
        r = _via_wikimedia(q_wiki, img_out)
        if r:
            return R(r, "wikimedia")
        rf, fuente = _stock_foto(query, img_out)
        if rf:
            return R(rf, fuente)
        r = _via_footage(query, out_dir)
        if r:
            return R(r, "topical_footage_cc", es_video=True, tipo_real="footage")
        return R(_via_escena(query, img_out), "escena_ia", tipo_real="escena_ia")

    # 6) escena_ia explícita o cualquier otro tipo: IA, con último respaldo Wikimedia del tema.
    r = _via_escena(query, img_out)
    if r:
        return R(r, "escena_ia", tipo_real="escena_ia")
    return R(_via_wikimedia(tema, img_out), "wikimedia")


def resolver_visuales(segmentos: list[dict], tema: str, out_dir: Path) -> list[dict]:
    """Resuelve el visual de TODOS los segmentos del guion. Devuelve la misma lista
    con la clave 'visual_resuelto' añadida a cada segmento."""
    out_dir = Path(out_dir)
    resueltos = []
    for i, seg in enumerate(segmentos, 1):
        vr = obtener_visual(seg.get("visual"), tema, out_dir, i)
        estado = vr["tipo_real"] if vr["ruta"] or vr["tipo_real"] == "grafica" else "SIN VISUAL"
        log.info(f"  Seg {i:>2}: {vr['tipo_pedido']:>13} → {estado:<14} {Path(vr['ruta']).name if vr['ruta'] else ''}")
        resueltos.append({**seg, "visual_resuelto": vr})
    return resueltos


if __name__ == "__main__":
    import sys, json, logging as _l
    _l.basicConfig(level=_l.INFO, format="%(message)s")
    try:
        import truststore; truststore.inject_into_ssl()
    except Exception:
        pass
    # Prueba rápida con unos segmentos tipo guion-narrador.
    demo = [
        {"n": 1, "visual": {"tipo": "foto_persona", "query": "Gabriel Garcia Marquez", "movimiento": "zoom_in", "clave": None}},
        {"n": 2, "visual": {"tipo": "foto_evento", "query": "Bogotazo 1948", "movimiento": "parallax", "clave": "1948"}},
        {"n": 3, "visual": {"tipo": "mapa", "query": "Colombia", "movimiento": "paneo", "clave": None}},
        {"n": 4, "visual": {"tipo": "gato_bumper", "movimiento": "corte_rapido", "clave": None}},
    ]
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "tmp" / "selector_demo"
    res = resolver_visuales(demo, "Colombia ciclica", out)
    print(json.dumps([r["visual_resuelto"] for r in res], ensure_ascii=False, indent=2))
