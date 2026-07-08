"""
essay_voice.py — Voz del VIDEO-ENSAYO LARGO (Profesor Gato)

NUEVO y SEPARADO de voice_synthesizer.py (que es el de los Shorts y NO se toca).
Diferencias con el de Shorts:
  - DÚO: cada segmento se sintetiza con la voz de su speaker (gato/bastet).
  - Endpoint `/with-timestamps` de ElevenLabs → tiempo exacto de cada palabra,
    los subtítulos salen del TEXTO REAL del guion (cero Whisper, que inventa).
  - Settings MÁS ESTABLES que los Shorts (lección de Partida Guardada: en bloques
    largos la lectura expresiva tartamudea; stability alta = narración pareja).
"""

import os
import time
import json
import base64
import subprocess
import requests
from pathlib import Path
from config import ELEVENLABS_API_KEY, VOICE_ID, BASTET_VOICE_ID, ELEVENLABS_MODEL
from modules import cost_tracker

# Ensayo = lectura larga y estable (los Shorts conservan sus settings expresivos).
ESSAY_GATO_SETTINGS = {
    # PERFIL B (2026-07-05, Luigi eligió de oído): grave y natural, sin "estirar
    # palabras". Unificado en todos los pipelines de la voz Luigie.
    "stability":         0.52,
    "similarity_boost":  0.90,
    "style":             0.25,
    "use_speaker_boost": True,
}
ESSAY_BASTET_SETTINGS = {
    "stability":         0.50,   # <0.30 en multilingual_v2 causa glitches (lección Shorts)
    "similarity_boost":  0.70,
    "style":             0.45,
    "use_speaker_boost": True,
}


def _pad_trailing(ruta_audio: str, segundos: float = 0.12):
    """Silencio corto al final del MP3 (suaviza uniones entre segmentos)."""
    tmp_out = ruta_audio + ".pad.mp3"
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", ruta_audio, "-af", f"apad=pad_dur={segundos}",
         "-c:a", "libmp3lame", "-q:a", "2", tmp_out],
        capture_output=True,
    )
    if r.returncode == 0 and os.path.exists(tmp_out):
        os.replace(tmp_out, ruta_audio)


def _post_con_timestamps(voice_id: str, payload: dict, intentos: int = 3) -> dict:
    """POST al endpoint /with-timestamps → {'audio_base64':.., 'alignment':..}."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "xi-api-key": ELEVENLABS_API_KEY}
    ultimo = None
    for i in range(intentos):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=90)
            if r.status_code == 200:
                d = r.json()
                if d.get("audio_base64"):
                    return d
            ultimo = f"[{r.status_code}] {r.text[:200]}"
        except Exception as e:
            ultimo = str(e)
        if i < intentos - 1:
            time.sleep(2 ** i)
    raise Exception(f"ElevenLabs (timestamps) falló tras {intentos} intentos: {ultimo}")


def _palabras_desde_alignment(align: dict) -> list[dict]:
    """Convierte el alignment por-carácter de ElevenLabs en palabras con tiempos."""
    chars  = align.get("characters", [])
    starts = align.get("character_start_times_seconds", [])
    ends   = align.get("character_end_times_seconds", [])
    palabras, cur, w_start, w_end = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.strip() == "":
            if cur:
                palabras.append({"w": cur, "start": w_start, "end": w_end})
                cur, w_start = "", None
        else:
            if w_start is None:
                w_start = s
            cur += ch
            w_end = e
    if cur:
        palabras.append({"w": cur, "start": w_start, "end": w_end})
    return palabras


def obtener_duracion_audio(ruta_audio: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", ruta_audio],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def _voz_de(speaker: str) -> tuple[str, dict, str]:
    if speaker == "bastet":
        return BASTET_VOICE_ID, ESSAY_BASTET_SETTINGS, "BASTET"
    return VOICE_ID, ESSAY_GATO_SETTINGS, "GATO"


def generar_audios_essay(segmentos: list[dict], carpeta_salida: str) -> list[dict]:
    """Genera un MP3 por segmento con la voz de SU speaker + palabras con tiempo.

    El contexto de prosodia (previous_text/next_text) solo se pasa si es del MISMO
    speaker: el texto del otro personaje confunde la continuidad de la voz.
    """
    Path(carpeta_salida).mkdir(parents=True, exist_ok=True)
    print(f"\n🎙️  Voz del ensayo: {len(segmentos)} segmentos (dúo Gato/Bastet, timestamps)...")

    resultados = []
    for idx, seg in enumerate(segmentos):
        numero    = seg["numero"]
        narracion = seg["narracion"]
        speaker   = seg.get("speaker", "gato")
        voice_id, vs, label = _voz_de(speaker)
        ruta_audio = os.path.join(carpeta_salida, f"bloque_{numero:02d}.mp3")
        print(f"  Seg {numero}/{len(segmentos)} [{label}]: \"{narracion[:50]}...\"")

        prev_txt = (segmentos[idx - 1]["narracion"]
                    if idx > 0 and segmentos[idx - 1].get("speaker", "gato") == speaker else None)
        next_txt = (segmentos[idx + 1]["narracion"]
                    if idx < len(segmentos) - 1
                    and segmentos[idx + 1].get("speaker", "gato") == speaker else None)
        payload = {
            "text": narracion,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": vs,
            "previous_text": prev_txt,
            "next_text": next_txt,
        }
        data = _post_con_timestamps(voice_id, payload)
        with open(ruta_audio, "wb") as f:
            f.write(base64.b64decode(data["audio_base64"]))
        palabras = _palabras_desde_alignment(data.get("alignment") or {})
        _pad_trailing(ruta_audio, 0.12)

        duracion = obtener_duracion_audio(ruta_audio)
        if duracion < 0.3:
            raise Exception(f"Audio segmento {numero} sospechosamente corto ({duracion:.2f}s)")
        try:
            cost_tracker.registrar_voz(ELEVENLABS_MODEL, n_chars=len(narracion),
                                       ctx=f"Essay seg {numero} [{label}]")
        except Exception:
            pass

        print(f"  ✅ bloque_{numero:02d}.mp3 [{label}] {duracion:.1f}s "
              f"({len(palabras)} palabras con tiempo)")
        resultados.append({
            "numero": numero, "speaker": speaker, "narracion": narracion,
            "ruta_audio": ruta_audio, "duracion_real": duracion,
            "palabras": palabras,
        })

    # Persistir tiempos (y speakers) → --reuse-audio re-ensambla con subtítulos
    # exactos y la voz/personaje correctos sin re-pagar ElevenLabs.
    try:
        palabras_map = {str(r["numero"]): r["palabras"] for r in resultados}
        Path(carpeta_salida, "palabras.json").write_text(
            json.dumps(palabras_map, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    total = sum(r["duracion_real"] for r in resultados)
    print(f"\n✅ {len(resultados)} audios — duración hablada: {total/60:.1f} min")
    return resultados
