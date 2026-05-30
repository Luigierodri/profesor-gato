"""
Módulo 3 — Sintetizador de Voz
Convierte el guion del Profesor Gato a audio usando la voz clonada de Luigie en ElevenLabs.
"""

import os
import requests
from datetime import datetime
from config import (
    ELEVENLABS_API_KEY, VOICE_ID, ELEVENLABS_MODEL,
    VOICE_SETTINGS, OUTPUT_DIR
)


def generar_audio(guion: str, nombre_archivo: str = None) -> str:
    """
    Genera el archivo de audio a partir del guion.
    
    Args:
        guion: Texto del guion del Profesor Gato
        nombre_archivo: Nombre base del archivo (sin extensión). 
                        Si no se da, usa timestamp.
    
    Returns:
        Ruta completa al archivo .mp3 generado
    """
    if nombre_archivo is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"profesor_gato_{timestamp}"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ruta_audio = os.path.join(OUTPUT_DIR, f"{nombre_archivo}.mp3")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }

    payload = {
        "text": guion,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": VOICE_SETTINGS
    }

    print(f"🎙️  Sintetizando voz con ElevenLabs...")
    print(f"   Voice ID: {VOICE_ID}")
    print(f"   Caracteres: {len(guion)}")

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(
            f"Error ElevenLabs [{response.status_code}]: {response.text}"
        )

    with open(ruta_audio, "wb") as f:
        f.write(response.content)

    size_kb = os.path.getsize(ruta_audio) / 1024
    print(f"✅ Audio generado: {ruta_audio} ({size_kb:.1f} KB)")
    return ruta_audio


def obtener_duracion_audio(ruta_audio: str) -> float:
    """
    Obtiene la duración del audio en segundos usando ffprobe.
    Requiere FFmpeg instalado.
    """
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         ruta_audio],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


if __name__ == "__main__":
    # Test rápido con un guion de ejemplo
    guion_test = (
        "¿Sabías que el dinero en tu bolsillo vale menos cada día que pasa? "
        "Bienvenidos a la clase de hoy, mis queridos estudiantes. "
        "Hablemos de la inflación. "
        "Imagina que tu sueldo es una pizza entera. "
        "El año pasado podías comprar ocho rebanadas con ese dinero. "
        "Este año, solo seis. Tu pizza se encogió, aunque el dinero sea el mismo. "
        "Eso es la inflación: el dinero pierde poder adquisitivo. "
        "¿Y quién gana? Los que tienen deudas fijas. "
        "Si debes un millón y hay inflación, ese millón vale menos en el futuro. "
        "Por eso los gobiernos a veces prefieren un poco de inflación a deflación. "
        "La lección de hoy: el dinero no es lo que vale, sino lo que puedes comprar con él. "
        "Y eso, mis queridos estudiantes, es todo por hoy. ¡Hasta la próxima clase!"
    )

    ruta = generar_audio(guion_test, "test_inflacion")
    print(f"\n🎵 Archivo de audio: {ruta}")
