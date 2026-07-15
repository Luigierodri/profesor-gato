"""
cost_tracker.py — Registro de costos en tiempo real
Proyecto: Profesor Gato

Escribe cada llamada a API en tmp/cost_log.txt con el costo calculado.
Se llama desde background_generator, music_generator, script_generator,
video_animator y voice_synthesizer después de cada llamada exitosa.

USO:
    # Al inicio del pipeline (main.py):
    from modules.cost_tracker import init_session, session_summary
    init_session(tema="La Revolución Francesa")

    # Desde cada módulo:
    from modules import cost_tracker
    cost_tracker.registrar_imagen("imagen-4.0-fast-generate-001", n=1, ctx="Panel 3 (gato)")
    cost_tracker.registrar_tokens("claude-haiku-4-5-20251001", in_tok=2500, out_tok=900, ctx="Script")
    cost_tracker.registrar_audio("lyria-002", duracion_seg=45.0, ctx="Mood: lofi")
    cost_tracker.registrar_video("veo-3.1-lite-generate-preview", duracion_seg=6, ctx="Panel 1")
    cost_tracker.registrar_voz("eleven_multilingual_v2", n_chars=312, ctx="Panel 2 [GATO]")

    # Al final del pipeline:
    resumen = session_summary()  # escribe totales y devuelve dict
"""

from __future__ import annotations

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from modules import google_budget
except Exception:
    google_budget = None

log = logging.getLogger("cost_tracker")

# ─── PRECIOS DE REFERENCIA (USD, mayo 2026) ──────────────────────────────────
# Vertex AI Imagen: https://cloud.google.com/vertex-ai/generative-ai/pricing
# Claude:           https://www.anthropic.com/pricing
# ElevenLabs:       https://elevenlabs.io/pricing  (Creator plan ~$0.18/1k chars)
# Lyria / Veo:      estimados (sin pricing público confirmado aún)

_PRECIOS: dict[str, dict] = {
    # ── Vertex AI Imagen ──
    "imagen-4.0-fast-generate-001": {
        "tipo": "IMAGEN", "por_imagen": 0.020, "estimado": False,
    },
    "imagen-3.0-fast-generate-001": {
        "tipo": "IMAGEN", "por_imagen": 0.020, "estimado": False,
    },
    # ── Vertex AI Lyria (música) ──
    "lyria-002": {
        "tipo": "MÚSICA", "por_segundo": 0.0006, "estimado": True,
    },
    # ── Vertex AI Veo (video) ──
    # Precios oficiales Vertex AI (mayo 2026):
    # veo-3.1-lite:  $0.05/seg  — fuente: cloud.google.com/vertex-ai/generative-ai/pricing
    # veo-3.1-fast:  ~$0.10/seg — estimado, mitad del estándar
    # veo-3.0:       $0.40/seg  — modelo anterior
    "veo-3.1-lite-generate-preview": {
        "tipo": "VIDEO", "por_segundo": 0.050, "estimado": False,
    },
    "veo-3.1-fast-generate-preview": {
        "tipo": "VIDEO", "por_segundo": 0.100, "estimado": True,
    },
    "veo-3.1-generate-preview": {
        "tipo": "VIDEO", "por_segundo": 0.200, "estimado": True,
    },
    "veo-3.0-generate-preview": {
        "tipo": "VIDEO", "por_segundo": 0.400, "estimado": False,
    },
    # ── Claude (Anthropic) ──
    "claude-haiku-4-5-20251001": {
        "tipo": "TOKENS", "input_por_mtoken": 0.80, "output_por_mtoken": 4.00, "estimado": False,
    },
    "claude-sonnet-4-6": {
        "tipo": "TOKENS", "input_por_mtoken": 3.00, "output_por_mtoken": 15.00, "estimado": False,
    },
    "claude-opus-4-7": {
        "tipo": "TOKENS", "input_por_mtoken": 15.00, "output_por_mtoken": 75.00, "estimado": False,
    },
    # ── ElevenLabs ──
    "eleven_multilingual_v2": {
        "tipo": "VOZ", "por_mil_chars": 0.18, "estimado": True,
    },
    "eleven_turbo_v2_5": {
        "tipo": "VOZ", "por_mil_chars": 0.18, "estimado": True,
    },
    # ── OpenAI Imagen ──
    "gpt-image-1": {
        "tipo": "IMAGEN", "por_imagen": 0.040, "estimado": False,
    },
    # ── fal.ai FLUX Schnell ──
    "fal-ai/flux/schnell": {
        "tipo": "IMAGEN", "por_imagen": 0.003, "estimado": True,
    },
}

_TIPO_ORDEN = ["TOKENS", "VOZ", "IMAGEN", "VIDEO", "MÚSICA"]


# ─── ESTADO INTERNO DE LA SESIÓN ─────────────────────────────────────────────

_log_path:       Optional[Path] = None
_session_inicio: Optional[datetime] = None
_entries:        list[dict] = []   # cada dict: {ts, tipo, modelo, desc, costo, estimado}


# ─── API PÚBLICA ──────────────────────────────────────────────────────────────

def init_session(tema: str = "", log_path: Optional[Path] = None) -> Path:
    """
    Inicia una nueva sesión de tracking. Crea / sobreescribe cost_log.txt.
    Llamar desde main.py al inicio del pipeline.
    """
    global _log_path, _session_inicio, _entries

    if log_path is None:
        base = Path(__file__).parent.parent / "tmp"
        base.mkdir(exist_ok=True)
        log_path = base / "cost_log.txt"

    _log_path       = log_path
    _session_inicio = datetime.now()
    _entries        = []

    # IMPORTANTE: usar + explícito — la concatenación implícita de Python haría
    # que `"═" * 66 + "\n" f"..."` concatene el f-string al "\n" y luego * 66
    # repita todo el bloque del medio 66 veces.
    _SEP = "═" * 66
    header = (
        _SEP + "\n" +
        f"PROFESOR GATO — Cost Log  |  {_session_inicio.strftime('%Y-%m-%d %H:%M:%S')}\n" +
        f"Tema: {tema or '(sin tema)'}\n" +
        _SEP + "\n\n"
    )
    _log_path.write_text(header, encoding="utf-8")
    log.info(f"[cost_tracker] Sesión iniciada → {_log_path}")
    return _log_path


def _get_log_path() -> Path:
    """Lazy-init si no se llamó init_session (módulo usado standalone)."""
    global _log_path, _session_inicio, _entries
    if _log_path is None:
        base = Path(__file__).parent.parent / "tmp"
        base.mkdir(exist_ok=True)
        _log_path       = base / "cost_log.txt"
        _session_inicio = datetime.now()
        _entries        = []
        _SEP = "═" * 66
        header = (
            _SEP + "\n" +
            f"PROFESOR GATO — Cost Log (auto-init)  |  {_session_inicio.strftime('%Y-%m-%d %H:%M:%S')}\n" +
            _SEP + "\n\n"
        )
        _log_path.write_text(header, encoding="utf-8")
    return _log_path


def _append(linea: str):
    with open(_get_log_path(), "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def _registrar(tipo: str, modelo: str, desc: str, costo: float, estimado: bool):
    """Escribe una línea en el log y acumula en _entries."""
    ts  = datetime.now().strftime("%H:%M:%S")
    est = "~" if estimado else " "
    modelo_corto = modelo[:32]
    linea = (
        f"{ts}  {tipo:<7}  {modelo_corto:<32}  {desc:<28}  "
        f"{est}${costo:>8.4f}"
    )
    _append(linea)
    _entries.append({
        "ts": ts, "tipo": tipo, "modelo": modelo,
        "desc": desc, "costo": costo, "estimado": estimado,
    })
    # Acumular el gasto de Google (Vertex: VIDEO/IMAGEN/MÚSICA) por mes para tener
    # visibilidad de la factura de Cloud. No cuenta TOKENS (Claude) ni VOZ (ElevenLabs).
    if google_budget is not None:
        try:
            google_budget.registrar_tipo(tipo, costo)
        except Exception:
            pass
    est_nota = " (estimado)" if estimado else ""
    log.info(f"[💰] {tipo} {modelo_corto}: {desc} → ${costo:.4f}{est_nota}")


# ─── FUNCIONES DE REGISTRO POR TIPO ──────────────────────────────────────────

def registrar_tokens(
    modelo: str,
    in_tok: int,
    out_tok: int,
    ctx: str = "",
) -> float:
    """
    Registra una llamada a Claude. Usa los tokens reales del usage.

    Args:
        modelo:  ID del modelo (ej. "claude-haiku-4-5-20251001")
        in_tok:  Tokens de entrada (message.usage.input_tokens)
        out_tok: Tokens de salida (message.usage.output_tokens)
        ctx:     Contexto legible (ej. "Script: La Revolución Francesa")

    Returns:
        Costo en USD.
    """
    p = _PRECIOS.get(modelo, {
        "tipo": "TOKENS", "input_por_mtoken": 3.00, "output_por_mtoken": 15.00, "estimado": True,
    })
    costo = (in_tok * p["input_por_mtoken"] + out_tok * p["output_por_mtoken"]) / 1_000_000
    desc  = f"{in_tok:,} in + {out_tok:,} out tok"
    _registrar("TOKENS", modelo, desc, costo, p.get("estimado", False))
    return costo


def registrar_imagen(
    modelo: str,
    n: int = 1,
    ctx: str = "",
) -> float:
    """
    Registra generación de imagen(s) con Imagen o OpenAI.

    Args:
        modelo: "imagen-4.0-fast-generate-001", "gpt-image-1", etc.
        n:      Cantidad de imágenes generadas.
        ctx:    Contexto (ej. "Panel 3 (gato)")

    Returns:
        Costo total en USD.
    """
    p = _PRECIOS.get(modelo, {"tipo": "IMAGEN", "por_imagen": 0.020, "estimado": True})
    costo = n * p["por_imagen"]
    desc  = f"{n} imagen{'es' if n > 1 else ''}" + (f" — {ctx}" if ctx else "")
    _registrar("IMAGEN", modelo, desc, costo, p.get("estimado", False))
    return costo


def registrar_audio(
    modelo: str,
    duracion_seg: float,
    ctx: str = "",
) -> float:
    """
    Registra generación de música con Lyria.

    Args:
        modelo:       "lyria-002"
        duracion_seg: Segundos de audio generado (aproximado).
        ctx:          Contexto (ej. "Mood: epico")

    Returns:
        Costo estimado en USD.
    """
    p = _PRECIOS.get(modelo, {"tipo": "MÚSICA", "por_segundo": 0.0006, "estimado": True})
    costo = duracion_seg * p["por_segundo"]
    desc  = f"{duracion_seg:.0f}s audio" + (f" — {ctx}" if ctx else "")
    _registrar("MÚSICA", modelo, desc, costo, p.get("estimado", True))
    return costo


def registrar_video(
    modelo: str,
    duracion_seg: float,
    ctx: str = "",
) -> float:
    """
    Registra generación de video con Veo.

    Args:
        modelo:       "veo-3.1-lite-generate-preview"
        duracion_seg: Segundos de video generado.
        ctx:          Contexto (ej. "Panel 1")

    Returns:
        Costo estimado en USD.
    """
    p = _PRECIOS.get(modelo, {"tipo": "VIDEO", "por_segundo": 0.350, "estimado": True})
    costo = duracion_seg * p["por_segundo"]
    desc  = f"{duracion_seg:.0f}s video" + (f" — {ctx}" if ctx else "")
    _registrar("VIDEO", modelo, desc, costo, p.get("estimado", True))
    return costo


def registrar_voz(
    modelo: str,
    n_chars: int,
    ctx: str = "",
) -> float:
    """
    Registra síntesis de voz con ElevenLabs.

    Args:
        modelo:   "eleven_multilingual_v2"
        n_chars:  Cantidad de caracteres sintetizados.
        ctx:      Contexto (ej. "Panel 2 [GATO]")

    Returns:
        Costo estimado en USD.
    """
    p = _PRECIOS.get(modelo, {"tipo": "VOZ", "por_mil_chars": 0.18, "estimado": True})
    costo = (n_chars / 1000) * p["por_mil_chars"]
    desc  = f"{n_chars:,} chars" + (f" — {ctx}" if ctx else "")
    _registrar("VOZ", modelo, desc, costo, p.get("estimado", True))
    return costo


# ─── RESUMEN FINAL ────────────────────────────────────────────────────────────

def session_summary() -> dict:
    """
    Escribe el resumen de la sesión al final del log y lo devuelve como dict.
    Llamar desde main.py al terminar el pipeline.

    Returns:
        {
            "total_usd": float,
            "por_tipo":  {"TOKENS": float, "VOZ": float, ...},
            "n_llamadas": int,
            "tiene_estimados": bool,
        }
    """
    path = _get_log_path()

    # Agrupar por tipo
    por_tipo: dict[str, list[dict]] = {}
    for e in _entries:
        por_tipo.setdefault(e["tipo"], []).append(e)

    total = sum(e["costo"] for e in _entries)
    tiene_estimados = any(e["estimado"] for e in _entries)

    # Construir bloque de resumen
    lineas = [
        "\n" + "─" * 66,
        "RESUMEN POR TIPO",
    ]
    totales_por_tipo = {}
    for tipo in _TIPO_ORDEN:
        if tipo not in por_tipo:
            continue
        items  = por_tipo[tipo]
        subtot = sum(i["costo"] for i in items)
        totales_por_tipo[tipo] = subtot
        hay_est = any(i["estimado"] for i in items)
        est     = "~" if hay_est else " "
        lineas.append(
            f"  {tipo:<8} {est}${subtot:>9.4f}   ({len(items)} llamada{'s' if len(items) > 1 else ''})"
        )

    est_nota = " (algunos valores son estimados — marcados con ~)" if tiene_estimados else ""
    duracion = ""
    if _session_inicio:
        secs = (datetime.now() - _session_inicio).total_seconds()
        m, s = divmod(int(secs), 60)
        duracion = f"  Duración sesión: {m}m {s}s\n"

    lineas += [
        "─" * 66,
        f"  TOTAL SESIÓN:  ${total:.4f} USD{est_nota}",
        duracion.rstrip(),
        "═" * 66,
    ]

    bloque = "\n".join(lineas)
    with open(path, "a", encoding="utf-8") as f:
        f.write(bloque + "\n")

    log.info(f"[cost_tracker] Resumen guardado en {path}")
    log.info(f"[cost_tracker] COSTO TOTAL SESIÓN: ${total:.4f} USD")

    return {
        "total_usd":       round(total, 6),
        "por_tipo":        {k: round(v, 6) for k, v in totales_por_tipo.items()},
        "n_llamadas":      len(_entries),
        "tiene_estimados": tiene_estimados,
        "log_path":        str(path),
    }
