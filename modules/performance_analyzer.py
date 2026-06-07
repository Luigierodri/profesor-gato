"""
performance_analyzer.py — Loop de aprendizaje del Profesor Gato.

Cierra el ciclo: lee el rendimiento REAL de los videos en YouTube (vistas,
retención, likes, subs) y produce un bloque de "lecciones" que se inyecta en
los prompts para que Claude escriba hacia lo que funciona.

Persistencia: data/performance.json (se commitea de vuelta desde el Action, como
topic_history.json). Es el único lugar duradero porque logs/ es efímero en el runner.

Auth: reusa el token de YouTube de publisher.py. REQUIERE el scope
`yt-analytics.readonly` (ver publisher.SCOPES) — si falta, las funciones degradan
a no-op y NUNCA rompen el pipeline.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, date
from pathlib import Path

log = logging.getLogger("performance")

BASE_DIR  = Path(__file__).parent.parent
PERF_FILE = BASE_DIR / "data" / "performance.json"

# Mínimos para que el bloque de aprendizajes tenga sentido estadístico
MIN_DIAS_PARA_MEDIR = 2     # YouTube Analytics tarda ~1-2 días en cuajar
MIN_VIDEOS_CON_DATOS = 4    # menos de esto = aún no generalizamos


# ── Persistencia ────────────────────────────────────────────────────────────

def _cargar() -> list[dict]:
    if not PERF_FILE.exists():
        return []
    try:
        return json.loads(PERF_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"  performance.json ilegible ({e}) — empezando vacío")
        return []


def _guardar(entradas: list[dict]) -> None:
    PERF_FILE.parent.mkdir(parents=True, exist_ok=True)
    PERF_FILE.write_text(
        json.dumps(entradas, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def registrar_video(video_id: str, titulo: str, categoria: str = "",
                    evento: str = "", gancho: str = "") -> None:
    """Añade (o actualiza) un video al registro persistente al momento de publicar."""
    if not video_id or video_id == "DRY_RUN":
        return
    entradas = _cargar()
    if any(e.get("video_id") == video_id for e in entradas):
        return  # ya registrado
    entradas.append({
        "video_id":  video_id,
        "fecha":     date.today().isoformat(),
        "titulo":    titulo,
        "categoria": categoria,
        "evento":    evento,
        "gancho":    gancho,
        "metricas":  {},   # se llena luego con refrescar_metricas()
    })
    _guardar(entradas)
    log.info(f"  [performance] video registrado: {video_id} ({categoria or '—'})")


# ── Métricas (YouTube Analytics API) ────────────────────────────────────────

def _credenciales():
    """Reusa el token de publisher (mismo token.json/secret)."""
    from publisher import obtener_credenciales
    return obtener_credenciales()


def refrescar_metricas(min_dias: int = MIN_DIAS_PARA_MEDIR) -> int:
    """
    Para cada video publicado hace >= min_dias, consulta YouTube Analytics y
    guarda vistas, retención (%), likes, comentarios, compartidos y subs.
    Devuelve cuántos videos actualizó. Nunca lanza: si algo falla, loguea y sigue.
    """
    entradas = _cargar()
    if not entradas:
        log.info("  [performance] sin videos registrados aún")
        return 0

    hoy = date.today()
    pendientes = []
    for e in entradas:
        try:
            f = date.fromisoformat(e["fecha"])
        except Exception:
            continue
        if (hoy - f).days >= min_dias:
            pendientes.append(e)

    if not pendientes:
        log.info("  [performance] ningún video tiene >= "
                 f"{min_dias} días todavía")
        return 0

    try:
        from googleapiclient.discovery import build
        creds = _credenciales()
        ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.warning(f"  [performance] sin acceso a Analytics ({e}). "
                    "¿Falta el scope yt-analytics.readonly? Se omite.")
        return 0

    ids = [e["video_id"] for e in pendientes]
    actualizados = 0
    # La API acepta hasta 500 ids por filtro (video==id1,id2,...)
    try:
        resp = ya.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=hoy.isoformat(),
            metrics="views,likes,comments,shares,subscribersGained,"
                    "averageViewPercentage,averageViewDuration,estimatedMinutesWatched",
            dimensions="video",
            filters="video==" + ",".join(ids),
            maxResults=500,
        ).execute()
    except Exception as e:
        log.warning(f"  [performance] query Analytics falló: {e}")
        return 0

    cols = [c["name"] for c in resp.get("columnHeaders", [])]
    por_id = {row[0]: dict(zip(cols, row)) for row in resp.get("rows", [])}

    for e in pendientes:
        m = por_id.get(e["video_id"])
        if not m:
            continue
        e["metricas"] = {
            "vistas":        int(m.get("views", 0)),
            "retencion_pct": round(float(m.get("averageViewPercentage", 0)), 1),
            "duracion_media_s": round(float(m.get("averageViewDuration", 0)), 1),
            "likes":         int(m.get("likes", 0)),
            "comentarios":   int(m.get("comments", 0)),
            "compartidos":   int(m.get("shares", 0)),
            "subs_ganados":  int(m.get("subscribersGained", 0)),
            "actualizado":   datetime.now(timezone.utc).isoformat(),
        }
        actualizados += 1

    _guardar(entradas)
    log.info(f"  [performance] métricas actualizadas: {actualizados} video(s)")
    return actualizados


# ── Bloque de aprendizajes para los prompts ─────────────────────────────────

def bloque_aprendizajes(min_videos: int = MIN_VIDEOS_CON_DATOS) -> str:
    """
    Devuelve un bloque de texto en español con lo que funciona (para inyectar en
    el prompt del selector de ángulo / guion). Si no hay datos suficientes,
    devuelve "" (no se inyecta nada).
    """
    entradas = [e for e in _cargar()
                if e.get("metricas", {}).get("vistas") is not None
                and e.get("metricas")]
    con_ret = [e for e in entradas if e["metricas"].get("retencion_pct")]
    if len(con_ret) < min_videos:
        return ""

    # Retención por categoría
    por_cat: dict[str, list[float]] = {}
    vistas_cat: dict[str, list[int]] = {}
    for e in con_ret:
        cat = e.get("categoria") or "sin_categoria"
        por_cat.setdefault(cat, []).append(e["metricas"]["retencion_pct"])
        vistas_cat.setdefault(cat, []).append(e["metricas"].get("vistas", 0))

    def prom(xs):
        return sum(xs) / len(xs) if xs else 0

    ranking = sorted(por_cat.items(), key=lambda kv: prom(kv[1]), reverse=True)
    mejores = ranking[:2]
    peores  = ranking[-1:] if len(ranking) > 2 else []

    # Mejores ganchos por retención (top 3 videos)
    top_videos = sorted(con_ret, key=lambda e: e["metricas"]["retencion_pct"],
                        reverse=True)[:3]

    lineas = ["LECCIONES DE DESEMPEÑO (datos reales de YouTube — guíate por esto):"]
    lineas.append(
        "- Categorías que MÁS retienen: " +
        "; ".join(f"{c} ({prom(r):.0f}% ret., {prom(vistas_cat[c]):.0f} vistas prom.)"
                  for c, r in mejores) + ". Priorízalas cuando el trend lo permita."
    )
    if peores:
        c, r = peores[0]
        lineas.append(
            f"- Categoría que MENOS retiene: {c} ({prom(r):.0f}%). "
            "Solo úsala si el ángulo es excepcional."
        )
    if top_videos:
        lineas.append("- Ganchos que mejor retuvieron (replica su ESTILO, no el tema):")
        for e in top_videos:
            g = (e.get("gancho") or e.get("titulo") or "").strip()
            if g:
                lineas.append(f'    · "{g[:90]}" ({e["metricas"]["retencion_pct"]:.0f}% ret.)')

    return "\n".join(lineas)


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("Refrescando métricas...")
    n = refrescar_metricas()
    print(f"Actualizados: {n}\n")
    bloque = bloque_aprendizajes()
    print(bloque or "(aún no hay datos suficientes para generar aprendizajes)")
