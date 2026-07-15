"""
voice_budget.py — Guard de presupuesto de ElevenLabs (caracteres por ciclo).

La cuota de ElevenLabs es por CICLO de facturación y COMPARTIDA entre Profesor Gato
y Partida Guardada (misma API key). El endpoint /user da 401, así que no hay forma
de leer el saldo por API → antes te enterabas cuando reventaba a media generación
(401 quota_exceeded). Este módulo lleva un contador LOCAL por ciclo y avisa (o
aborta) ANTES de pasarse.

CONTADOR COMPARTIDO: por defecto escribe en ~/.eleven_voz_presupuesto.json (home del
usuario), el MISMO archivo que usa Partida Guardada → así ambos canales cuentan
contra el mismo cupo. Override con la env var VOZ_BUDGET_PATH.

Se engancha en voice_synthesizer.py:
  - chequear_job(chars_totales) al inicio de un job (pre-flight, avisa/aborta).
  - registrar(chars) después de CADA síntesis exitosa (mismo punto que cost_tracker).

CICLO: la cuota resetea el día VOZ_RESET_DIA de cada mes (aniversario del plan, no
mes calendario). El contador se reinicia solo ese día.

CLI:  python -m modules.voice_budget           # muestra uso/restante del ciclo
      python -m modules.voice_budget --reset    # reinicia el contador del ciclo
      python -m modules.voice_budget --set N     # fija el usado del ciclo a N
"""
from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from pathlib import Path

try:
    from config import (
        ELEVENLABS_LIMITE_MENSUAL as _LIMITE,
        VOZ_RESET_DIA as _RESET_DIA,
        VOZ_PRESUPUESTO_HARD_STOP as _HARD,
    )
except Exception:
    _LIMITE, _RESET_DIA, _HARD = 153_204, 15, False


def _path() -> Path:
    p = os.getenv("VOZ_BUDGET_PATH")
    if p:
        return Path(p)
    # COMPARTIDO con Partida Guardada (misma cuenta ElevenLabs) → un solo archivo en
    # el home del usuario para que ambos repos cuenten contra el mismo cupo.
    return Path.home() / ".eleven_voz_presupuesto.json"


def _ciclo(cuando: datetime | None = None) -> str:
    """Etiqueta del ciclo de facturación actual, anclada al día de reset.
    Ej. con reset=15: el 14-jul → '2026-06-15'; el 15-jul → '2026-07-15'."""
    hoy = cuando or datetime.now()
    if hoy.day >= _RESET_DIA:
        y, m = hoy.year, hoy.month
    else:
        y, m = (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)
    return f"{y}-{m:02d}-{_RESET_DIA:02d}"


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


def usado(ciclo: str | None = None) -> int:
    return int(_load().get(ciclo or _ciclo(), 0))


def restante(ciclo: str | None = None) -> int:
    return _LIMITE - usado(ciclo)


def registrar(n_chars: int) -> int:
    """Suma n_chars al ciclo actual. Llamar tras CADA síntesis exitosa."""
    d = _load()
    c = _ciclo()
    d[c] = int(d.get(c, 0)) + int(n_chars)
    _save(d)
    return d[c]


def chequear_job(n_chars: int, ctx: str = "") -> dict:
    """Pre-flight antes de un job de voz. Avisa del estado del presupuesto y, si
    se pasa del cupo restante con VOZ_PRESUPUESTO_HARD_STOP=True, lanza RuntimeError
    con un mensaje claro (en vez del 401 crudo a media generación)."""
    u, rest = usado(), restante()
    pct = 100 * u / _LIMITE if _LIMITE else 0
    excede = n_chars > rest
    base = (f"[VOZ] Presupuesto ElevenLabs {_ciclo()}: usados {u:,}/{_LIMITE:,} "
            f"({pct:.0f}%) · restan {rest:,} · este job ~{n_chars:,} chars")
    if excede:
        print(f"⚠️  {base}")
        print(f"⚠️  ESTE JOB (~{n_chars:,}) SE PASA del cupo restante ({rest:,}). "
              f"ElevenLabs lo va a rechazar (401 quota_exceeded).")
        if _HARD:
            raise RuntimeError(
                f"Presupuesto de voz agotado ({_ciclo()}): restan {rest:,}, "
                f"el job pide ~{n_chars:,}. Recarga ElevenLabs o espera el reset "
                f"(día {_RESET_DIA}). Desactiva con VOZ_PRESUPUESTO_HARD_STOP=False.")
    elif rest < _LIMITE * 0.15:
        print(f"⚠️  {base}  (queda <15% del ciclo)")
    else:
        print(f"   {base}")
    return {"usado": u, "limite": _LIMITE, "restante": rest,
            "job": n_chars, "excede": excede}


def _cli():
    args = sys.argv[1:]
    if "--reset" in args:
        d = _load(); d[_ciclo()] = 0; _save(d)
        print(f"Contador del ciclo {_ciclo()} reiniciado a 0.")
        return
    if "--set" in args:
        try:
            n = int(args[args.index("--set") + 1])
        except (ValueError, IndexError):
            print("Uso: --set N  (N = caracteres ya usados en el ciclo)")
            return
        d = _load(); d[_ciclo()] = n; _save(d)
        print(f"Ciclo {_ciclo()} fijado a {n:,} chars usados.")
        return
    c = _ciclo()
    print(f"Presupuesto ElevenLabs — ciclo {c} (reset día {_RESET_DIA})")
    print(f"  Límite por ciclo : {_LIMITE:,} chars")
    print(f"  Usados           : {usado(c):,}")
    print(f"  Restantes        : {restante(c):,} ({100 * restante(c) / _LIMITE:.0f}%)")
    print(f"  ≈ {restante(c) // 400} shorts más este ciclo (~400 chars c/u)")
    print(f"  Archivo          : {_path()}")


if __name__ == "__main__":
    _cli()
