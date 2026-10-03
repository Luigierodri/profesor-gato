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

log = logging.getLogger("selector_visual")

BASE_DIR = Path(__file__).parent.parent
GATO_PNG = BASE_DIR / "assets" / "profesor_gato.png"

# Tipos que se resuelven buscando una FOTO real en Wikimedia.
_TIPOS_FOTO = {"foto_persona", "foto_evento", "foto_lugar", "cuadro"}


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

    # 3) Footage CC real
    if tipo == "footage":
        r = _via_footage(query, out_dir)
        if r:
            return R(r, "topical_footage_cc", es_video=True)
        r = _via_wikimedia(query, img_out)
        if r:
            return R(r, "wikimedia", tipo_real="foto_lugar")
        return R(_via_escena(query, img_out), "escena_ia", tipo_real="escena_ia")

    # 4) Mapa ESTILIZADO con identidad del canal (modules/mapa.py). Respaldo: foto del lugar.
    if tipo == "mapa":
        try:
            from modules import mapa as _mapa
            r = _mapa.generar_mapa(query, str(img_out.with_suffix(".png")))
        except Exception as e:
            log.warning(f"  [mapa] {query[:40]}: {e}")
            r = None
        if r:
            return R(r, "mapa_identidad", tipo_real="mapa")
        r = _via_wikimedia(query, img_out)  # respaldo: foto del lugar
        if r:
            return R(r, "wikimedia", tipo_real="foto_lugar")
        return R(_via_escena(query, img_out), "escena_ia", tipo_real="escena_ia")

    # 4b) Cultura pop (personaje de serie/película/juego): Wikimedia (actor/obra) →
    #     si no hay, se GENERA un "film still" cinematográfico coherente con la escena.
    if tipo == "foto_cultura":
        r = _via_wikimedia(query, img_out)
        if r:
            return R(r, "wikimedia", tipo_real="foto_cultura")
        prompt = (f"{query}, cinematic film still, dramatic cinematic lighting, "
                  f"photorealistic, movie scene, shallow depth of field")
        return R(_via_escena(prompt, img_out), "escena_ia", tipo_real="escena_ia")

    # 5) Fotos / cuadros (lo más común): Wikimedia → footage → escena_ia.
    if tipo in _TIPOS_FOTO:
        r = _via_wikimedia(query, img_out)
        if r:
            return R(r, "wikimedia")
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
