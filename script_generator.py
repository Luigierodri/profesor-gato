"""
Módulo 2 — Generador de Scripts
Usa Claude API para generar el guion del Profesor Gato sobre un tema dado.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SCRIPT_MAX_TOKENS


def cargar_system_prompt() -> str:
    with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def generar_script(tema: str, contexto_extra: str = "") -> dict:
    """
    Genera el guion completo del Profesor Gato para un tema dado.
    
    Args:
        tema: El tema del video (ej. "La inflación en México 2026")
        contexto_extra: Info adicional opcional (ej. dato trending de Polymarket)
    
    Returns:
        dict con titulo, guion, leccion, hashtags, descripcion_social, prompt_visual
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_message = f"Crea un video educativo sobre: {tema}"
    if contexto_extra:
        user_message += f"\n\nContexto adicional relevante hoy: {contexto_extra}"

    print(f"🎓 Generando script sobre: {tema}")

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=SCRIPT_MAX_TOKENS,
        system=cargar_system_prompt(),
        messages=[{"role": "user", "content": user_message}]
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
    print(f"📝 Palabras: {len(script_data['guion'].split())}")
    return script_data


if __name__ == "__main__":
    # Test rápido
    resultado = generar_script("Por qué México tiene tanta inflación")
    print("\n" + "="*50)
    print("TÍTULO:", resultado["titulo"])
    print("\nGUIÓN:\n", resultado["guion"])
    print("\nLECCIÓN:", resultado["leccion"])
    print("\nHASHTAGS:", resultado["hashtags"])
    print("\nPROMPT VISUAL:", resultado["prompt_visual"])
