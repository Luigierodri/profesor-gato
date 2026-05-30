"""Test Vertex AI — imagen models con payload correcto."""
import os, sys, requests, importlib, base64
sys.path.insert(0, r"C:\Users\luigi\Desktop\profesor-gato")
os.environ["GOOGLE_CLOUD_PROJECT"] = "project-71cbc30b-23ca-40b4-a93"

import modules.gcp_client as gc
importlib.reload(gc)

print(f"Proyecto: {os.environ['GOOGLE_CLOUD_PROJECT']}\n")

# === IMAGEN via predict (formato correcto) ===
print("=== Imagen models (predict) ===")
payload_imagen_predict = {
    "instances": [{"prompt": "A cat sitting on a chair, cartoon style"}],
    "parameters": {"sampleCount": 1},
}
for model in ["imagen-3.0-fast-generate-001", "imagen-4.0-fast-generate-001"]:
    url = gc.vertex_url(model, "predict")
    try:
        resp = requests.post(url, json=payload_imagen_predict, headers=gc.vertex_headers(), timeout=60)
        if resp.ok:
            data = resp.json()
            imgs = data.get("predictions", [])
            print(f"[OK] {model}: {len(imgs)} imagen(es) generadas")
        else:
            err = resp.json().get("error", {})
            print(f"[{resp.status_code}] {model}: {err.get('message', '')[:130]}")
    except Exception as e:
        print(f"[ERR] {model}: {e}")

# === GEMINI imagen via generateContent (con role) ===
print("\n=== Gemini imagen models (generateContent) ===")
payload_gemini_img = {
    "contents": [{"role": "user", "parts": [{"text": "Generate an image of a cat sitting on a chair, cartoon style"}]}],
    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
}
for model in [
    "gemini-2.5-flash-preview-image-generation",
    "gemini-2.5-flash",
]:
    url = gc.vertex_url(model, "generateContent")
    try:
        resp = requests.post(url, json=payload_gemini_img, headers=gc.vertex_headers(), timeout=60)
        if resp.ok:
            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            has_image = any("inlineData" in p for p in parts)
            has_text = any("text" in p for p in parts)
            print(f"[OK] {model}: imagen={has_image} texto={has_text}")
        else:
            err = resp.json().get("error", {})
            print(f"[{resp.status_code}] {model}: {err.get('message', '')[:130]}")
    except Exception as e:
        print(f"[ERR] {model}: {e}")

# === LYRIA (música) ===
print("\n=== Lyria (música) ===")
for model in ["lyria-realtime-exp", "lyria-002"]:
    url = gc.vertex_url(model, "generateContent")
    payload = {"contents": [{"role": "user", "parts": [{"text": "Calm educational background music"}]}]}
    try:
        resp = requests.post(url, json=payload, headers=gc.vertex_headers(), timeout=30)
        print(f"[{resp.status_code}] {model}: {resp.json().get('error', {}).get('message', 'OK')[:100]}")
    except Exception as e:
        print(f"[ERR] {model}: {e}")
