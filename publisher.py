"""
publisher.py — Publicador de Videos a YouTube
Proyecto: Profesor Gato

Sube el video más reciente de videos/ a YouTube como YouTube Short.
Lee el metadata desde el JSON de run correspondiente en logs/.

USO:
  python publisher.py                           # Sube el video más reciente
  python publisher.py --dry-run                 # Muestra qué subiría sin subir
  python publisher.py --video videos/mi.mp4     # Video específico

SETUP INICIAL:
  1. Obtén credentials.json de Google Cloud Console (ver YOUTUBE_SETUP.md)
  2. Coloca credentials.json en la raíz del proyecto
  3. Primera ejecución abrirá el browser para autorizar — genera token.json
  4. Las siguientes ejecuciones usan token.json directamente (sin browser)
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ── Google / YouTube ───────────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("publisher")

# ── Constantes ─────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).parent
VIDEOS_DIR       = BASE_DIR / "videos"
LOGS_DIR         = BASE_DIR / "logs"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE       = BASE_DIR / "token.json"
COST_TRACKER     = LOGS_DIR / "cost_tracker.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",       # necesario para comentarios
    "https://www.googleapis.com/auth/yt-analytics.readonly",   # loop de métricas (performance_analyzer)
]

# Hashtags fijos que van en todas las descripciones
HASHTAGS_FIJOS = ["#ProfessorGato", "#Educación", "#HistoriaCurta", "#Shorts", "#Aprendizaje"]

YOUTUBE_CATEGORY_EDUCATION = "27"


# ── Auth ──────────────────────────────────────────────────────────────────────

def obtener_credenciales() -> Credentials:
    """
    Devuelve credenciales OAuth 2.0 válidas.
    - Usa token.json si existe y está vigente (o lo refresca automáticamente).
    - Si no, lanza el flujo OAuth en el browser y guarda token.json.
    """
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Token expirado — refrescando automáticamente...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"No se encontró {CREDENTIALS_FILE}.\n"
                    "Descarga credentials.json desde Google Cloud Console "
                    "(ver YOUTUBE_SETUP.md) y colócalo en la raíz del proyecto."
                )
            log.info("Primera autenticación — abriendo browser para OAuth...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        log.info(f"Token guardado en {TOKEN_FILE.name}")

    return creds


# ── Búsqueda de video + metadata ───────────────────────────────────────────────

def encontrar_video_reciente() -> Path:
    """Devuelve el .mp4 más nuevo en videos/ (excluye subdirectorios)."""
    mp4s = [
        f for f in VIDEOS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() == ".mp4"
    ]
    if not mp4s:
        raise FileNotFoundError(f"No hay archivos .mp4 en {VIDEOS_DIR}")
    return max(mp4s, key=lambda f: f.stat().st_mtime)


def buscar_log_del_video(ruta_video: Path) -> dict | None:
    """
    Busca en logs/run_*.json el log cuyo campo ruta_video coincide con ruta_video.
    Devuelve el dict del log, o None si no se encuentra.
    """
    ruta_str = str(ruta_video.resolve())
    logs = sorted(LOGS_DIR.glob("run_*.json"), reverse=True)
    for log_path in logs:
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            log_ruta = data.get("ruta_video", "")
            if Path(log_ruta).resolve() == Path(ruta_str).resolve():
                return data
        except Exception:
            continue
    return None


def construir_metadata(run_log: dict, ruta_video: Path) -> dict:
    """Construye el dict de metadata para YouTube a partir del run log."""
    script = run_log.get("script", {})
    tema   = run_log.get("tema", ruta_video.stem)

    titulo_raw  = script.get("titulo") or tema
    titulo      = titulo_raw[:100]  # YouTube max 100 chars

    descripcion_social = script.get("descripcion_social", "")
    hashtags_script    = script.get("hashtags", [])

    # Tags: palabras del tema + hashtags del script (sin #, max 500 chars total)
    tags_raw = [w for w in tema.split() if len(w) > 3]
    tags_raw += [h.lstrip("#") for h in hashtags_script]
    tags_raw += [h.lstrip("#") for h in HASHTAGS_FIJOS]
    tags = list(dict.fromkeys(tags_raw))[:30]  # dedup, máx 30

    hashtags_str = " ".join(hashtags_script + HASHTAGS_FIJOS)
    descripcion  = f"{descripcion_social}\n\n{hashtags_str}".strip()

    return {
        "titulo":      titulo,
        "descripcion": descripcion,
        "tags":        tags,
        "tema":        tema,
    }


# ── Subida a YouTube ───────────────────────────────────────────────────────────

def subir_a_youtube(ruta_video: Path, metadata: dict, dry_run: bool = False,
                    publish_at: str | None = None) -> dict:
    """
    Sube el video a YouTube como YouTube Short.
    Si `publish_at` (ISO8601 UTC, ej. 2026-07-10T18:00:00Z) se pasa, lo sube PRIVADO
    y YouTube lo hace público a esa hora server-side (no requiere PC encendida).
    Devuelve {"video_id": ..., "url": ..., "titulo": ...}.
    """
    log.info("=" * 60)
    log.info("  YOUTUBE UPLOAD — Profesor Gato")
    log.info("=" * 60)
    log.info(f"  Video:       {ruta_video.name}")
    log.info(f"  Título:      {metadata['titulo']}")
    log.info(f"  Tema:        {metadata['tema']}")
    log.info(f"  Tags:        {', '.join(metadata['tags'][:8])}...")
    size_mb = ruta_video.stat().st_size / 1024 / 1024
    log.info(f"  Tamaño:      {size_mb:.1f} MB")

    if dry_run:
        log.info("\n  [DRY RUN] No se sube nada.")
        log.info(f"  Descripción preview:\n{metadata['descripcion'][:200]}...")
        return {"video_id": "DRY_RUN", "url": "https://youtu.be/DRY_RUN", "titulo": metadata["titulo"], "_youtube": None}

    creds   = obtener_credenciales()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    body = {
        "snippet": {
            "title":       metadata["titulo"],
            "description": metadata["descripcion"],
            "tags":        metadata["tags"],
            "categoryId":  YOUTUBE_CATEGORY_EDUCATION,
            "defaultLanguage": "es",
        },
        "status": {
            "privacyStatus":           "private" if publish_at else "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
        },
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at
        log.info(f"  ⏰ Programado para: {publish_at} (privado hasta entonces)")

    media = MediaFileUpload(
        str(ruta_video),
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5 MB chunks
    )

    log.info("\n  Iniciando subida (resumable)...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    uploaded_bytes = 0
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            mb_done = size_mb * status.progress()
            log.info(f"  Subiendo... {pct}% ({mb_done:.1f}/{size_mb:.1f} MB)")

    video_id = response["id"]
    url      = f"https://youtu.be/{video_id}"

    log.info("\n" + "=" * 60)
    log.info(f"  PUBLICADO")
    log.info(f"  Video ID: {video_id}")
    log.info(f"  URL:      {url}")
    log.info("=" * 60)

    return {"video_id": video_id, "url": url, "titulo": metadata["titulo"], "_youtube": youtube}


# ── Comentario del creador ────────────────────────────────────────────────────

def publicar_comentario(youtube, video_id: str, metadata: dict, run_log: dict | None) -> str | None:
    """
    Publica un comentario del creador en el video recién subido.
    Usa descripcion_social del script si está disponible, o un CTA genérico.
    Devuelve el comment_id o None si falla.

    Nota: la API de YouTube no permite pinear comentarios vía API v3.
    Este comentario aparece con badge de Creador. Para pinearlo ir a YouTube Studio.
    """
    script = (run_log or {}).get("script", {})
    desc_social = script.get("descripcion_social", "").strip()
    hashtags    = " ".join(script.get("hashtags", []))

    # CTA de suscripción fijo: convierte espectadores en suscriptores (conversión actual ~0.5%).
    # Pinea este comentario en YouTube Studio para máxima visibilidad.
    cta_suscripcion = (
        "🐱 Si esto te voló la cabeza, suscríbete: subimos un dato que te cambia "
        "la forma de ver el mundo CADA DÍA a las 7am. No te lo pierdas."
    )

    if desc_social:
        texto = f"{desc_social}\n\n{cta_suscripcion}"
        if hashtags:
            texto += f"\n\n{hashtags}"
    else:
        tema = metadata.get("tema", "este tema")
        texto = (
            f"¿Tú ya lo sabías? Cuéntanos en los comentarios 👇\n\n"
            f"{cta_suscripcion}\n\n{hashtags}"
        ).strip()

    try:
        resp = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": texto}
                    },
                }
            },
        ).execute()
        comment_id = resp["id"]
        log.info(f"  Comentario publicado (id={comment_id})")
        log.info(f"  Texto: {texto[:80]}{'...' if len(texto) > 80 else ''}")
        return comment_id
    except Exception as e:
        log.warning(f"  No se pudo publicar el comentario: {e}")
        return None


# ── Actualizar cost tracker ────────────────────────────────────────────────────

def registrar_publicacion(ruta_video: Path, resultado: dict) -> None:
    """Añade youtube_id y youtube_url al run correspondiente en cost_tracker.json."""
    if not COST_TRACKER.exists():
        return
    try:
        data = json.loads(COST_TRACKER.read_text(encoding="utf-8"))
        ruta_str = str(ruta_video.resolve())

        for run in data.get("runs", []):
            log_ruta = run.get("ruta_video", "")
            if log_ruta and Path(log_ruta).resolve() == Path(ruta_str).resolve():
                run["youtube_id"]  = resultado["video_id"]
                run["youtube_url"] = resultado["url"]
                run["publicado_en"] = datetime.now(timezone.utc).isoformat()
                break
        else:
            # Si no hay run con esa ruta, añadir entrada mínima
            data.setdefault("runs", []).append({
                "timestamp":    datetime.now(timezone.utc).isoformat(),
                "ruta_video":   str(ruta_video),
                "youtube_id":   resultado["video_id"],
                "youtube_url":  resultado["url"],
                "titulo":       resultado["titulo"],
            })

        COST_TRACKER.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info(f"  cost_tracker.json actualizado con youtube_id: {resultado['video_id']}")
    except Exception as e:
        log.warning(f"  No se pudo actualizar cost_tracker.json: {e}")


# ── Fallback: subir a Google Drive ─────────────────────────────────────────────

def subir_a_drive(ruta_video: Path, metadata: dict) -> dict | None:
    """
    Sube el video a Google Drive usando las credenciales del entorno
    (funciona con Workload Identity Federation en GitHub Actions o con
    Application Default Credentials en local).

    Requiere la variable de entorno GOOGLE_DRIVE_FOLDER_ID con el ID de
    una carpeta de Drive compartida con la cuenta de servicio.
    Devuelve {"drive_id": ..., "drive_url": ...} o None si falla.
    """
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        log.info("  Drive: GOOGLE_DRIVE_FOLDER_ID no configurado — omitiendo backup.")
        return None

    log.info("=" * 60)
    log.info("  GOOGLE DRIVE BACKUP — Profesor Gato")
    log.info("=" * 60)
    try:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        file_meta = {
            "name":    ruta_video.name,
            "parents": [folder_id],
            "description": metadata.get("titulo", ruta_video.stem),
        }
        media = MediaFileUpload(str(ruta_video), mimetype="video/mp4", resumable=True)
        resultado = (
            drive.files()
            .create(body=file_meta, media_body=media, fields="id,webViewLink")
            .execute()
        )
        drive_id  = resultado.get("id", "")
        drive_url = resultado.get("webViewLink", f"https://drive.google.com/file/d/{drive_id}/view")
        log.info(f"  ✅ Subido a Drive: {drive_url}")
        return {"drive_id": drive_id, "drive_url": drive_url}
    except Exception as e:
        log.warning(f"  Drive fallback falló: {e}")
        return None


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Publica el último video de Profesor Gato en YouTube")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin subir nada")
    parser.add_argument("--video",   type=str, default=None, help="Ruta a un video específico")
    args = parser.parse_args()

    # 1. Localizar video
    if args.video:
        ruta_video = Path(args.video)
        if not ruta_video.exists():
            log.error(f"Video no encontrado: {ruta_video}")
            sys.exit(1)
    else:
        ruta_video = encontrar_video_reciente()
        log.info(f"Video más reciente: {ruta_video.name}")

    # 2. Leer metadata desde el run log
    run_log = buscar_log_del_video(ruta_video)
    if run_log:
        log.info(f"Log encontrado: tema='{run_log.get('tema', '?')}'")
        metadata = construir_metadata(run_log, ruta_video)
    else:
        log.warning("No se encontró log JSON para este video — usando nombre de archivo como título")
        metadata = {
            "titulo":      ruta_video.stem[:100],
            "descripcion": " ".join(HASHTAGS_FIJOS),
            "tags":        [h.lstrip("#") for h in HASHTAGS_FIJOS],
            "tema":        ruta_video.stem,
        }

    # 3. Subir a YouTube; si falla → fallback Drive
    resultado = None
    try:
        resultado = subir_a_youtube(ruta_video, metadata, dry_run=args.dry_run)
    except HttpError as e:
        log.error(f"Error de YouTube API: {e}")
        log.warning("YouTube rechazó el video — intentando Google Drive como respaldo...")
        drive_result = subir_a_drive(ruta_video, metadata)
        if drive_result:
            log.info(f"  📂 Video disponible en Drive: {drive_result['drive_url']}")
        else:
            log.warning(
                f"  ⚠️  Sin Drive configurado. El video está disponible como artefacto "
                f"de GitHub Actions por 30 días."
            )
        sys.exit(1)

    # 4. Publicar comentario del creador
    if not args.dry_run and resultado and resultado.get("_youtube"):
        publicar_comentario(resultado["_youtube"], resultado["video_id"], metadata, run_log)

    # 5. Registrar en cost tracker
    if not args.dry_run and resultado:
        registrar_publicacion(ruta_video, resultado)

    # 6. Registro PERSISTENTE para el loop de métricas (data/performance.json)
    if not args.dry_run and resultado and resultado["video_id"] != "DRY_RUN":
        try:
            from modules.performance_analyzer import registrar_video
            paneles = (run_log or {}).get("script", {}).get("paneles", [])
            gancho = paneles[0].get("narracion", "") if paneles else ""
            registrar_video(
                resultado["video_id"], resultado["titulo"],
                categoria=(run_log or {}).get("categoria", ""),
                evento=(run_log or {}).get("evento", ""),
                gancho=gancho,
            )
        except Exception as e:
            log.warning(f"  No se pudo registrar en performance.json: {e}")

    return resultado


if __name__ == "__main__":
    main()
