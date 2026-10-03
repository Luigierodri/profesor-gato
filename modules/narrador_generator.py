"""
narrador_generator.py — Guion del LARGO formato NARRADOR ÚNICO (motor visual v2)
Proyecto: Profesor Gato

Flujo: ficha de datos VERIFICADOS (fact_checker) → Claude escribe el guion con
el cerebro prompts/system_prompt_narrador.txt → JSON de segmentos que consume
modules/ensamblador_narrador.armar_video().

Separado del pipeline viejo (essay_script_generator = dúo Gato/Bastet con tarjetas;
script_generator = Shorts). NO los toca.
"""

import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, VOCES
from modules import cost_tracker

log = logging.getLogger("narrador_generator")

# Headroom para un largo de 8-12 min (40-60 segmentos). Igual que el essay.
NARRADOR_MAX_TOKENS = 24000

VOCES_VALIDAS = set(VOCES.keys()) if VOCES else {"narrador", "luigi", "alt"}
VISUALES_VALIDOS = {"foto_persona", "foto_evento", "foto_lugar", "cuadro", "foto_cultura",
                    "footage", "mapa", "grafica", "escena_ia", "titulo", "gato_bumper"}
# Nombres de capítulo que son del Gato anfitrión (cold open / título / cierre).
_CAP_HOST = ("cold open", "cold-open", "titulo", "título", "intro", "apertura",
             "cierre", "outro", "despedida", "final")
MOVIMIENTOS = {"parallax", "zoom_in", "paneo", "paneo_der", "paneo_izq", "corte_rapido"}
GATO_POSES = {"gancho", "explica", "revela", "cierre", "senala", "indignado", "piensa", "dinero"}
# El Profesor Gato SIEMPRE habla con esta voz (coherente con ensamblador_narrador).
VOZ_GATO = "luigi"


def _cargar_prompt() -> str:
    with open("prompts/system_prompt_narrador.txt", "r", encoding="utf-8") as f:
        return f.read()


def _normalizar_visual(v) -> dict:
    """Devuelve SIEMPRE un dict de visual válido. Lo dudoso cae a escena_ia."""
    if not isinstance(v, dict):
        return {"tipo": "escena_ia", "query": "", "movimiento": "zoom_in", "clave": None}
    tipo = (v.get("tipo") or "").strip().lower()
    if tipo not in VISUALES_VALIDOS:
        tipo = "escena_ia"
    mov = (v.get("movimiento") or "").strip().lower()
    if mov not in MOVIMIENTOS:
        mov = "zoom_in"
    clave = v.get("clave")
    clave = clave.strip() if isinstance(clave, str) and clave.strip() else None
    return {"tipo": tipo, "query": (v.get("query") or "").strip(),
            "movimiento": mov, "clave": clave}


def _es_cap_host(cap: str) -> bool:
    c = (cap or "").lower()
    return any(k in c for k in _CAP_HOST)


def _enforce_voces(script: dict):
    """El Profesor Gato es el anfitrión. UNA voz por capítulo, sostenida:
    - cold open / título / cierre → siempre "luigi" (el Gato).
    - cada capítulo de contenido → UNA sola voz en el cuerpo; el Gato (luigi)
      PRESENTA el capítulo en su primer segmento. Casi todos luigi; máximo 2
      capítulos con voz invitada "narrador". Nunca se alterna dentro del capítulo."""
    from collections import Counter
    segs = script.get("segmentos", [])
    orden = []
    for s in segs:
        c = s.get("capitulo", "")
        if c and c not in orden:
            orden.append(c)

    desired = {}
    for cap in orden:
        if _es_cap_host(cap):
            desired[cap] = "luigi"
            continue
        votos = Counter((s.get("voz") or "luigi") for s in segs if s.get("capitulo") == cap)
        tot = sum(votos.values())
        narr = votos.get("narrador", 0)
        desired[cap] = "narrador" if (tot and narr / tot >= 0.6) else "luigi"
    # máximo 2 capítulos invitados (narrador); el resto vuelve al Gato
    invitados = [c for c in orden if desired[c] == "narrador"]
    for extra in invitados[2:]:
        desired[extra] = "luigi"

    content_caps = {c for c in orden if not _es_cap_host(c)}
    ya_presento = set()
    for s in segs:
        cap = s.get("capitulo", "")
        voz_cap = desired.get(cap, "luigi")
        tipo = (s.get("visual") or {}).get("tipo")
        if tipo == "titulo":
            s["voz"] = "luigi"
        elif cap in content_caps and cap not in ya_presento:
            ya_presento.add(cap)
            s["voz"] = "luigi"               # el Gato presenta el capítulo
        else:
            s["voz"] = voz_cap
        if s.get("gato") and s["voz"] != "luigi":
            s["gato"] = None                 # el Gato solo aparece cuando habla él
    return script


def _normalizar_datos(d):
    """Valida los `datos` de una gráfica: >=2 valores numéricos. Si no, None."""
    if not isinstance(d, dict):
        return None
    vals = []
    for it in (d.get("valores") or []):
        if not isinstance(it, dict):
            continue
        label = (str(it.get("label", "")) or "").strip()
        try:
            valor = float(it.get("valor"))
        except (TypeError, ValueError):
            continue
        if label:
            vals.append({"label": label, "valor": valor})
    if len(vals) < 2:
        return None
    return {"titulo": (d.get("titulo") or "").strip(),
            "unidad": (d.get("unidad") or "").strip(),
            "fuente": (d.get("fuente") or "").strip(),
            "valores": vals}


def generar_largo(tema: str, outline=None, ficha_datos: str = "") -> dict:
    """
    Args:
        tema: tema del video.
        outline: opcional — dict {"nota":..., "capitulos":[{"capitulo","notas"}]} o lista.
        ficha_datos: ficha de datos verificados (fact_checker) — ÚNICA fuente de cifras.
    Devuelve el script dict listo para ensamblador_narrador.armar_video().
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_message = f"Escribe el video LARGO (formato narrador único, 8-12 min) sobre: {tema}"
    if outline:
        nota_global = ""
        capitulos = outline
        if isinstance(outline, dict):
            nota_global = outline.get("nota", "")
            capitulos = outline.get("capitulos", [])
        lineas = []
        for c in capitulos:
            linea = f"- Capítulo \"{c.get('capitulo','')}\""
            if c.get("notas"):
                linea += f"\n  · Beats que este capítulo DEBE tocar: {c['notas']}"
            lineas.append(linea)
        if lineas:
            user_message += ("\n\nOUTLINE CURADO (respétalo: cubre estos capítulos en este "
                             "orden, con su cold open y su cierre):\n" + "\n".join(lineas))
        if nota_global:
            user_message += f"\n\nDIRECTRIZ GLOBAL DEL VIDEO (obligatoria): {nota_global}"
    if ficha_datos:
        user_message += ("\n\nFICHA DE DATOS VERIFICADOS (tu ÚNICA fuente de cifras, "
                         "fechas y nombres — lo que no esté aquí NO lo afirmes):\n"
                         + ficha_datos)

    print(f"🎬 Generando LARGO (narrador): {tema}")
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=NARRADOR_MAX_TOKENS,
        system=_cargar_prompt(),
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        message = stream.get_final_message()
    try:
        cost_tracker.registrar_tokens(
            modelo=CLAUDE_MODEL,
            in_tok=message.usage.input_tokens, out_tok=message.usage.output_tokens,
            ctx=f"Largo narrador: {tema[:40]}",
        )
    except Exception:
        pass

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    script = json.loads(raw)
    script.setdefault("tema", "negro_oro")
    mg = script.get("musica_global")
    script["musica_global"] = mg.strip() if isinstance(mg, str) and mg.strip() else None

    segs = script.get("segmentos", [])
    for i, s in enumerate(segs, 1):
        s["n"] = i
        s["narracion"] = (s.get("narracion") or "").strip()
        s["capitulo"] = (s.get("capitulo") or "").strip()

        # Pose del Gato (opcional, ocasional).
        pose = (s.get("gato") or "").strip().lower()
        s["gato"] = pose if pose in GATO_POSES else None

        # Voz: válida; si aparece el Gato, SIEMPRE su voz (nunca se mezcla).
        voz = (s.get("voz") or "narrador").strip().lower()
        if voz not in VOCES_VALIDAS:
            voz = "narrador"
        if s["gato"]:
            voz = VOZ_GATO
        s["voz"] = voz

        s["visual"] = _normalizar_visual(s.get("visual"))
        s["datos"] = _normalizar_datos(s.get("datos")) if s["visual"]["tipo"] == "grafica" else None
        # Gráfica sin datos válidos → cae a escena_ia para no romper el render.
        if s["visual"]["tipo"] == "grafica" and not s["datos"]:
            s["visual"]["tipo"] = "escena_ia"
        sfx = s.get("sfx")
        s["sfx"] = sfx.strip() if isinstance(sfx, str) and sfx.strip() else None
        mus = s.get("musica")
        s["musica"] = mus.strip() if isinstance(mus, str) and mus.strip() else None

    # El Gato es el anfitrión: una voz por capítulo, sin saltos.
    _enforce_voces(script)

    total_words = sum(len(s["narracion"].split()) for s in segs)
    n_graf = sum(1 for s in segs if s["visual"]["tipo"] == "grafica")
    n_mapa = sum(1 for s in segs if s["visual"]["tipo"] == "mapa")
    # voz por capítulo (para verificar que no haya saltos)
    from collections import OrderedDict
    cap_voz = OrderedDict()
    for s in segs:
        cap_voz.setdefault(s.get("capitulo", ""), s["voz"])
    print(f"✅ Largo generado: \"{script.get('titulo','(sin título)')}\" — "
          f"{len(segs)} segmentos, ~{total_words} palabras, {n_graf} gráficas, {n_mapa} mapas")
    print("   Voz por capítulo:")
    for cap, v in cap_voz.items():
        print(f"     [{v:8s}] {cap}")
    return script


if __name__ == "__main__":
    import sys
    tema = " ".join(sys.argv[1:]) or "¿Por qué Colombia parece vivir en Macondo?"
    s = generar_largo(tema)
    print(json.dumps(s, ensure_ascii=False, indent=2))
