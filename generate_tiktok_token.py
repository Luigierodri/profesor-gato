"""
generate_tiktok_token.py — Autenticación OAuth inicial con TikTok
Corre una sola vez localmente para obtener access_token y refresh_token.
Los valores resultantes van como secrets en GitHub Actions.

SETUP:
  1. Agrega al .env local:
       TIKTOK_CLIENT_KEY=aw2sl3x78disarz5
       TIKTOK_CLIENT_SECRET=7gAxSN8PcXMewp3ADsYlXxgKQVLh0XTB
  2. python generate_tiktok_token.py
  3. Copia los tokens que imprime a GitHub Secrets:
       TIKTOK_REFRESH_TOKEN → el refresh_token resultante
"""

import os
import json
import webbrowser
import urllib.parse
import http.server
import threading
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI  = "http://localhost:8080"
SCOPES        = "user.info.basic,video.publish,video.upload"
TOKEN_FILE    = Path("tiktok_token.json")

AUTH_URL  = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def main():
    if not CLIENT_KEY or not CLIENT_SECRET:
        print("Error: TIKTOK_CLIENT_KEY y TIKTOK_CLIENT_SECRET deben estar en .env")
        return

    params = {
        "client_key":    CLIENT_KEY,
        "scope":         SCOPES,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "state":         "profesor_gato",
    }
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params)

    code_holder = {"code": None, "error": None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                code_holder["code"] = qs["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<h1>Autorizado. Puedes cerrar esta ventana.</h1>")
            else:
                code_holder["error"] = qs.get("error", ["desconocido"])[0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Error en la autorizacion.</h1>")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("localhost", 8080), Handler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print("Abriendo navegador para autorizar TikTok...")
    print(f"Si no se abre: {auth_url}\n")
    webbrowser.open(auth_url)
    thread.join()

    if code_holder["error"]:
        print(f"Error de autorización: {code_holder['error']}")
        return

    code = code_holder["code"]
    if not code:
        print("No se recibió el authorization code.")
        return

    print("Intercambiando code por tokens...")
    resp = requests.post(TOKEN_URL, data={
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
    })
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        print(f"Error TikTok: {data['error']} — {data.get('error_description', '')}")
        return

    token_data = data.get("data", data)
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("  TOKENS OBTENIDOS")
    print("=" * 60)
    print(f"\nAgrega este secret en GitHub Actions:")
    print(f"\nTIKTOK_REFRESH_TOKEN:")
    print(f"  {token_data.get('refresh_token')}")
    print(f"\n(access_token expira en {token_data.get('expires_in', '?')}s — se auto-refresca)")
    print(f"(refresh_token expira en {token_data.get('refresh_expires_in', 31536000) // 86400} días)")
    print(f"\nGuardado en: {TOKEN_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
