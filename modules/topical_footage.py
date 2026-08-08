# -*- coding: utf-8 -*-
"""topical_footage.py — Footage TEMÁTICO copyright-seguro para los ensayos de Gato.

Busca en YouTube SOLO videos con licencia Creative Commons (reutilizables) vía la
API (videoLicense=creativeCommon) y baja un clip corto MUTEADO (bestvideo, sin audio;
encima va la voz del gato). Así el ensayo intercala footage real del tema (un discurso,
una ciudad, un evento) con los fondos pixel-art y las gráficas — sin usar material ajeno.

Uso desde el pipeline:  descargar_footage_cc(query) -> Path del clip (o excepción).
"""
import os, re, subprocess, logging
from pathlib import Path

log = logging.getLogger("topical_footage")

BASE_DIR = Path(__file__).parent.parent
FOOT_DIR = BASE_DIR / "footage_cc"

# Títulos a evitar: reacciones/opinión/lives + NOTICIEROS (presentador/banner "ÚLTIMA
# HORA" se ven feo) — preferimos b-roll ambiental o institucional.
_BLOCK = re.compile(
    r"react|reacc|opini|qu[eé] opinas|en vivo|live\b|podcast|entrevista completa|"
    r"noticier|noticias|[uú]ltima hora|informativo|telediario|newscast|breaking news|"
    r"debate|rueda de prensa|declaracion", re.I)
# Canales de NOTICIEROS/medios a evitar (salen presentadores). Preferimos oficiales.
_BLOCK_CANAL = re.compile(
    r"noticias|noticiero|radio\b|caracol|rcn|semana|blu\b|pilon|desdeabajo|"
    r"televis|prensa|el tiempo|el espectador|canal \d", re.I)

_YT = None


def _svc():
    global _YT
    if _YT is None:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        c = Credentials.from_authorized_user_file(str(BASE_DIR / "token.json"))
        if not c.valid:
            c.refresh(Request())
        _YT = build("youtube", "v3", credentials=c)
    return _YT


def _slug(t: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", t)[:44].strip("_")


def buscar_footage_cc(query: str, n: int = 6) -> list[tuple]:
    """(videoId, título, canal) de videos CC relevantes (filtra reacciones/opinión)."""
    r = _svc().search().list(
        part="snippet", q=query, type="video", videoLicense="creativeCommon",
        maxResults=n, relevanceLanguage="es", safeSearch="strict",
        videoEmbeddable="true").execute()
    out = []
    for it in r.get("items", []):
        title = it["snippet"]["title"]
        canal = it["snippet"]["channelTitle"]
        if _BLOCK.search(title) or _BLOCK_CANAL.search(canal):
            continue
        out.append((it["id"]["videoId"], title, canal))
    return out


def descargar_footage_cc(query: str, dest_dir: Path = FOOT_DIR, ini: int = 8,
                         dur: int = 42) -> Path:
    """Baja ~`dur`s (desde el segundo `ini`) del primer candidato CC que sirva.
    Solo video (muteado). Cachea por slug de la query. Lanza si nada baja."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(query)
    for p in dest_dir.glob(f"{slug}_raw.*"):
        if p.suffix.lower() in (".mp4", ".mkv", ".webm") and p.stat().st_size > 50_000:
            log.info(f"  [footage-cc] (cache) {p.name}")
            return p

    cands = buscar_footage_cc(query)
    if not cands:
        raise RuntimeError(f"sin footage CC para: {query}")

    cookies = BASE_DIR / "cookies.txt"
    pc = os.getenv("YTDLP_PLAYER_CLIENT", "tv,android,web,ios")
    raw = dest_dir / f"{slug}_raw.mp4"
    for vid, title, ch in cands:
        cmd = ["yt-dlp", "--no-playlist", "--force-overwrites",
               "-f", "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]/best[height<=1080]",
               "--download-sections", f"*{ini}-{ini + dur}",
               "-o", str(raw), f"https://www.youtube.com/watch?v={vid}"]
        if pc:
            cmd += ["--extractor-args", f"youtube:player_client={pc}"]
        if cookies.exists():
            cmd += ["--cookies", str(cookies)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=200)
            if raw.exists() and raw.stat().st_size > 50_000:
                log.info(f"  [footage-cc] \"{query[:30]}\" → {vid} ({ch[:20]})")
                return raw
        except Exception as e:
            log.warning(f"  [footage-cc] {vid} no bajó ({str(e)[:70]})")
            continue
    raise RuntimeError(f"ningún candidato CC bajó para: {query}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import sys
    q = " ".join(sys.argv[1:]) or "Congreso Colombia"
    print("->", descargar_footage_cc(q))
