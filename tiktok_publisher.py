"""
tiktok_publisher.py — Publica videos en TikTok (Content Posting API v2)
Proyecto: Profesor Gato

Flujo:
  1. Refresca access token usando TIKTOK_REFRESH_TOKEN
  2. POST /v2/post/publish/video/init/  → obtiene publish_id + upload_url
  3. PUT chunks del video al upload_url
  4. POST /v2/post/publish/status/fetch/ → verifica que quedó publicado

GitHub Secrets necesarios:
  TIKTOK_CLIENT_KEY      — App client key
  TIKTOK_CLIENT_SECRET   — App client secret
  TIKTOK_REFRESH_TOKEN   — OAuth refresh token (365 días de vida)

USO:
  python tiktok_publisher.py              # Sube el video más reciente
  python tiktok_publisher.py --dry-run    # Simula sin subir
  python tiktok_publisher.py --video v.mp4
"""

import os
import sys
import json
import math
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tiktok_publisher")

BASE_DIR   = Path(__file__).parent
VIDEOS_DIR = BASE_DIR / "videos"
LOGS_DIR   = BASE_DIR / "logs"

CLIENT_KEY     = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET  = os.getenv("TIKTOK_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("TIKTOK_REFRESH_TOKEN")

REDIRECT_URI   = "https://www.tiktok.com/auth/redirect/"
TOKEN_URL      = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL       = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL     = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

CHUNK_SIZE     = 10 * 1024 * 1024   # 10 MB por chunk (TikTok min 5MB, max 64MB)
MAX_TITLE_LEN  = 2200               # límite de caption en TikTok
HASHTAGS_FIJOS = ["#ProfessorGato", "#Educacion", "#Shorts", "#Aprender", "#HistoriaCurta"]


# ── Auth ──────────────────────────────────────────────────────────────────────

def obtener_access_token() -> str:
    """
    Obtiene un access token fresco usando el refresh token.
    El refresh token de TikTok dura 365 días y no se invalida al usarse.
    """
    if not CLIENT_KEY or not CLIENT_SECRET or not REFRESH_TOKEN:
        raise EnvironmentError(
            "Faltan variables de entorno: TIKTOK_CLIENT_KEY, "
            "TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN"
        )

    resp = requests.post(TOKEN_URL, data={
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "refresh_token",
        "refresh_token": REFRESH_TOKEN,
    })
    resp.raise_for_status()
    data = resp.json()

    if data.get("error") and data["error"] != "ok":
        raise RuntimeError(
            f"TikTok token error: {data['error']} — {data.get('error_description', '')}"
        )

    token_data = data.get("data", data)
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"No se obtuvo access_token. Respuesta: {data}")

    expires = token_data.get("expires_in", 86400)
    log.info(f"  Access token obtenido (expira en {expires}s)")
    return access_token


# ── Metadata ──────────────────────────────────────────────────────────────────

def encontrar_video_reciente() -> Path:
    mp4s = [f for f in VIDEOS_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".mp4"]
    if not mp4s:
        raise FileNotFoundError(f"No hay .mp4 en {VIDEOS_DIR}")
    return max(mp4s, key=lambda f: f.stat().st_mtime)


def buscar_log_del_video(ruta_video: Path) -> dict | None:
    ruta_str = str(ruta_video.resolve())
    for log_path in sorted(LOGS_DIR.glob("run_*.json"), reverse=True):
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            if Path(data.get("ruta_video", "")).resolve() == Path(ruta_str).resolve():
                return data
        except Exception:
            continue
    return None


def construir_caption(run_log: dict | None, ruta_video: Path) -> str:
    """Construye el caption/title para TikTok (max 2200 chars)."""
    if run_log:
        script = run_log.get("script", {})
        titulo = script.get("titulo") or run_log.get("tema", ruta_video.stem)
        desc   = script.get("descripcion_social", "").strip()
        tags   = script.get("hashtags", [])
    else:
        titulo = ruta_video.stem[:80]
        desc   = ""
        tags   = []

    tags_str = " ".join(tags + HASHTAGS_FIJOS)
    caption  = f"{titulo}\n\n{desc}\n\n{tags_str}".strip()
    return caption[:MAX_TITLE_LEN]


# ── Upload ────────────────────────────────────────────────────────────────────

def inicializar_upload(access_token: str, video_path: Path, caption: str) -> tuple[str, str]:
    """
    POST /v2/post/publish/video/init/
    Devuelve (publish_id, upload_url).
    """
    video_size = video_path.stat().st_size
    total_chunks = math.ceil(video_size / CHUNK_SIZE)

    payload = {
        "post_info": {
            "title":                    caption,
            "privacy_level":            "PUBLIC_TO_EVERYONE",
            "disable_duet":             False,
            "disable_comment":          False,
            "disable_stitch":           False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source":            "FILE_UPLOAD",
            "video_size":        video_size,
            "chunk_size":        CHUNK_SIZE,
            "total_chunk_count": total_chunks,
        },
    }

    resp = requests.post(
        INIT_URL,
        json=payload,
        headers={
            "Authorization":  f"Bearer {access_token}",
            "Content-Type":   "application/json; charset=UTF-8",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("error", {}).get("code", "ok") != "ok":
        raise RuntimeError(f"TikTok init error: {data['error']}")

    publish_id = data["data"]["publish_id"]
    upload_url = data["data"]["upload_url"]
    log.info(f"  Upload inicializado | publish_id: {publish_id}")
    log.info(f"  Chunks: {total_chunks} × {CHUNK_SIZE // 1024 // 1024} MB | Total: {video_size / 1024 / 1024:.1f} MB")
    return publish_id, upload_url


def subir_chunks(upload_url: str, video_path: Path) -> None:
    """Sube el video en chunks al upload_url de TikTok."""
    video_size   = video_path.stat().st_size
    total_chunks = math.ceil(video_size / CHUNK_SIZE)

    with open(video_path, "rb") as f:
        for i in range(total_chunks):
            start  = i * CHUNK_SIZE
            chunk  = f.read(CHUNK_SIZE)
            end    = start + len(chunk) - 1

            resp = requests.put(
                upload_url,
                data=chunk,
                headers={
                    "Content-Range":  f"bytes {start}-{end}/{video_size}",
                    "Content-Length": str(len(chunk)),
                    "Content-Type":   "video/mp4",
                },
            )
            resp.raise_for_status()
            pct = int((i + 1) / total_chunks * 100)
            log.info(f"  Chunk {i + 1}/{total_chunks} subido ({pct}%)")


def verificar_publicacion(access_token: str, publish_id: str, intentos: int = 12) -> bool:
    """
    Polling del status de publicación. Espera hasta 2 minutos.
    Devuelve True si se publicó, False si timeout o error.
    """
    for intento in range(intentos):
        resp = requests.post(
            STATUS_URL,
            json={"publish_id": publish_id},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json; charset=UTF-8",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        status = data.get("data", {}).get("status", "UNKNOWN")
        log.info(f"  Status [{intento + 1}/{intentos}]: {status}")

        if status == "PUBLISH_COMPLETE":
            return True
        if status in ("FAILED", "PUBLISH_FAILED"):
            log.error(f"  TikTok rechazó el video: {data}")
            return False
        if status in ("PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "SEND_TO_USER_INBOX"):
            time.sleep(10)
        else:
            time.sleep(10)

    log.warning("  Timeout esperando confirmación de TikTok (el video puede haberse publicado igual)")
    return False


# ── Entry point ───────────────────────────────────────────────────────────────

def publicar_en_tiktok(ruta_video: Path, dry_run: bool = False) -> dict:
    log.info("=" * 60)
    log.info("  TIKTOK UPLOAD — Profesor Gato")
    log.info("=" * 60)

    run_log = buscar_log_del_video(ruta_video)
    caption = construir_caption(run_log, ruta_video)
    size_mb = ruta_video.stat().st_size / 1024 / 1024

    log.info(f"  Video:   {ruta_video.name} ({size_mb:.1f} MB)")
    log.info(f"  Caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")

    if dry_run:
        log.info("\n  [DRY RUN] No se sube nada.")
        return {"status": "dry_run", "publish_id": None}

    access_token = obtener_access_token()
    publish_id, upload_url = inicializar_upload(access_token, ruta_video, caption)

    log.info("\n  Subiendo video en chunks...")
    subir_chunks(upload_url, ruta_video)

    log.info("\n  Verificando publicación...")
    ok = verificar_publicacion(access_token, publish_id)

    resultado = {
        "status":     "published" if ok else "processing",
        "publish_id": publish_id,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }

    if ok:
        log.info("\n" + "=" * 60)
        log.info(f"  PUBLICADO EN TIKTOK")
        log.info(f"  publish_id: {publish_id}")
        log.info("=" * 60)
    else:
        log.info("  Video subido — TikTok lo está procesando")

    return resultado


def main():
    parser = argparse.ArgumentParser(description="Publica en TikTok — Profesor Gato")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--video",   type=str, default=None)
    args = parser.parse_args()

    if args.video:
        ruta_video = Path(args.video)
        if not ruta_video.exists():
            log.error(f"Video no encontrado: {ruta_video}")
            sys.exit(1)
    else:
        ruta_video = encontrar_video_reciente()
        log.info(f"Video más reciente: {ruta_video.name}")

    try:
        resultado = publicar_en_tiktok(ruta_video, dry_run=args.dry_run)
        sys.exit(0 if resultado["status"] in ("published", "processing", "dry_run") else 1)
    except Exception as e:
        log.error(f"Error publicando en TikTok: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
