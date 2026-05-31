"""
generate_tiktok_token.py — Autenticación OAuth inicial con TikTok
Corre una sola vez localmente para obtener access_token y refresh_token.
Los valores resultantes van como secrets en GitHub Actions.

SETUP:
  1. Agrega al .env local:
       TIKTOK_CLIENT_KEY=aw2sl3x78disarz5
       TIKTOK_CLIENT_SECRET=7gAxSN8PcXMewp3ADsYlXxgKQVLh0XTB
  2. python generate_tiktok_token.py
  3. El browser abre TikTok → autoriza con tu cuenta @Gatoprofesor
  4. TikTok redirige a tiktok.com/auth/redirect/?code=... — copia ESA URL completa
  5. Pégala en la terminal cuando te lo pida
  6. Copia el TIKTOK_REFRESH_TOKEN resultante a GitHub Secrets
"""

import os
import json
import webbrowser
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI  = "https://www.tiktok.com/auth/redirect/"
SCOPES        = "user.info.basic,video.publish,video.upload"
TOKEN_FILE    = Path("tiktok_token.json")

AUTH_URL  = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def extraer_code(raw: str) -> str | None:
    """
    Acepta la URL completa de redirect o solo el code.
    Ej: https://www.tiktok.com/auth/redirect/?code=ABC&state=...  → "ABC"
    O directamente: ABC → "ABC"
    """
    raw = raw.strip()
    if raw.startswith("http"):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)
        return qs.get("code", [None])[0]
    return raw or None


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

    print("=" * 60)
    print("  AUTENTICACIÓN TIKTOK — Profesor Gato")
    print("=" * 60)
    print("\nPASO 1: Abriendo navegador...")
    print("        Inicia sesión con la cuenta @Gatoprofesor\n")
    webbrowser.open(auth_url)
    print(f"Si el browser no abre, ve a esta URL manualmente:\n{auth_url}\n")

    print("PASO 2: Después de autorizar, TikTok te redirige a una URL que empieza con:")
    print("        https://www.tiktok.com/auth/redirect/?code=...\n")
    print("        Copia esa URL completa de la barra del navegador y pégala aquí.")
    print("        (También puedes pegar solo el valor del parámetro 'code')\n")

    raw = input("URL o code: ").strip()
    code = extraer_code(raw)

    if not code:
        print("\nError: no se pudo extraer el code. Inténtalo de nuevo.")
        return

    print(f"\nCode obtenido: {code[:20]}...")
    print("Intercambiando code por tokens...")

    resp = requests.post(TOKEN_URL, data={
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
    })

    if resp.status_code != 200:
        print(f"\nError HTTP {resp.status_code}: {resp.text}")
        return

    data = resp.json()
    err  = data.get("error", {})
    if isinstance(err, dict) and err.get("code", "ok") != "ok":
        print(f"\nError TikTok: {err.get('code')} — {err.get('message', '')}")
        return
    if isinstance(err, str) and err not in ("", "ok"):
        print(f"\nError TikTok: {err} — {data.get('error_description', '')}")
        return

    token_data = data.get("data", data)
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")

    refresh_token  = token_data.get("refresh_token", "—")
    expires_in     = token_data.get("expires_in", 86400)
    refresh_expiry = token_data.get("refresh_expires_in", 31536000) // 86400

    print("\n" + "=" * 60)
    print("  TOKENS OBTENIDOS")
    print("=" * 60)
    print(f"\nAgrega estos 2 secrets en GitHub Actions:")
    print(f"  https://github.com/Luigierodri/profesor-gato/settings/secrets/actions\n")
    print(f"TIKTOK_REFRESH_TOKEN:")
    print(f"  {refresh_token}")
    print(f"\n  (access_token dura {expires_in // 3600}h — se auto-refresca en cada run)")
    print(f"  (refresh_token dura {refresh_expiry} días)")
    print(f"\nArchivo guardado en: {TOKEN_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
