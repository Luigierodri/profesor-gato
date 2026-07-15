"""
google_budget.py — Tracker de gasto de Google Cloud (Vertex AI: Veo, Imagen, Lyria).

El pipeline gasta dinero REAL en Vertex AI: Veo (video, ~$0.30 por panel de 6s = el
caro), Imagen ($0.02/img) y Lyria (música, centavos). Antes no había visibilidad
acumulada — el cost_tracker calcula cada costo pero se BORRA cada sesión. Este módulo
acumula el gasto de Google por MES CALENDARIO (Google Cloud factura por mes natural)
en un archivo COMPARTIDO (~/.google_cloud_gasto.json), igual que voice_budget con
ElevenLabs. Sirve para no llevarse sorpresas en la factura de Cloud.

Se alimenta desde cost_tracker._registrar (tipos VIDEO/IMAGEN/MÚSICA = Vertex). NO
cuenta Claude/Anthropic (TOKENS) ni ElevenLabs (VOZ): esas son otras facturas.

OJO: es una ESTIMACIÓN local (los precios del cost_tracker). La factura real está en
Google Cloud Console → Facturación. Pero da una señal temprana muy útil.

CLI:  python -m modules.google_budget          # gasto del mes + desglose por servicio
      python -m modules.google_budget --all      # todos los meses
"""
from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from pathlib import Path

try:
    from config import GOOGLE_CLOUD_ALERTA_USD as _ALERTA
except Exception:
    _ALERTA = 0.0  # 0 = sin alerta

# Mapa tipo del cost_tracker → etiqueta de servicio legible.
_SVC = {"VIDEO": "veo", "IMAGEN": "imagen", "MÚSICA": "lyria"}


def _path() -> Path:
    p = os.getenv("GOOGLE_BUDGET_PATH")
    if p:
        return Path(p)
    return Path.home() / ".google_cloud_gasto.json"


def _mes() -> str:
    return datetime.now().strftime("%Y-%m")


def _load() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict):
    try:
        _path().write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def registrar_tipo(tipo: str, costo: float) -> None:
    """Acumula un costo del cost_tracker si es de Google (VIDEO/IMAGEN/MÚSICA)."""
    svc = _SVC.get(tipo)
    if svc:
        registrar(costo, svc)


def registrar(usd: float, servicio: str = "vertex") -> float:
    """Suma un gasto de Vertex al mes actual. Devuelve el total del mes."""
    if not usd or usd <= 0:
        return gastado()
    d = _load()
    m = _mes()
    mes = d.setdefault(m, {"total": 0.0})
    prev = mes.get("total", 0.0)
    mes["total"] = round(prev + usd, 4)
    mes[servicio] = round(mes.get(servicio, 0.0) + usd, 4)
    _save(d)
    tot = mes["total"]
    if _ALERTA and tot >= _ALERTA > prev:
        print(f"⚠️  [GOOGLE] El gasto estimado de Vertex este mes ({m}) pasó "
              f"${_ALERTA:.2f} → llevas ${tot:.2f}. Revisa Cloud Console si no lo esperabas.")
    return tot


def gastado(mes: str | None = None) -> float:
    return float(_load().get(mes or _mes(), {}).get("total", 0.0))


def resumen(mes: str | None = None) -> dict:
    return _load().get(mes or _mes(), {})


def _cli():
    d = _load()
    if "--all" in sys.argv[1:]:
        if not d:
            print("Sin datos todavía.")
            return
        for m in sorted(d):
            print(f"{m}: ${d[m].get('total', 0):.2f}")
        return
    m = _mes()
    r = d.get(m, {})
    print(f"Gasto estimado Google Cloud (Vertex) — {m}")
    print(f"  TOTAL: ${r.get('total', 0):.2f}")
    for k, v in sorted(r.items()):
        if k != "total":
            print(f"    {k:<8}: ${v:.2f}")
    if _ALERTA:
        print(f"  Alerta configurada: ${_ALERTA:.2f}")
    print(f"  Archivo: {_path()}")
    print("  (estimación local; la factura real está en Google Cloud Console)")


if __name__ == "__main__":
    _cli()
