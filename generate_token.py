"""
generate_token.py — Genera token.json para YouTube OAuth
Corre este script una sola vez para autorizar la cuenta de YouTube.
"""
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
CREDENTIALS = Path(__file__).parent / "credentials.json"
TOKEN = Path(__file__).parent / "token.json"

if not CREDENTIALS.exists():
    raise FileNotFoundError("No se encontró credentials.json")

print("Abriendo navegador para autorizar YouTube...")
flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
creds = flow.run_local_server(port=0)
TOKEN.write_text(creds.to_json(), encoding="utf-8")
print(f"token.json generado en: {TOKEN}")
