"""
cost_monitor.py — Monitoreo de costos del pipeline
Proyecto: Profesor Gato

Registro acumulado en logs/cost_tracker.json.
Saldos iniciales en .env (OPENAI_INITIAL_BALANCE, FALAI_INITIAL_BALANCE).
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger("cost_monitor")

BASE_DIR     = Path(__file__).parent.parent
TRACKER_FILE = BASE_DIR / "logs" / "cost_tracker.json"

_ALERTA_USD = 2.00   # alerta si saldo de algún servicio cae por debajo de esto

# Costo de referencia por video con arquitectura de clips (sin openai ni falai)
_COSTO_CLIPS_VIDEO = 0.011


# ─── Persistencia ─────────────────────────────────────────────────────────────

def _cargar() -> dict:
    if not TRACKER_FILE.exists():
        return {
            "runs": [],
            "totals": {
                "anthropic_usd": 0.0,
                "elevenlabs_usd": 0.0,
                "imagenes_usd": 0.0,
                "falai_usd": 0.0,
                "grand_total": 0.0,
                "videos_completados": 0,
            },
        }
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Migrar campo renombrado imagenes_usd → imagenes_usd en archivos existentes
    if "imagenes_usd" in data.get("totals", {}):
        data["totals"]["imagenes_usd"] = data["totals"].pop("imagenes_usd")
    for run in data.get("runs", []):
        if "imagenes_usd" in run:
            run["imagenes_usd"] = run.pop("imagenes_usd")
    return data


def _guardar(data: dict):
    TRACKER_FILE.parent.mkdir(exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _saldos_restantes(totals: dict) -> tuple[float, float]:
    openai_init = float(os.getenv("OPENAI_INITIAL_BALANCE", 0))
    falai_init  = float(os.getenv("FALAI_INITIAL_BALANCE", 0))
    openai_rem  = max(0.0, openai_init - totals.get("imagenes_usd", 0.0))
    falai_rem   = max(0.0, falai_init  - totals.get("falai_usd", 0.0))
    return openai_rem, falai_rem


def _costo_promedio(runs: list[dict], n: int = 5) -> float:
    ultimas = [r for r in runs[-n:] if r.get("total_usd", 0) > 0]
    if not ultimas:
        return _COSTO_CLIPS_VIDEO
    return sum(r["total_usd"] for r in ultimas) / len(ultimas)


def _videos_restantes(falai_rem: float, avg_falai: float) -> str:
    """Devuelve un string legible de cuántos videos quedan por servicio."""
    if avg_falai > 0.001:
        n = int(falai_rem / avg_falai)
        return f"~{n} con fal.ai"
    return "ilimitados (Google Imagen + clips)"


# ─── API pública ──────────────────────────────────────────────────────────────

def mostrar_saldo_inicial():
    """Llamar al inicio del pipeline para mostrar saldo estimado."""
    data   = _cargar()
    totals = data["totals"]
    runs   = data["runs"]

    _, falai_rem = _saldos_restantes(totals)
    avg = _costo_promedio(runs)
    completados = totals.get("videos_completados", 0)

    ultimas = runs[-3:] if len(runs) >= 3 else runs
    avg_falai = (sum(r.get("falai_usd", 0) for r in ultimas) / len(ultimas)) if ultimas else 0
    est = _videos_restantes(falai_rem, avg_falai)

    log.info(
        f"💰 fal.ai ~${falai_rem:.2f}"
        f" | Videos restantes: {est}"
        f" | Completados: {completados} | Avg costo: ~${avg:.3f}"
    )

    if float(os.getenv("FALAI_INITIAL_BALANCE", 0)) > 0 and falai_rem < _ALERTA_USD:
        log.warning(f"  ⚠️  SALDO BAJO — fal.ai: ${falai_rem:.2f} restante")


def registrar_run(run_log: dict):
    """Añade esta ejecución al historial. Llamar al final del pipeline."""
    if not run_log.get("status", "").startswith("success"):
        return

    costos = run_log.get("costos", {})
    entrada = {
        "timestamp":      run_log.get("timestamp", datetime.now().isoformat()),
        "tema":           run_log.get("tema", ""),
        "anthropic_usd":  costos.get("script_usd",    0.0),
        "elevenlabs_usd": costos.get("audio_usd",     0.0),
        "imagenes_usd":     costos.get("imagenes_usd",  0.0),
        "falai_usd":      costos.get("animacion_usd", 0.0),
        "total_usd":      costos.get("total_usd",     0.0),
    }

    data = _cargar()
    data["runs"].append(entrada)

    t = data["totals"]
    for key in ("anthropic_usd", "elevenlabs_usd", "imagenes_usd", "falai_usd"):
        t[key] = round(t.get(key, 0.0) + entrada[key], 4)
    t["grand_total"]        = round(t.get("grand_total", 0.0) + entrada["total_usd"], 4)
    t["videos_completados"] = t.get("videos_completados", 0) + 1

    _guardar(data)


def mostrar_resumen_run(run_log: dict):
    """Imprime el resumen de costos al final del pipeline."""
    costos = run_log.get("costos", {})
    tema   = run_log.get("tema", "")

    ant_usd = costos.get("script_usd",    0.0)
    el_usd  = costos.get("audio_usd",     0.0)
    oa_usd  = costos.get("imagenes_usd",  0.0)
    fa_usd  = costos.get("animacion_usd", 0.0)
    tot_usd = costos.get("total_usd",     0.0)

    # Indicador de método usado
    clips_flag = " (clips reales)" if oa_usd == 0 and fa_usd == 0 else ""

    log.info("─" * 55)
    log.info(f"💸 COSTOS — {tema[:45]}")
    log.info(f"   Script  (Claude):     ${ant_usd:.3f}")
    log.info(f"   Voz     (ElevenLabs): ${el_usd:.3f}")
    log.info(f"   Imágen  (Google/IA):     ${oa_usd:.3f}{clips_flag}")
    log.info(f"   Animac. (fal.ai):     ${fa_usd:.3f}{clips_flag}")
    log.info(f"   ──────────────────────────")
    log.info(f"   TOTAL este video:     ${tot_usd:.3f}")

    # Historial acumulado
    data   = _cargar()
    totals = data["totals"]
    _, falai_rem = _saldos_restantes(totals)
    completados = totals.get("videos_completados", 0)
    grand       = totals.get("grand_total", 0.0)

    log.info(f"\n📊 HISTORIAL ({completados} videos completados):")
    log.info(f"   Claude total:     ${totals.get('anthropic_usd',  0):.3f}")
    log.info(f"   ElevenLabs total: ${totals.get('elevenlabs_usd', 0):.3f}")
    log.info(f"   Imagen total:     ${totals.get('imagenes_usd',   0):.3f}  (Google/IA)")
    log.info(f"   fal.ai total:     ${totals.get('falai_usd',      0):.3f}  → saldo restante ~${falai_rem:.2f}")
    log.info(f"   GRAND TOTAL:      ${grand:.3f}")

    runs = data["runs"]
    ultimas = runs[-3:] if len(runs) >= 3 else runs
    avg_falai = (sum(r.get("falai_usd", 0) for r in ultimas) / len(ultimas)) if ultimas else 0
    est = _videos_restantes(falai_rem, avg_falai)
    log.info(f"\n🎬 Videos restantes estimados: {est}")
    log.info("─" * 55)

    if float(os.getenv("FALAI_INITIAL_BALANCE", 0)) > 0 and falai_rem < _ALERTA_USD:
        log.warning(f"  ⚠️  SALDO BAJO — fal.ai: ${falai_rem:.2f} restante")
