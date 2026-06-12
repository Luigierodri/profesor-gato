"""
essay_script_generator.py — Guion del VIDEO-ENSAYO LARGO (Profesor Gato)

Ensayo de economía 16:9 de 8-10 min, narrado por el dúo Gato/Bastet.
Flujo: ficha de datos VERIFICADOS (fact_checker) + outline curado → Claude escribe
el guion completo en segmentos agrupados por capítulo, con tarjetas de datos.
NUEVO y separado de script_generator.py (Shorts, no se toca).
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from modules import cost_tracker

ESSAY_MAX_TOKENS = 8000

POSES_VALIDAS = {
    "gato":   {"gancho", "explica", "revela", "cierre"},
    "bastet": {"sorpresa", "pregunta", "preocupada", "eureka"},
}


def _cargar_prompt() -> str:
    with open("prompts/system_prompt_essay.txt", "r", encoding="utf-8") as f:
        return f.read()


def generar_essay(tema: str, outline=None, ficha_datos: str = "") -> dict:
    """
    Args:
        tema: tema del video (ej. "El negocio del Mundial 2026").
        outline: opcional — lista de capítulos o dict {"nota":..., "capitulos":[...]};
                 cada capítulo {"capitulo": ..., "notas": ...}. Si se da, se respeta.
        ficha_datos: ficha de datos verificados (fact_checker) — ÚNICA fuente de cifras.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_message = f"Escribe el video-ensayo de economía (8-10 min) sobre el tema: {tema}"
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
        user_message += ("\n\nOUTLINE CURADO (respétalo: cubre estos capítulos en este "
                         "orden, además de una introducción y un cierre):\n"
                         + "\n".join(lineas))
        if nota_global:
            user_message += f"\n\nDIRECTRIZ GLOBAL DEL VIDEO (obligatoria): {nota_global}"
    if ficha_datos:
        user_message += ("\n\nFICHA DE DATOS VERIFICADOS (tu ÚNICA fuente de cifras, "
                         "fechas y nombres — lo que no esté aquí NO lo afirmes):\n"
                         + ficha_datos)

    print(f"🎬 Generando video-ensayo de economía: {tema}")
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=ESSAY_MAX_TOKENS,
        system=_cargar_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )
    try:
        cost_tracker.registrar_tokens(
            modelo=CLAUDE_MODEL,
            in_tok=message.usage.input_tokens, out_tok=message.usage.output_tokens,
            ctx=f"Essay: {tema[:40]}",
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
    script.setdefault("tema", tema)
    segs = script.get("segmentos", [])
    for i, s in enumerate(segs, 1):
        s["numero"] = i
        speaker = s.get("speaker", "gato")
        s["speaker"] = speaker if speaker in POSES_VALIDAS else "gato"
        s.setdefault("energia", "media")
        s.setdefault("capitulo", "")
        s["location"] = (s.get("location") or "").strip() or \
            "wide aerial view of a sprawling latin american city at golden hour"
        # Pose: válida para SU personaje o default sensato.
        pose = (s.get("pose") or "").strip()
        if pose not in POSES_VALIDAS[s["speaker"]]:
            s["pose"] = "explica" if s["speaker"] == "gato" else "pregunta"
        # Tarjeta de datos: solo si trae cifra real.
        d = s.get("dato")
        if not (isinstance(d, dict) and (d.get("cifra") or "").strip()):
            s["dato"] = None

    total_words = sum(len(s["narracion"].split()) for s in segs)
    n_datos = sum(1 for s in segs if s["dato"])
    n_bastet = sum(1 for s in segs if s["speaker"] == "bastet")
    print(f"✅ Ensayo generado: \"{script['titulo']}\" — {len(segs)} segmentos, "
          f"~{total_words} palabras, {n_datos} tarjetas de datos, {n_bastet} de Bastet")
    return script


if __name__ == "__main__":
    import sys
    tema = " ".join(sys.argv[1:]) or "¿Quién gana realmente con el Mundial 2026?"
    s = generar_essay(tema)
    print(json.dumps(s, ensure_ascii=False, indent=2))
