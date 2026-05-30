"""Verifica que los módulos modificados importen correctamente."""
import sys, os
sys.path.insert(0, r"C:\Users\luigi\Desktop\profesor-gato")

from dotenv import load_dotenv
load_dotenv(r"C:\Users\luigi\Desktop\profesor-gato\.env")

import modules.background_generator as bg
import modules.music_generator as mg

print("[OK] background_generator importado")
print("[OK] music_generator importado")

proj = os.getenv("GOOGLE_CLOUD_PROJECT")
print(f"Proyecto GCP: {proj}")
print(f"IMAGEN4_MODEL: {bg.IMAGEN4_MODEL}")
print(f"IMAGEN3_MODEL: {bg.IMAGEN3_MODEL}")
print(f"LYRIA_MODEL:   {mg.LYRIA_MODEL}")
