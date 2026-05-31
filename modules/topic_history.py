"""
topic_history.py — Historial de temas para evitar repeticiones.

Recuerda qué temas/ángulos ya se publicaron para que el pipeline:
  1. NUNCA repita el mismo ángulo (p.ej. "el Azteca en 3 Mundiales") dentro de
     una ventana amplia (VENTANA_DEDUP_DIAS).
  2. No sature un mismo EVENTO de tendencia: máximo CAP_POR_EVENTO videos por
     evento (p.ej. "mundial_2026") en una ventana móvil (VENTANA_CAP_DIAS).
     Así, si el Mundial está trending 10 días, solo se hacen ~3 videos de él,
     y cada uno desde un ángulo distinto (Azteca, derrama económica, historia…).

Persistencia: data/topic_history.json (carpeta TRACKEADA — `logs/` está en
.gitignore). En GitHub Actions el archivo se commitea de vuelta al repo al final
del run para sobrevivir entre ejecuciones efímeras.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR  = Path(__file__).parent.parent
HIST_PATH = BASE_DIR / "data" / "topic_history.json"

CAP_POR_EVENTO     = 3    # máximo de videos por evento de tendencia...
VENTANA_CAP_DIAS   = 10   # ...dentro de esta ventana móvil de días
VENTANA_DEDUP_DIAS = 30   # no repetir el mismo ángulo dentro de este rango
VENTANA_CATEG_DIAS = 7    # ventana para balancear categorías

# Taxonomía fija de categorías para rotar "un poco de todo".
CATEGORIAS = [
    "historia", "politica", "economia", "sociedad", "deportes",
    "guerras_conflictos", "ciencia", "cultura_pop", "tecnologia",
    "psicologia", "geografia", "salud", "arte", "filosofia",
]


def cargar() -> list[dict]:
    """Lee el historial; lista vacía si no existe o está corrupto."""
    if HIST_PATH.exists():
        try:
            datos = json.loads(HIST_PATH.read_text(encoding="utf-8"))
            return datos if isinstance(datos, list) else []
        except Exception:
            return []
    return []


def _recientes(hist: list[dict], dias: int) -> list[dict]:
    corte = date.today() - timedelta(days=dias)
    out = []
    for e in hist:
        try:
            f = datetime.strptime(e.get("fecha", ""), "%Y-%m-%d").date()
        except Exception:
            continue
        if f >= corte:
            out.append(e)
    return out


def angulos_recientes(hist: list[dict] = None, dias: int = VENTANA_DEDUP_DIAS) -> list[str]:
    """Ángulos ya usados en los últimos `dias` (para no repetirlos)."""
    hist = cargar() if hist is None else hist
    return [e["angulo"] for e in _recientes(hist, dias) if e.get("angulo")]


def eventos_en_tope(hist: list[dict] = None, dias: int = VENTANA_CAP_DIAS,
                    cap: int = CAP_POR_EVENTO) -> list[str]:
    """Eventos que ya alcanzaron el tope de videos en la ventana (hay que evitarlos)."""
    hist = cargar() if hist is None else hist
    counts: dict[str, int] = {}
    for e in _recientes(hist, dias):
        ev = (e.get("evento") or "").strip().lower()
        if ev:
            counts[ev] = counts.get(ev, 0) + 1
    return [ev for ev, c in counts.items() if c >= cap]


def eventos_conocidos(hist: list[dict] = None, dias: int = VENTANA_DEDUP_DIAS) -> list[str]:
    """Tags de evento ya vistos (para que Claude reutilice el MISMO tag por evento)."""
    hist = cargar() if hist is None else hist
    return sorted({(e.get("evento") or "").strip().lower()
                   for e in _recientes(hist, dias) if e.get("evento")})


def categorias_recientes(hist: list[dict] = None, dias: int = VENTANA_CATEG_DIAS) -> list[str]:
    """Categorías de los últimos `dias`, en orden cronológico (la última es la más reciente)."""
    hist = cargar() if hist is None else hist
    recientes = _recientes(hist, dias)
    recientes.sort(key=lambda e: e.get("fecha", ""))
    return [e["categoria"] for e in recientes if e.get("categoria")]


def conteo_categorias(hist: list[dict] = None, dias: int = VENTANA_CATEG_DIAS) -> dict[str, int]:
    """Cuántos videos por categoría en la ventana (para detectar las menos usadas)."""
    hist = cargar() if hist is None else hist
    counts = {c: 0 for c in CATEGORIAS}
    for e in _recientes(hist, dias):
        c = (e.get("categoria") or "").strip().lower()
        if c:
            counts[c] = counts.get(c, 0) + 1
    return counts


def registrar(angulo: str, evento: str = "", trend: str = "",
              categoria: str = "", fecha: str = None) -> list[dict]:
    """Agrega una entrada al historial y lo guarda en disco."""
    hist = cargar()
    hist.append({
        "fecha":     fecha or date.today().strftime("%Y-%m-%d"),
        "angulo":    (angulo or "").strip(),
        "evento":    (evento or "").strip().lower(),
        "categoria": (categoria or "").strip().lower(),
        "trend":     (trend or "").strip(),
    })
    HIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    HIST_PATH.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    return hist
