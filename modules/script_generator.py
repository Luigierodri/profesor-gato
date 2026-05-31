"""
Módulo 2 — Generador de Scripts
Usa Claude API para generar el guion del Profesor Gato sobre un tema dado.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SCRIPT_MAX_TOKENS
from modules import cost_tracker


def cargar_system_prompt() -> str:
    with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def generar_script(tema: str, contexto_extra: str = "", datos_verificados: str = "") -> dict:
    """
    Genera el guion completo del Profesor Gato para un tema dado.

    Args:
        tema: El tema del video (ej. "La inflación en México 2026")
        contexto_extra: Info adicional opcional (ej. dato trending de Polymarket)
        datos_verificados: Ficha de datos verificados (web search) que Claude debe
                           usar como ÚNICA fuente de cifras/fechas/hechos.

    Returns:
        dict con titulo, guion, leccion, hashtags, descripcion_social, prompt_visual
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_message = f"Crea un video educativo sobre: {tema}"
    if datos_verificados:
        user_message += (
            "\n\nFICHA DE DATOS VERIFICADOS (úsala como ÚNICA fuente de cifras, "
            "fechas, nombres y hechos; NO inventes nada fuera de esto):\n"
            f"{datos_verificados}"
        )
    if contexto_extra:
        user_message += f"\n\nContexto adicional relevante hoy: {contexto_extra}"

    print(f"🎓 Generando script sobre: {tema}")

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=SCRIPT_MAX_TOKENS,
        system=cargar_system_prompt(),
        messages=[{"role": "user", "content": user_message}]
    )

    # Registrar costo con tokens reales
    cost_tracker.registrar_tokens(
        modelo=CLAUDE_MODEL,
        in_tok=message.usage.input_tokens,
        out_tok=message.usage.output_tokens,
        ctx=f"Script: {tema[:45]}",
    )

    raw = message.content[0].text.strip()

    # Limpiar markdown si Claude lo envuelve en ```json
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    script_data = json.loads(raw)
    print(f"✅ Script generado: \"{script_data['titulo']}\"")
    # Contar palabras del diálogo completo (nuevo formato paneles o guion legacy)
    if "paneles" in script_data:
        total_words = sum(len(p["narracion"].split()) for p in script_data["paneles"])
    else:
        total_words = len(script_data.get("guion", "").split())
    print(f"📝 Palabras: {total_words}")
    return script_data


if __name__ == "__main__":
    resultado = generar_script("Por que Mexico tiene tanta inflacion")
    print("\n" + "=" * 50)
    print("TITULO:", resultado["titulo"])
    print("LECCION:", resultado["leccion"])
    for p in resultado.get("paneles", []):
        print(f"\nPanel {p['numero']} [{p['speaker'].upper()}]: {p['narracion']}")
