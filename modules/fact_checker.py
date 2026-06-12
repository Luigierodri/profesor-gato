"""
fact_checker.py — Verificación de hechos con búsqueda web
Proyecto: Profesor Gato

Antes de escribir el guion, busca datos reales (fechas, cifras, nombres) con la
herramienta de búsqueda web de Anthropic y devuelve una "ficha de datos verificados".
Esa ficha se pasa a script_generator como ÚNICA fuente de hechos, para evitar
alucinaciones como el título "México organizará DOS Mundiales" (es el TERCERO).

Costo: web_search ≈ $10 / 1000 búsquedas → con max_uses=3, ~$0.03 por video.
"""

import logging
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from modules import cost_tracker

log = logging.getLogger("fact_checker")

_FICHA_PROMPT = """Investiga con búsqueda web el tema: "{tema}".

Devuelve una FICHA DE DATOS VERIFICADOS en español, en viñetas, con:
- Fechas exactas (años, no aproximaciones)
- Cifras y estadísticas con su año y fuente
- Nombres propios correctos (personas, lugares, instituciones)
- 1-2 datos sorprendentes pero CIERTOS y verificables
- Si un dato es incierto, discutido o no lo confirmas, dilo explícitamente.

NO inventes nada. Si no encuentras un dato, escribe "[no verificado]".
Máximo {max_vinetas} viñetas. Empieza directamente con las viñetas, sin preámbulo."""


def generar_ficha_datos(tema: str, max_uses: int = 3, max_vinetas: int = 12,
                        max_tokens: int = 1000, enfoque: str = "") -> str:
    """
    Devuelve una ficha breve de datos verificados sobre el tema usando web search.
    Si la búsqueda web no está disponible o falla, devuelve "" (el pipeline sigue,
    aunque sin verificación — script_generator lo maneja).

    Los defaults son los de los Shorts (~$0.03/video). El ensayo LARGO pide más
    (max_uses=6, max_vinetas=20, max_tokens=2000, enfoque con los ángulos del
    outline) porque vive o muere por los datos.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = _FICHA_PROMPT.replace("{max_vinetas}", str(max_vinetas)).format(tema=tema)
    if (enfoque or "").strip():
        prompt += f"\n\nENFOCA la búsqueda en estos ángulos:\n{enfoque.strip()}"

    try:
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        log.warning(f"  [FactCheck] búsqueda web no disponible ({e}) — guion sin verificar")
        return ""

    # Registrar costo (tokens). La búsqueda web se factura aparte por Anthropic.
    try:
        cost_tracker.registrar_tokens(
            modelo=CLAUDE_MODEL,
            in_tok=msg.usage.input_tokens,
            out_tok=msg.usage.output_tokens,
            ctx=f"FactCheck: {tema[:40]}",
        )
    except Exception:
        pass

    # Unir todos los bloques de texto de la respuesta (ignora bloques de tool_use)
    ficha = "\n".join(
        b.text for b in msg.content if getattr(b, "type", None) == "text"
    ).strip()

    log.info(f"  [FactCheck] Ficha de {len(ficha)} chars generada")
    return ficha


if __name__ == "__main__":
    import sys
    tema = " ".join(sys.argv[1:]) or "México será sede del Mundial 2026"
    print(f"Tema: {tema}\n" + "=" * 50)
    print(generar_ficha_datos(tema))
