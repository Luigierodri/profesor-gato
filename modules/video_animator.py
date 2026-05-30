"""
video_animator.py — Módulo de Animación de Paneles
Proyecto: Profesor Gato

v4: Usa Veo 3.1 Lite (Google) via Vertex AI para animar paneles imagen→video.
- Auth: Application Default Credentials (Bearer token).
- Endpoint: predictLongRunning con polling hasta done=true.
- Fallback: Ken Burns estático (el ensamblador lo maneja con None).
"""

import os
import base64
import logging
import time
import urllib.request
import requests
from pathlib import Path
from datetime import datetime
from modules.gcp_client import vertex_url, vertex_headers, vertex_operation_url
from modules import cost_tracker

log = logging.getLogger("video_animator")

BASE_DIR  = Path(__file__).parent.parent
VEO_MODEL = "veo-3.1-lite-generate-preview"

VEO_POLL_INTERVAL = 10   # segundos entre polls
VEO_POLL_MAX      = 60   # máximo 10 minutos


def _slug(titulo: str) -> str:
    return (
        titulo.replace(" ", "_").replace("/", "-")
        .replace(":", "").replace("?", "").replace("*", "")
        .replace("<", "").replace(">", "").replace('"', "").replace("|", "")
    )[:30]


def _descargar_video_veo(ruta_imagen: str, prompt: str) -> bytes:
    """
    Llama a Veo 3.1 Lite via Vertex AI y devuelve los bytes del video MP4.
    Lanza excepción si falla.
    """
    with open(ruta_imagen, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "instances": [{
            "prompt": prompt,
            "image": {
                "bytesBase64Encoded": image_b64,
                "mimeType": "image/png",
            },
        }],
        "parameters": {
            "aspectRatio": "16:9",
            "sampleCount": 1,
            "durationSeconds": 6,
        },
    }

    resp = requests.post(
        vertex_url(VEO_MODEL, "predictLongRunning"),
        json=payload,
        headers=vertex_headers(),
        timeout=60,
    )
    resp.raise_for_status()
    operation = resp.json()

    operation_name = operation.get("name")
    if not operation_name:
        raise ValueError(f"Veo no devolvió nombre de operación: {operation}")

    log.info(f"     Veo operación: {operation_name}")

    # Polling hasta done=true
    for attempt in range(VEO_POLL_MAX):
        time.sleep(VEO_POLL_INTERVAL)
        poll_resp = requests.get(
            vertex_operation_url(operation_name),
            headers=vertex_headers(),
            timeout=30,
        )
        poll_resp.raise_for_status()
        status = poll_resp.json()

        if status.get("done"):
            log.info(f"     Veo completado en ~{(attempt+1)*VEO_POLL_INTERVAL}s")
            return _extraer_video_bytes(status)

        if attempt % 3 == 0:
            log.info(f"     Veo generando... ({(attempt+1)*VEO_POLL_INTERVAL}s)")

    raise TimeoutError(f"Veo no terminó en {VEO_POLL_MAX * VEO_POLL_INTERVAL}s")


def _extraer_video_bytes(status: dict) -> bytes:
    """
    Extrae los bytes del video del response final de Veo (Vertex AI).
    Maneja múltiples posibles estructuras de respuesta.
    """
    response = status.get("response", {})
    hdrs = vertex_headers()

    # Formato 1: predictions[].video.uri (Vertex AI style)
    predictions = response.get("predictions", [])
    if predictions:
        video = predictions[0].get("video", {})
        uri = video.get("uri") or video.get("url")
        if uri:
            resp = requests.get(uri, headers=hdrs, timeout=120)
            resp.raise_for_status()
            return resp.content

        b64 = video.get("bytesBase64Encoded")
        if b64:
            return base64.b64decode(b64)

    # Formato 2: generateVideoResponse.generatedSamples[].video
    gen_resp = response.get("generateVideoResponse", {})
    samples = gen_resp.get("generatedSamples", [])
    if samples:
        video = samples[0].get("video", {})
        uri = video.get("uri") or video.get("url")
        if uri:
            resp = requests.get(uri, headers=hdrs, timeout=120)
            resp.raise_for_status()
            return resp.content

    # Formato 3: GCS URI firmada (no necesita auth header)
    file_name = (
        response.get("name")
        or response.get("fileName")
        or (predictions[0].get("name") if predictions else None)
    )
    if file_name:
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        download_url = f"https://{location}-aiplatform.googleapis.com/v1/{file_name}:download?alt=media"
        resp = requests.get(download_url, headers=hdrs, timeout=120)
        resp.raise_for_status()
        return resp.content

    raise ValueError(
        f"No se pudo extraer video del response de Veo. "
        f"Claves disponibles: response={list(response.keys())}, status={list(status.keys())}"
    )


def animar_panel(
    ruta_imagen: str,
    visual_pizarron: str,
    numero_panel: int,
    carpeta_salida: str,
    speaker: str = "gato",
) -> str | None:
    """
    Anima un panel PNG con Veo 3.1 Fast.

    Args:
        ruta_imagen:     Ruta local al PNG del panel.
        visual_pizarron: Descripción visual del panel (guía la animación).
        numero_panel:    Número de panel (para el nombre de archivo).
        carpeta_salida:  Carpeta donde guardar el clip .mp4.
        speaker:         "gato" o "bastet".

    Returns:
        Ruta al clip .mp4 generado, o None si falla (el ensamblador
        hace fallback a Ken Burns con la imagen estática).
    """
    Path(carpeta_salida).mkdir(parents=True, exist_ok=True)
    output_path = Path(carpeta_salida) / f"panel_{numero_panel:02d}.mp4"

    log.info(f"  Animando panel {numero_panel} con Veo 3.1 Fast...")

    if speaker == "bastet":
        char_desc = "calico cat character with golden headband and plaid skirt, curious expression"
    else:
        char_desc = "orange cat professor with round glasses and green jacket, teaching expression"

    prompt = (
        f"Subtle cinematic parallax effect. Static foreground: {char_desc} must NOT move or deform — keep character completely still. "
        f"Only the background moves: gentle depth parallax, slow camera drift. "
        f"{visual_pizarron} visible on blackboard. "
        "16-bit pixel art style. Smooth, loop-friendly, professional."
    )

    try:
        video_bytes = _descargar_video_veo(ruta_imagen, prompt)

        with open(output_path, "wb") as f:
            f.write(video_bytes)

        size_mb = output_path.stat().st_size / 1024 / 1024
        log.info(f"  Veo panel_{numero_panel:02d}.mp4 ({size_mb:.1f} MB)")
        duracion_generada = payload["parameters"]["durationSeconds"]
        cost_tracker.registrar_video(
            VEO_MODEL,
            duracion_seg=duracion_generada,
            ctx=f"Panel {numero_panel} ({speaker})",
        )
        return str(output_path)

    except Exception as e:
        log.warning(f"  Panel {numero_panel} no se pudo animar con Veo: {e}")
        log.warning(f"     Fallback a Ken Burns con imagen estatica.")
        return None


def animar_paneles(
    resultados_imagenes: list[dict],
    datos_comic: dict,
    carpeta_salida: str = None,
) -> list[dict]:
    """
    Anima todos los paneles de imagen a video clip con Veo 3.1 Fast.

    Args:
        resultados_imagenes: Output de generar_imagenes_por_paneles()
        datos_comic:         Estructura del comic.
        carpeta_salida:      Carpeta destino para los clips.

    Returns:
        La misma lista con 'ruta_video' añadida (None = Ken Burns fallback).
    """
    if carpeta_salida is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        carpeta_salida = f"videos/clips/{_slug(datos_comic['titulo'])}_{timestamp}"

    paneles_idx = {p["numero"]: p for p in datos_comic["paneles"]}

    log.info(f"Animando {len(resultados_imagenes)} paneles con Veo 3.1 Fast...")
    log.info(f"  Modelo:  {VEO_MODEL}")
    log.info(f"  Carpeta: {carpeta_salida}")

    resultados = []
    for img_r in resultados_imagenes:
        numero  = img_r["numero"]
        visual  = paneles_idx[numero]["visual_pizarron"]
        speaker = img_r.get("speaker", "gato")
        ruta_v  = animar_panel(img_r["ruta_imagen"], visual, numero, carpeta_salida, speaker)
        resultados.append({**img_r, "ruta_video": ruta_v})

    animados = sum(1 for r in resultados if r["ruta_video"])
    log.info(f"  {animados}/{len(resultados)} paneles animados con Veo")
    return resultados


if __name__ == "__main__":
    import json, sys

    if len(sys.argv) < 3:
        print("Uso: python -m modules.video_animator <comic.json> <carpeta_imagenes>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        datos = json.load(f)

    imgs = [
        {"numero": p["numero"], "ruta_imagen": f"{sys.argv[2]}/panel_{p['numero']:02d}.png",
         "visual_pizarron": p["visual_pizarron"]}
        for p in datos["paneles"]
    ]

    resultados = animar_paneles(imgs, datos)
    print("\n" + "=" * 50)
    for r in resultados:
        estado = r["ruta_video"] or "FALLBACK (imagen estatica)"
        print(f"Panel {r['numero']}: {estado}")
    print("=" * 50)
