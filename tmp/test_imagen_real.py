"""Test real: genera una imagen con background_generator y la guarda."""
import sys, os, logging
sys.path.insert(0, r"C:\Users\luigi\Desktop\profesor-gato")
logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

from dotenv import load_dotenv
load_dotenv(r"C:\Users\luigi\Desktop\profesor-gato\.env")

from modules.background_generator import generar_imagen_panel

ruta = generar_imagen_panel(
    visual_pizarron="A timeline showing Ancient Rome falling, with columns crumbling",
    numero_panel=1,
    carpeta_salida=r"C:\Users\luigi\Desktop\profesor-gato\tmp\test_output",
    ruta_referencia="",
    speaker="gato",
    outfit_seed=42,
)
print(f"\n=== IMAGEN GENERADA ===")
print(f"Ruta: {ruta}")
size_kb = os.path.getsize(ruta) / 1024
print(f"Tamaño: {size_kb:.0f} KB")
print("OK - imagen generada exitosamente!")
