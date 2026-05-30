"""
setup_bastet_voice.py — Crea la voz de Bastet en ElevenLabs via Voice Design
Uso: python tools/setup_bastet_voice.py

Genera una voz femenina joven latinoamericana para Bastet y guarda el ID en .env
"""

import sys
import os
import json
import requests
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ELEVENLABS_API_KEY

BASE_URL = "https://api.elevenlabs.io/v1"
HEADERS  = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
ENV_FILE = Path(__file__).parent.parent / ".env"

SAMPLE_TEXT = (
    "Profe, espera un momento! Si eso es verdad, entonces por que nadie nos lo habia dicho antes? "
    "Esto cambia todo lo que creia saber del tema. Cuentame mas, por favor!"
)


def listar_voces_existentes():
    r = requests.get(f"{BASE_URL}/voices", headers=HEADERS)
    voces = r.json().get("voices", [])
    for v in voces:
        if "bastet" in v["name"].lower():
            print(f"  Voz existente encontrada: {v['name']} ({v['voice_id']})")
            return v["voice_id"]
    return None


def generar_preview_voz() -> str | None:
    """Genera una voz via Voice Design y retorna el generated_voice_id."""
    payload = {
        "voice_description": (
            "Young Latin American female cat character, energetic and curious, "
            "slightly high-pitched but clear, warm and expressive, "
            "perfect for educational content for young adults"
        ),
        "text": SAMPLE_TEXT,
    }
    r = requests.post(f"{BASE_URL}/voice-generation/generate-voice",
                      headers=HEADERS, json=payload, timeout=60)
    if r.status_code != 200:
        print(f"  Error Voice Design [{r.status_code}]: {r.text[:200]}")
        return None
    generated_id = r.headers.get("generated_voice_id")
    print(f"  Preview generado. generated_voice_id: {generated_id}")
    return generated_id


def guardar_voz(generated_voice_id: str) -> str | None:
    """Guarda la voz generada y retorna el voice_id permanente."""
    payload = {
        "voice_name": "Bastet",
        "voice_description": "Gata calico joven, energica y curiosa. Voz del show Profesor Gato.",
        "generated_voice_id": generated_voice_id,
        "labels": {"character": "Bastet", "project": "ProfesorGato"},
    }
    r = requests.post(f"{BASE_URL}/voice-generation/create-voice",
                      headers=HEADERS, json=payload, timeout=30)
    if r.status_code != 200:
        print(f"  Error guardando voz [{r.status_code}]: {r.text[:200]}")
        return None
    voice_id = r.json().get("voice_id")
    print(f"  Voz guardada: {voice_id}")
    return voice_id


def guardar_en_env(voice_id: str):
    """Agrega BASTET_VOICE_ID al .env."""
    contenido = ENV_FILE.read_text(encoding="utf-8")
    if "BASTET_VOICE_ID" in contenido:
        lineas = [
            f"BASTET_VOICE_ID={voice_id}" if l.startswith("BASTET_VOICE_ID") else l
            for l in contenido.splitlines()
        ]
        ENV_FILE.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    else:
        with open(ENV_FILE, "a", encoding="utf-8") as f:
            f.write(f"\nBASTET_VOICE_ID={voice_id}\n")
    print(f"  Guardado en .env: BASTET_VOICE_ID={voice_id}")


def main():
    print("\nConfigurando voz de Bastet en ElevenLabs...\n")

    # 1. Revisar si ya existe
    voice_id = listar_voces_existentes()
    if voice_id:
        guardar_en_env(voice_id)
        return

    # 2. Generar preview via Voice Design
    print("  Generando preview de voz femenina joven...")
    gen_id = generar_preview_voz()
    if not gen_id:
        print("\nFallo Voice Design. Opciones:")
        print("  a) Tu plan no incluye Voice Design (requiere Creator+)")
        print("  b) Usa una voz preset: agrega BASTET_VOICE_ID=<id> al .env")
        print("\nVoces femeninas sugeridas de ElevenLabs:")
        print("  Matilda: XrExE9yKIg1WjnnlVkGX")
        print("  Charlotte: XB0fDUnXU5powFXDhCwa")
        print("  Freya: jsCqWAovK2LkecY7zXl4")
        return

    # 3. Guardar la voz permanentemente
    print("  Guardando voz en tu cuenta ElevenLabs...")
    voice_id = guardar_voz(gen_id)
    if voice_id:
        guardar_en_env(voice_id)
        print(f"\nBastet lista! Ejecuta el pipeline normalmente.")
    else:
        print("\nNo se pudo guardar. Agrega manualmente BASTET_VOICE_ID al .env")


if __name__ == "__main__":
    main()
