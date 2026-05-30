"""
Probe rápido de modelos de generación de imágenes de Google.
Prueba gemini-2.5-flash-image, gemini-3.1-flash-image-preview e Imagen 4 Fast.
"""
import os, base64, requests, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
API_KEY = os.getenv("GOOGLE_API_KEY")
BASE    = "https://generativelanguage.googleapis.com/v1beta/models"
PROMPT  = "orange cat professor with glasses in pixel art style, simple blackboard background"

def test_generatecontent(model: str) -> str:
    url     = f"{BASE}/{model}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 200:
            parts = r.json()["candidates"][0]["content"]["parts"]
            for p in parts:
                if "inline_data" in p:
                    return f"OK ({len(p['inline_data']['data']) // 1024} KB b64)"
            return f"OK pero sin imagen — partes: {[list(p.keys()) for p in parts]}"
        return f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"ERROR: {e}"

def test_imagen4(model: str) -> str:
    url     = f"{BASE}/{model}:predict?key={API_KEY}"
    payload = {
        "instances": [{"prompt": PROMPT}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            imgs = data.get("predictions", [])
            if imgs:
                return f"OK ({len(imgs)} imagen(es))"
            return f"OK pero sin predictions: {list(data.keys())}"
        return f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"ERROR: {e}"

print("=" * 60)
print("PROBE — Generadores de imágenes Google")
print("=" * 60)

models_gc = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
]
for m in models_gc:
    result = test_generatecontent(m)
    print(f"[generateContent] {m}:")
    print(f"  → {result}")

print()
models_img4 = [
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
]
for m in models_img4:
    result = test_imagen4(m)
    print(f"[predict]         {m}:")
    print(f"  → {result}")

print("=" * 60)
