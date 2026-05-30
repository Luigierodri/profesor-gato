"""
comic_parser.py — Módulo 0: Parser de Comic
Proyecto: Profesor Gato 🐱

Toma una imagen de comic (estilo Profesor Gato) y extrae:
- La narración de cada panel
- La descripción visual del pizarrón
- La duración aproximada de cada panel

Output: JSON con estructura de paneles lista para el pipeline v4
"""

import anthropic
import base64
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def imagen_a_base64(ruta_imagen: str) -> tuple[str, str]:
    """Convierte imagen a base64 y detecta el media type."""
    path = Path(ruta_imagen)
    extension = path.suffix.lower()
    
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    media_type = media_types.get(extension, "image/png")
    
    with open(ruta_imagen, "rb") as f:
        datos = base64.standard_b64encode(f.read()).decode("utf-8")
    
    return datos, media_type


def parsear_comic(ruta_imagen: str) -> dict:
    """
    Analiza una imagen de comic y extrae la estructura de paneles.
    
    Args:
        ruta_imagen: Path a la imagen del comic
        
    Returns:
        Dict con titulo y lista de paneles
    """
    logger.info(f"Analizando comic: {ruta_imagen}")
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    imagen_b64, media_type = imagen_a_base64(ruta_imagen)
    
    prompt = """Analiza este comic del Profesor Gato y extrae la información de cada panel.

Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta, sin texto adicional:

{
  "titulo": "título del tema del comic",
  "paneles": [
    {
      "numero": 1,
      "narracion": "texto exacto que narra ese panel (lo que diría el Profesor Gato en voz alta)",
      "visual_pizarron": "descripción visual de lo que se ve en el pizarrón o fondo del panel",
      "duracion_aprox": 5
    }
  ],
  "leccion": "la lección final o moraleja del comic"
}

Reglas:
- "narracion": usa el texto de los globos de diálogo, adaptado para narración en voz en off (2-3 oraciones cortas máximo por panel)
- "visual_pizarron": describe lo que se ve visualmente en el panel (mapas, gráficas, fechas, imágenes) para regenerar con DALL-E
- "duracion_aprox": estima segundos de audio basado en la longitud del texto (4-8 segundos por panel)
- Extrae TODOS los paneles que veas en el comic"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": imagen_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )
    
    texto_respuesta = response.content[0].text.strip()
    
    # Limpiar si viene con markdown
    if texto_respuesta.startswith("```"):
        lineas = texto_respuesta.split("\n")
        texto_respuesta = "\n".join(lineas[1:-1])
    
    datos = json.loads(texto_respuesta)
    
    logger.info(f"✅ Comic parseado: '{datos['titulo']}' — {len(datos['paneles'])} paneles")
    for panel in datos["paneles"]:
        logger.info(f"  Panel {panel['numero']}: {panel['duracion_aprox']}s — {panel['narracion'][:60]}...")
    
    return datos


def guardar_estructura(datos: dict, ruta_salida: str = None) -> str:
    """Guarda el JSON de paneles en disco."""
    if ruta_salida is None:
        titulo_limpio = datos["titulo"].replace(" ", "_").replace("/", "-")[:30]
        ruta_salida = f"logs/comic_{titulo_limpio}.json"
    
    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    
    logger.info(f"💾 Estructura guardada en: {ruta_salida}")
    return ruta_salida


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python modules/comic_parser.py <ruta_imagen>")
        print("Ejemplo: python modules/comic_parser.py images/comic_mar_aral.png")
        sys.exit(1)
    
    ruta = sys.argv[1]
    
    datos = parsear_comic(ruta)
    ruta_json = guardar_estructura(datos)
    
    print("\n" + "="*50)
    print(f"TÍTULO: {datos['titulo']}")
    print(f"PANELES: {len(datos['paneles'])}")
    print(f"LECCIÓN: {datos['leccion']}")
    print(f"JSON guardado en: {ruta_json}")
    print("="*50)