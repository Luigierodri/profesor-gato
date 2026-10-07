"""
background_generator.py — Generación de Imágenes por Panel
Proyecto: Profesor Gato

v13 (relanzamiento v2): Imagen fue RETIRADO por Google el 17 ago 2026. Se migra a
Nano Banana (Gemini image) vía Vertex AI generateContent. Se quitan del respaldo
fal.ai (saldo negativo) y OpenAI (agotado).

  • gemini-3.1-flash-image — único generador (Vertex AI, ~$0.13/img), con reintentos.

Aspect ratio nativo por imageConfig.aspectRatio: "1:1" para paneles de Shorts
(se componen a 9:16 en el assembler) y "16:9" para el ensayo largo.

Auth: Application Default Credentials (gcloud auth application-default login)
Proyecto GCP: GOOGLE_CLOUD_PROJECT en .env
"""

import os
import base64
import logging
import time
import requests
from pathlib import Path
from datetime import datetime
from modules.gcp_client import vertex_url, vertex_headers
from modules import cost_tracker

log = logging.getLogger("background_generator")

BASE_DIR   = Path(__file__).parent.parent
IMAGES_DIR = BASE_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# Nano Banana. gemini-3.1-flash-image genera imagen vía generateContent (NO :predict
# como Imagen). El aspect ratio va en generationConfig.imageConfig.aspectRatio.
# OJO: el ID debe EXISTIR en Vertex. "gemini-3.1-flash-image" daba 404; el GA
# estable de Nano Banana en Vertex es "gemini-2.5-flash-image". Configurable por
# entorno; si el principal da 404 se cae a los respaldos automáticamente.
GEMINI_IMG_MODEL  = os.getenv("GEMINI_IMG_MODEL", "gemini-2.5-flash-image")
_GEMINI_FALLBACKS = ["gemini-2.5-flash-image", "gemini-2.5-flash-image-preview"]

# Estilo visual pixel art 16-bit
_PIXEL_STYLE = (
    "16-bit pixel art style, retro videogame aesthetic, "
    "warm colors, detailed pixel shading, clean pixel outlines, "
    "educational game character art"
)


def _construir_prompt(visual_pizarron: str, location: str = "classroom") -> str:
    """
    Genera el prompt para el FONDO del panel.
    - location="classroom": salón de clases con pizarrón (Panel 1 y 6)
    - location=<descripción>: escenario real relevante al tema (Paneles 2-5)
    El personaje se superpone en el assembler — NO debe aparecer en el fondo.
    """
    # NOTA: los modelos de imagen ignoran los negativos con facilidad. Lo que más
    # ayuda a NO meter personajes es pedir un PLANO AMPLIO de SOLO escenario; los
    # negativos quedan como refuerzo. El personaje se superpone luego en el assembler.
    if location == "classroom":
        return (
            f"{_PIXEL_STYLE}. "
            "WIDE ESTABLISHING SHOT of an EMPTY classroom interior, scenery only. "
            "Large blackboard centered on the wall with chalk drawings and diagrams. "
            f"The blackboard shows: {visual_pizarron}. "
            "Desks and decorations in the background, bright educational room. "
            "Completely empty of living beings: NO people, NO cats, NO animals, "
            "NO characters, NO silhouettes, NO figures anywhere. "
            "NO text, NO numbers, NO letters anywhere in the image."
        )
    # IMPORTANTE: fuera del salón NO inyectamos `visual_pizarron`. Ese campo trae
    # diagramas/íconos/etiquetas (p.ej. "podiums labeled 1970 1986 2026",
    # "football icons") que el modelo renderiza como texto basura y objetos
    # incoherentes (calendarios con años erróneos, balones equivocados). El fondo
    # debe ser SOLO un plano limpio del lugar; la info la dan narración y subtítulos.
    return (
        f"{_PIXEL_STYLE}. "
        f"WIDE ESTABLISHING SHOT of this setting: {location}. "
        "Clean scenery, landscape and architecture only — like an empty postcard or backdrop. "
        "Vivid atmospheric colors. NO classroom, NO blackboard. "
        "Completely empty of living beings: NO people, NO cats, NO animals, "
        "NO characters, NO silhouettes, NO crowds, NO figures anywhere. "
        "NO floating objects, NO diagrams, NO icons. "
        # El modelo no sabe escribir: cualquier letrero sale como texto basura.
        # Antes los pedíamos "en blanco" pero quedaban carteles vacíos (se ve raro);
        # ahora pedimos que NO existan letreros en la escena.
        "NO signs, NO banners, NO billboards, NO scoreboards, NO posters, NO screens "
        "anywhere — the scene has no signage at all. "
        "Absolutely NO readable words, NO names, NO logos, NO text, NO numbers, "
        "NO letters, NO dates, NO writing of any kind anywhere in the image."
    )


def _generar_con_nano_banana(prompt: str, aspect: str, model: str,
                             ref_b64: str = None, ref_mime: str = "image/jpeg") -> bytes:
    """
    Genera una imagen con un modelo Gemini image (Nano Banana) vía Vertex AI
    generateContent. Devuelve los bytes de la imagen (PNG/JPEG inline).

    `aspect`: "1:1" (paneles Shorts) o "16:9" (ensayo).  `model`: ID de Vertex.
    `ref_b64`: si se pasa una imagen de referencia (base64), hace IMAGE-TO-IMAGE
    (redibuja la foto real en el estilo pedido) en vez de texto-a-imagen.
    """
    url = vertex_url(model, "generateContent")
    parts = [{"text": prompt}]
    if ref_b64:
        parts.append({"inlineData": {"mimeType": ref_mime, "data": ref_b64}})
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            # TEXT+IMAGE es lo más compatible entre 2.5 y 3.x (el parser ignora el texto).
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect},
        },
    }
    resp = requests.post(url, json=payload, headers=vertex_headers(), timeout=120)
    if resp.status_code == 429:
        raise requests.exceptions.HTTPError(f"429 rate limit en {model}")
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"{model} no devolvió candidates: {str(data)[:200]}")
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise ValueError(f"{model} sin imagen. Parts: {[list(p.keys()) for p in parts]}")


def estilizar_referencia(ref_path, output_path, aspect: str = "16:9") -> str:
    """PIXEL-ARTEADOR: toma una FOTO REAL y la redibuja en el estilo pixel-art
    cinematográfico del canal (recreación transformativa → coherente y sin copiar la
    foto, evitando copyright). Devuelve la ruta de salida, o None si falla.
    """
    ref_path = Path(ref_path)
    if not ref_path.exists():
        return None
    ref_b64 = base64.b64encode(ref_path.read_bytes()).decode()
    mime = "image/png" if ref_path.suffix.lower() == ".png" else "image/jpeg"
    prompt = (
        "Redraw this image as an ORIGINAL detailed pixel-art cinematic illustration in the "
        "style of a cozy retro video-game: same subject, pose and composition, warm dramatic "
        "cinematic lighting. Do NOT copy the photo pixel for pixel — REINTERPRET it as new "
        "pixel-art artwork. Keep it tasteful and respectful. "
        "NO text, NO letters, NO numbers, NO watermarks anywhere in the image."
    )
    candidatos = []
    for m in [GEMINI_IMG_MODEL, *_GEMINI_FALLBACKS]:
        if m not in candidatos:
            candidatos.append(m)
    for model in candidatos:
        for i in range(2):
            try:
                img = _generar_con_nano_banana(prompt, aspect, model, ref_b64, mime)
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(img)
                cost_tracker.registrar_imagen(model, n=1, ctx=f"pixelart ref {ref_path.name}")
                log.info(f"  [pixel-art] {ref_path.name} → {Path(output_path).name}")
                return str(output_path)
            except Exception as e:
                log.warning(f"    estilizar {model} intento {i+1} falló: {e}")
                if "404" in str(e):
                    break
                if i < 1:
                    time.sleep(2)
    return None


def _nano_banana_con_reintentos(prompt: str, aspect: str, ctx: str,
                                intentos: int = 2) -> bytes:
    """
    Genera con Nano Banana probando varios IDs de modelo (por si uno da 404) y con
    reintentos ante fallos transitorios. Registra el costo con el modelo que sirvió.
    """
    candidatos = []
    for m in [GEMINI_IMG_MODEL, *_GEMINI_FALLBACKS]:
        if m not in candidatos:
            candidatos.append(m)

    ultimo = None
    for model in candidatos:
        for i in range(intentos):
            try:
                img_data = _generar_con_nano_banana(prompt, aspect, model)
                cost_tracker.registrar_imagen(model, n=1, ctx=ctx)
                return img_data
            except Exception as e:
                ultimo = e
                log.warning(f"    {model} intento {i+1}/{intentos} falló: {e}")
                # 404 = el modelo no existe en Vertex → no insistir, pasar al siguiente ID.
                if "404" in str(e):
                    break
                if i < intentos - 1:
                    time.sleep(2 * (i + 1))
    raise RuntimeError(f"Nano Banana falló ({ctx}): {ultimo}")


def generar_imagen_panel(
    visual_pizarron: str,
    numero_panel: int,
    carpeta_salida: str,
    ruta_referencia: str,
    speaker: str = "gato",
    location: str = "classroom",
) -> str:
    """
    Genera la imagen de FONDO del panel con Nano Banana (gemini-3.1-flash-image).
    El personaje se superpone en el assembler via sprite overlay — no aparece aquí.

    Args:
        visual_pizarron: Contexto visual de la escena (objetos, diagramas)
        numero_panel:    Número del panel
        carpeta_salida:  Carpeta de destino
        ruta_referencia: Ignorado (mantenido por compatibilidad)
        speaker:         "gato" o "bastet" (informativo, no afecta el fondo)
        location:        "classroom" o lugar real para paneles del medio
    """
    prompt = _construir_prompt(visual_pizarron, location)

    Path(carpeta_salida).mkdir(parents=True, exist_ok=True)
    output_path = Path(carpeta_salida) / f"panel_{numero_panel:02d}.png"

    log.info(f"  [{speaker.upper()}] Panel {numero_panel}: \"{visual_pizarron[:55]}...\" [{location}]")
    log.info(f"    {GEMINI_IMG_MODEL} (1:1)...")

    img_data = _nano_banana_con_reintentos(
        prompt, "1:1", f"Panel {numero_panel} ({speaker})"
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
    Genera una imagen por cada panel con Nano Banana (gemini-3.1-flash-image).

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

    log.info(f"Generando {len(paneles)} imagenes (Nano Banana {GEMINI_IMG_MODEL}) pixel art...")
    log.info(f"  Titulo:      {datos_comic['titulo']}")
    log.info(f"  Carpeta:     {carpeta_salida}")

    resultados = []
    for panel in paneles:
        numero  = panel["numero"]
        visual  = panel["visual_pizarron"]
        speaker = panel.get("speaker", "gato")

        location = panel.get("location", "classroom")
        ruta_imagen = generar_imagen_panel(
            visual, numero, carpeta_salida,
            ruta_referencia, speaker, location
        )
        resultados.append({
            "numero":          numero,
            "speaker":         speaker,
            "visual_pizarron": visual,
            "ruta_imagen":     ruta_imagen,
        })

    log.info(f"  {len(resultados)} imagenes generadas en: {carpeta_salida}")
    return resultados


# ─── ENSAYO LARGO (16:9) — aditivo, los Shorts no usan nada de esto ──────────

def _construir_prompt_essay(location: str) -> str:
    """Prompt del fondo 16:9 del ensayo: misma identidad pixel art del canal,
    plano cinematográfico amplio, sin seres vivos ni texto (el personaje y las
    tarjetas de datos se superponen en el assembler)."""
    return (
        f"{_PIXEL_STYLE}. "
        f"WIDE CINEMATIC ESTABLISHING SHOT of this setting: {location}. "
        "Clean scenery, landscape and architecture only — like an empty postcard or backdrop. "
        "Vivid atmospheric colors, dramatic cinematic lighting. "
        "Completely empty of living beings: NO people, NO cats, NO animals, "
        "NO characters, NO silhouettes, NO crowds, NO figures anywhere. "
        "NO floating objects, NO diagrams, NO icons. "
        "NO signs, NO banners, NO billboards, NO scoreboards, NO posters, NO screens "
        "anywhere — the scene has no signage at all. "
        "Absolutely NO readable words, NO names, NO logos, NO text, NO numbers, "
        "NO letters, NO dates, NO writing of any kind anywhere in the image."
    )


def generar_imagen_essay(location: str, output_path) -> str:
    """Genera UN fondo 16:9 para el ensayo con Nano Banana (gemini-3.1-flash-image)."""
    prompt = _construir_prompt_essay(location)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img_data = _nano_banana_con_reintentos(
        prompt, "16:9", f"Essay bg: {location[:40]}"
    )
    with open(output_path, "wb") as f:
        f.write(img_data)
    log.info(f"  [essay bg] {output_path.name} ({output_path.stat().st_size/1024:.0f} KB)")
    return str(output_path)


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
