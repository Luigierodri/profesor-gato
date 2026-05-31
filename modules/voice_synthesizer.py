"""
Módulo 3 — Sintetizador de Voz
Convierte el guion del Profesor Gato a audio usando la voz clonada de Luigie en ElevenLabs.
v4: Soporta generación por paneles (un audio por panel)
"""

import os
import requests
from datetime import datetime
from pathlib import Path
from config import (
    ELEVENLABS_API_KEY, VOICE_ID, BASTET_VOICE_ID,
    ELEVENLABS_MODEL, VOICE_SETTINGS, OUTPUT_DIR
)
from modules import cost_tracker

BASTET_VOICE_SETTINGS = {
    "stability":        0.40,   # subido de 0.20: <0.30 en multilingual_v2 causa glitches/cortes
    "similarity_boost": 0.70,
    "style":            0.55,   # expresiva pero estable
    "use_speaker_boost": True,
}


def _pad_trailing(ruta_audio: str, segundos: float = 0.08):
    """Añade un silencio corto al final del MP3 (suaviza uniones entre paneles)."""
    import subprocess
    tmp_out = ruta_audio + ".pad.mp3"
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", ruta_audio, "-af", f"apad=pad_dur={segundos}",
         "-c:a", "libmp3lame", "-q:a", "2", tmp_out],
        capture_output=True,
    )
    if r.returncode == 0 and os.path.exists(tmp_out):
        os.replace(tmp_out, ruta_audio)


def _post_elevenlabs(url: str, headers: dict, payload: dict, intentos: int = 3):
    """POST a ElevenLabs con reintentos y backoff. Valida que el MP3 no venga vacío."""
    import time
    ultimo = None
    for i in range(intentos):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=90)
            if r.status_code == 200 and len(r.content) > 2000:  # mp3 mínimamente válido
                return r
            ultimo = f"[{r.status_code}] {r.text[:200]}"
        except Exception as e:
            ultimo = str(e)
        if i < intentos - 1:
            time.sleep(2 ** i)  # backoff: 1s, 2s
    raise Exception(f"ElevenLabs falló tras {intentos} intentos: {ultimo}")


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


def generar_audios_por_paneles(datos_comic: dict, carpeta_salida: str = None) -> list[dict]:
    """
    Genera un archivo de audio por cada panel del comic.
    
    Args:
        datos_comic: Dict con estructura del comic (output de comic_parser)
        carpeta_salida: Carpeta donde guardar los audios. 
                        Si no se da, crea una carpeta en audio/ con el título.
    
    Returns:
        Lista de dicts con info de cada panel + ruta del audio generado
    """
    titulo_limpio = (
        datos_comic["titulo"]
        .replace(" ", "_").replace("/", "-")
        .replace(":", "").replace("?", "").replace("*", "")
        .replace("<", "").replace(">", "").replace('"', "").replace("|", "")
    )[:30]
    
    if carpeta_salida is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        carpeta_salida = f"audio/{titulo_limpio}_{timestamp}"
    
    Path(carpeta_salida).mkdir(parents=True, exist_ok=True)
    
    paneles = datos_comic["paneles"]
    print(f"\n🎙️  Generando audio para {len(paneles)} paneles...")
    print(f"   Título: {datos_comic['titulo']}")
    print(f"   Carpeta: {carpeta_salida}\n")
    
    resultados = []

    for idx, panel in enumerate(paneles):
        numero    = panel["numero"]
        narracion = panel["narracion"]
        speaker   = panel.get("speaker", "gato")

        # Elegir voz según personaje
        if speaker == "bastet":
            voice_id       = BASTET_VOICE_ID
            voice_settings = BASTET_VOICE_SETTINGS
            speaker_label  = "BASTET"
        else:
            voice_id       = VOICE_ID
            voice_settings = VOICE_SETTINGS
            speaker_label  = "GATO"

        nombre_archivo = f"panel_{numero:02d}"
        ruta_audio = os.path.join(carpeta_salida, f"{nombre_archivo}.mp3")

        print(f"  Panel {numero}/{len(paneles)} [{speaker_label}]: \"{narracion[:50]}...\"")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        payload = {
            "text": narracion,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": voice_settings,
            # Continuidad de prosodia: contexto del panel anterior y siguiente
            "previous_text": paneles[idx - 1]["narracion"] if idx > 0 else None,
            "next_text":     paneles[idx + 1]["narracion"] if idx < len(paneles) - 1 else None,
        }

        response = _post_elevenlabs(url, headers, payload)

        with open(ruta_audio, "wb") as f:
            f.write(response.content)

        # Pad de 80 ms de silencio al final → suaviza la unión entre paneles
        # (evita "pops"). Como el mismo archivo alimenta video y audio, no desincroniza.
        _pad_trailing(ruta_audio, 0.08)

        duracion = obtener_duracion_audio(ruta_audio)
        if duracion < 0.3:
            raise Exception(
                f"Audio panel {numero} sospechosamente corto ({duracion:.2f}s) — posible glitch"
            )
        size_kb  = os.path.getsize(ruta_audio) / 1024

        # Registrar costo ElevenLabs con caracteres reales
        cost_tracker.registrar_voz(
            ELEVENLABS_MODEL,
            n_chars=len(narracion),
            ctx=f"Panel {numero} [{speaker_label}]",
        )

        print(f"  panel_{numero:02d}.mp3 [{speaker_label}] {duracion:.1f}s ({size_kb:.1f} KB)")

        resultados.append({
            "numero":          numero,
            "speaker":         speaker,
            "narracion":       narracion,
            "visual_pizarron": panel["visual_pizarron"],
            "ruta_audio":      ruta_audio,
            "duracion_real":   duracion,
        })
    
    print(f"\n✅ {len(resultados)} audios generados en: {carpeta_salida}")
    duracion_total = sum(p["duracion_real"] for p in resultados)
    print(f"   Duración total del video: {duracion_total:.1f}s")
    
    return resultados


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


def ajustar_duracion_total(resultados: list[dict], max_seg: float) -> list[dict]:
    """
    Garantiza que la suma de los audios no supere max_seg (para que el video
    sea un Short válido < 60s). Si se pasa, acelera TODOS los audios con
    atempo (preserva el tono) por el mismo factor, manteniendo la sincronía.

    Modifica los MP3 in-place y actualiza 'duracion_real'. Devuelve la lista.
    """
    import subprocess

    total = sum(r["duracion_real"] for r in resultados)
    if total <= max_seg:
        print(f"⏱️  Duración total {total:.1f}s ≤ {max_seg:.0f}s — OK para Short")
        return resultados

    factor = total / max_seg  # >1 → hay que acelerar
    factor = min(factor, 1.5)  # tope de seguridad; atempo soporta hasta 2.0
    print(f"⏱️  Duración {total:.1f}s > {max_seg:.0f}s — acelerando audios ×{factor:.3f}")

    for r in resultados:
        ruta = r["ruta_audio"]
        tmp_out = ruta + ".fast.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-i", ruta, "-filter:a", f"atempo={factor:.4f}",
             "-c:a", "libmp3lame", "-q:a", "2", tmp_out],
            capture_output=True,
        )
        os.replace(tmp_out, ruta)
        r["duracion_real"] = obtener_duracion_audio(ruta)

    nuevo_total = sum(r["duracion_real"] for r in resultados)
    print(f"⏱️  Nueva duración total: {nuevo_total:.1f}s")
    return resultados


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Uso: python modules/voice_synthesizer.py logs/comic_La_Tragedia_del_Mar_de_Aral.json")
        sys.exit(1)

    ruta_json = sys.argv[1]

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos_comic = json.load(f)

    resultados = generar_audios_por_paneles(datos_comic)

    print("\n" + "="*50)
    for p in resultados:
        print(f"Panel {p['numero']}: {p['duracion_real']:.1f}s → {p['ruta_audio']}")
    print("="*50)