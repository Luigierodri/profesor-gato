"""One-off: llena data/performance.json con los videos YA publicados, cruzando
Analytics (métricas) + Data API (título/fecha) + topic_history (categoría).
Así el loop de aprendizaje tiene datos desde el día 1 en vez de esperar ~4 días.

Uso: python tools/backfill_performance.py
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # repo root para importar publisher
from publisher import obtener_credenciales
from googleapiclient.discovery import build

BASE = Path(__file__).parent.parent
PERF = BASE / "data" / "performance.json"
HIST = BASE / "data" / "topic_history.json"

_STOP = set("de la el los las que por con una uno del al en y o a un cada se su sus "
            "para más cómo qué quién cuándo dónde es son fue ser the of".split())


def _palabras(txt: str) -> set:
    return {w for w in re.findall(r"[a-záéíóúñ]+", (txt or "").lower())
            if len(w) > 3 and w not in _STOP}


def main():
    creds = obtener_credenciales()
    ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # 1) Métricas por video
    rep = ya.reports().query(
        ids="channel==MINE", startDate="2020-01-01", endDate=date.today().isoformat(),
        metrics="views,likes,comments,shares,subscribersGained,"
                "averageViewPercentage,averageViewDuration",
        dimensions="video", sort="-views", maxResults=200,
    ).execute()
    cols = [c["name"] for c in rep.get("columnHeaders", [])]
    metr = {row[0]: dict(zip(cols, row)) for row in rep.get("rows", [])}
    ids = list(metr.keys())
    if not ids:
        print("No hay videos con métricas.")
        return

    # 2) Título + fecha de publicación (Data API)
    info = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        res = yt.videos().list(part="snippet", id=",".join(chunk)).execute()
        for it in res.get("items", []):
            sn = it["snippet"]
            info[it["id"]] = {
                "titulo": sn.get("title", ""),
                "fecha":  sn.get("publishedAt", "")[:10],
            }

    # 3) Categoría desde topic_history (match por solape de palabras con el ángulo)
    hist = json.loads(HIST.read_text(encoding="utf-8")) if HIST.exists() else []

    def categoria_de(titulo: str) -> str:
        pt = _palabras(titulo)
        mejor, mejor_score = "", 0
        for h in hist:
            score = len(pt & _palabras(h.get("angulo", "")))
            if score > mejor_score:
                mejor, mejor_score = h.get("categoria", ""), score
        return mejor if mejor_score >= 2 else ""

    entradas = []
    for vid in ids:
        m = metr[vid]
        nfo = info.get(vid, {})
        titulo = nfo.get("titulo", "")
        entradas.append({
            "video_id":  vid,
            "fecha":     nfo.get("fecha", ""),
            "titulo":    titulo,
            "categoria": categoria_de(titulo),
            "evento":    "",
            "gancho":    "",  # los videos viejos no tienen el panel 1 guardado
            "metricas": {
                "vistas":        int(m.get("views", 0)),
                "retencion_pct": round(float(m.get("averageViewPercentage", 0)), 1),
                "duracion_media_s": round(float(m.get("averageViewDuration", 0)), 1),
                "likes":         int(m.get("likes", 0)),
                "comentarios":   int(m.get("comments", 0)),
                "compartidos":   int(m.get("shares", 0)),
                "subs_ganados":  int(m.get("subscribersGained", 0)),
                "actualizado":   "backfill",
            },
        })

    PERF.write_text(json.dumps(entradas, ensure_ascii=False, indent=2), encoding="utf-8")
    con_cat = sum(1 for e in entradas if e["categoria"])
    print(f"Backfill OK: {len(entradas)} videos -> data/performance.json "
          f"({con_cat} con categoría detectada)")


if __name__ == "__main__":
    main()
