"""
background_generator.py — Generación de Imágenes por Panel
Proyecto: Profesor Gato

v12: Cadena de fallback de 4 proveedores (todos funcionales en project-71cbc30b):
1. imagen-4.0-fast-generate-001 — principal (Vertex AI, $0.02/img, 1080p)
2. imagen-3.0-fast-generate-001 — fallback Google 2 (Vertex AI, más barato)
3. fal-ai/flux/schnell           — fallback externo 1
4. gpt-image-1 (OpenAI)         — último recurso

Auth: Application Default Credentials (gcloud auth application-default login)
Proyecto GCP: GOOGLE_CLOUD_PROJECT en .env
"""

import os
import base64
import random
import logging
import time
import requests
from pathlib import Path
from datetime import datetime
from openai import OpenAI
import fal_client
from modules.gcp_client import vertex_url, vertex_headers
from modules import cost_tracker

log = logging.getLogger("background_generator")

BASE_DIR   = Path(__file__).parent.parent
IMAGES_DIR = BASE_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

IMAGEN4_MODEL  = "imagen-4.0-fast-generate-001"
IMAGEN3_MODEL  = "imagen-3.0-fast-generate-001"

# Outfits del Profesor Gato — cambia por video
_GATO_OUTFITS = [
    "green jacket and dark red tie",
    "black suit and white shirt",
    "brown tweed jacket and bow tie",
    "navy blazer and yellow tie",
    "casual denim jacket",
]

# Outfits de Bastet — cambia por video
_BASTET_OUTFITS = [
    "golden headband, plaid skirt and green vest",
    "golden headband, royal blue dress",
    "golden headband, purple academic robe",
    "golden headband, white blouse and red cardigan",
    "golden headband, emerald green jacket",
]

# Estilo visual pixel art 16-bit
_PIXEL_STYLE = (
    "16-bit pixel art style, retro videogame aesthetic, "
    "warm colors, detailed pixel shading, clean pixel outlines, "
    "educational game character art"
)


def _elegir_outfit(speaker: str, seed: int) -> str:
    """Elige un outfit consistente para todo el video (mismo seed = mismo outfit)."""
    rng = random.Random(seed)
    if speaker == "bastet":
        return rng.choice(_BASTET_OUTFITS)
    return rng.choice(_GATO_OUTFITS)


_CHAR_GATO   = "orange tabby cat professor with round glasses"
_CHAR_BASTET = "young calico cat with golden headband"

def _construir_prompt(
    visual_pizarron: str,
    location: str = "classroom",
    speaker: str = "gato",
    outfit: str = "",
    accion: str = "",
) -> str:
    """
    Genera el prompt de imagen completo: personaje en escena actuando.
    El personaje ya NO se superpone en el assembler — está dentro de la imagen generada.
    """
    char_base = _CHAR_GATO if speaker != "bastet" else _CHAR_BASTET
    char_desc = f"{char_base} wearing {outfit}" if outfit else char_base
    action    = accion if accion else ("teaching at blackboard" if location == "classroom" else "standing and observing")

    if location == "classroom":
        return (
            f"{_PIXEL_STYLE}. "
            "Colorful classroom scene. "
            f"{char_desc}, {action}, centered in frame. "
            "Large blackboard on the back wall showing: "
            f"{visual_pizarron}. "
            "Bright educational classroom interior, desks in background. "
            "NO text, NO numbers, NO letters anywhere in the image."
        )
    return (
        f"{_PIXEL_STYLE}. "
        f"Real-world location: {location}. "
        f"{char_desc}, {action}, visible in the scene. "
        f"Environment details: {visual_pizarron}. "
        "Vivid atmospheric pixel art, wide shot showing character and location. "
        "NO classroom, NO blackboard, NO text, NO numbers, NO letters."
    )


def _generar_con_imagen_vertex(model: str, prompt: str) -> bytes:
    """imagen-X via Vertex AI predict endpoint (devuelve bytesBase64Encoded)."""
    url = vertex_url(model, "predict")
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }
    resp = requests.post(url, json=payload, headers=vertex_headers(), timeout=120)
    if resp.status_code == 429:
        raise requests.exceptions.HTTPError(f"429 rate limit en {model}")
    resp.raise_for_status()
    data = resp.json()
    predictions = data.get("predictions", [])
    if not predictions:
        raise ValueError(f"{model} no devolvió predicciones")
    img_b64 = predictions[0].get("bytesBase64Encoded") or predictions[0].get("b64_json")
    if not img_b64:
        raise ValueError(f"{model} sin bytes. Keys: {list(predictions[0].keys())}")
    return base64.b64decode(img_b64)


def _generar_con_flux_schnell(prompt: str) -> bytes:
    # fal_client usa FAL_KEY; nuestro .env lo expone como FAL_API_KEY
    fal_key = os.getenv("FAL_API_KEY") or os.getenv("FAL_KEY")
    if not fal_key:
        raise ValueError("FAL_API_KEY no está configurada")
    os.environ["FAL_KEY"] = fal_key

    result = fal_client.run(
        "fal-ai/flux/schnell",
        arguments={
            "prompt": prompt,
            "image_size": "square_hd",
            "num_images": 1,
            "num_inference_steps": 4,
        },
    )
    image_url = result["images"][0]["url"]
    resp = requests.get(image_url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _generar_con_openai(prompt: str) -> bytes:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality="high",
    )
    return base64.b64decode(response.data[0].b64_json)


def generar_imagen_panel(
    visual_pizarron: str,
    numero_panel: int,
    carpeta_salida: str,
    ruta_referencia: str,
    speaker: str = "gato",
    outfit_seed: int = 0,
    location: str = "classroom",
    accion: str = "",
) -> str:
    """
    Genera una imagen para un panel con Imagen 4 (fallback: Imagen 3 → FLUX → OpenAI).
    El personaje aparece dentro de la imagen en la acción indicada.

    Args:
        visual_pizarron: Contexto visual de la escena (objetos, ambiente)
        numero_panel:    Número del panel
        carpeta_salida:  Carpeta de destino
        ruta_referencia: Ignorado (mantenido por compatibilidad)
        speaker:         "gato" o "bastet"
        outfit_seed:     Seed para outfit consistente en todo el video
        location:        "classroom" o lugar real para paneles del medio
        accion:          Qué está haciendo físicamente el personaje en la escena
    """
    outfit = _elegir_outfit(speaker, outfit_seed)
    prompt = _construir_prompt(visual_pizarron, location, speaker, outfit, accion)

    Path(carpeta_salida).mkdir(parents=True, exist_ok=True)
    output_path = Path(carpeta_salida) / f"panel_{numero_panel:02d}.png"

    log.info(f"  [{speaker.upper()}] Panel {numero_panel}: \"{visual_pizarron[:55]}...\" [{location}]")

    img_data = None
    errores  = {}

    ctx_panel = f"Panel {numero_panel} ({speaker})"

    # 1. Imagen 4 Fast — principal (Vertex AI, funcional en project-71cbc30b)
    try:
        log.info(f"    [1/4] {IMAGEN4_MODEL}...")
        img_data = _generar_con_imagen_vertex(IMAGEN4_MODEL, prompt)
        log.info(f"    OK ({IMAGEN4_MODEL})")
        cost_tracker.registrar_imagen(IMAGEN4_MODEL, n=1, ctx=ctx_panel)
    except Exception as e:
        errores["imagen4"] = str(e)
        log.warning(f"    {IMAGEN4_MODEL} fallo: {e}")

    # 2. Imagen 3 Fast — fallback Google 2 (Vertex AI)
    if img_data is None:
        try:
            log.info(f"    [2/4] {IMAGEN3_MODEL}...")
            img_data = _generar_con_imagen_vertex(IMAGEN3_MODEL, prompt)
            log.info(f"    OK ({IMAGEN3_MODEL})")
            cost_tracker.registrar_imagen(IMAGEN3_MODEL, n=1, ctx=ctx_panel)
        except Exception as e:
            errores["imagen3"] = str(e)
            log.warning(f"    {IMAGEN3_MODEL} fallo: {e}")

    # 3. FLUX Schnell (fal.ai) — sin costo de Vertex, pero registrar si se usa
    if img_data is None:
        try:
            log.info(f"    [3/4] FLUX Schnell (fal.ai)...")
            img_data = _generar_con_flux_schnell(prompt)
            log.info(f"    OK (FLUX Schnell)")
            cost_tracker.registrar_imagen("fal-ai/flux/schnell", n=1, ctx=ctx_panel)
        except Exception as e:
            errores["flux"] = str(e)
            log.warning(f"    FLUX Schnell fallo: {e}")

    # 4. OpenAI gpt-image-1 (último recurso)
    if img_data is None:
        try:
            log.info(f"    [4/4] OpenAI gpt-image-1...")
            img_data = _generar_con_openai(prompt)
            log.info(f"    OK (OpenAI)")
            cost_tracker.registrar_imagen("gpt-image-1", n=1, ctx=ctx_panel)
        except Exception as e:
            errores["openai"] = str(e)
            log.error(f"    OpenAI fallo: {e}")

    if img_data is None:
        raise RuntimeError(
            f"Todos los generadores fallaron para panel {numero_panel}. "
            + " | ".join(f"{k}: {v[:80]}" for k, v in errores.items())
        )

    with open(output_path, "wb") as f:
        f.write(img_data)

    size_kb = output_path.stat().st_size / 1024
    log.info(f"  panel_{numero_panel:02d}.png ({size_kb:.0f} KB)")
    return str(output_path)


def generar_imagenes_por_paneles(
    datos_comic: dict,
    ruta_referencia: str,
    carpeta_salida: str = None,
) -> list[dict]:
    """
    Genera una imagen por cada panel con Imagen 4 (fallback: Imagen 3 → FLUX → OpenAI).

    Args:
        datos_comic:     Dict con estructura del comic (output de script_generator)
        ruta_referencia: Ignorado (mantenido por compatibilidad)
        carpeta_salida:  Carpeta destino. Auto-generada si None.
    """
    titulo_limpio = (
        datos_comic["titulo"]
        .replace(" ", "_").replace("/", "-")
        .replace(":", "").replace("?", "").replace("*", "")
        .replace("<", "").replace(">", "").replace('"', "").replace("|", "")
    )[:30]

    if carpeta_salida is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        carpeta_salida = f"images/{titulo_limpio}_{timestamp}"

    paneles = datos_comic["paneles"]
    outfit_seed = hash(datos_comic.get("titulo", "")) & 0xFFFFFF

    log.info(f"Generando {len(paneles)} imagenes (Imagen4 → Imagen3 → FLUX → OpenAI) pixel art...")
    log.info(f"  Titulo:      {datos_comic['titulo']}")
    log.info(f"  Carpeta:     {carpeta_salida}")
    log.info(f"  Outfit seed: {outfit_seed}")

    resultados = []
    for panel in paneles:
        numero  = panel["numero"]
        visual  = panel["visual_pizarron"]
        speaker = panel.get("speaker", "gato")

        location = panel.get("location", "classroom")
        accion   = panel.get("accion", "")
        ruta_imagen = generar_imagen_panel(
            visual, numero, carpeta_salida,
            ruta_referencia, speaker, outfit_seed, location, accion
        )
        resultados.append({
            "numero":          numero,
            "speaker":         speaker,
            "visual_pizarron": visual,
            "ruta_imagen":     ruta_imagen,
        })

    log.info(f"  {len(resultados)} imagenes generadas en: {carpeta_salida}")
    return resultados


if __name__ == "__main__":
    import json, sys

    if len(sys.argv) < 2:
        print("Uso: python -m modules.background_generator <json> [imagen_referencia]")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        datos = json.load(f)

    ref = sys.argv[2] if len(sys.argv) > 2 else ""
    resultados = generar_imagenes_por_paneles(datos, ref)
    print("\n" + "="*50)
    for p in resultados:
        print(f"Panel {p['numero']} [{p['speaker']}]: {p['ruta_imagen']}")
    print("="*50)
