"""
run_daily.py — Scheduler diario Profesor Gato
Ejecuta el pipeline completo todos los días a las 7:00am hora Ciudad de México.

USO:
  python run_daily.py          # Inicia el scheduler (corre indefinidamente)
  python run_daily.py --now    # Dispara el pipeline ahora mismo (para testing)
  python run_daily.py --status # Muestra próxima ejecución y último run

NO se activa al importar. Requiere invocación explícita.
"""

import os
import sys
import json
import subprocess
import argparse
import logging
import time
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, field

import schedule
import pytz
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ── Constantes ─────────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).parent
LOGS_DIR  = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

PYTHON     = str(Path(sys.executable))  # venv actual
MEX_TZ     = pytz.timezone("America/Mexico_City")
HORA_DIARIA = (7, 0)  # 7:00am México

# Banners que emite main.py — usados para rastrear qué paso completó
# (nombre_paso, fragmento del banner, es_critico)
PASOS_PIPELINE = [
    ("trend_detector",      "PASO 1",          False),
    ("script_generator",    "PASO 2",          False),
    ("voice_synthesizer",   "PASO 4",          False),
    ("background_generator","PASO 5 —",        False),
    ("video_animator",      "PASO 5.5",        False),
    ("music_generator",     "PASO 5.9",        False),
    ("video_assembler",     "PASO 6",          True),   # crítico: si falla → no publicar
    ("cost_monitor",        "PIPELINE COMPLETADO", False),
]


# ── Logging ────────────────────────────────────────────────────────────────────

def _setup_logging(log_file: Path | None = None):
    fmt = "%(asctime)s %(message)s"
    datefmt = "[%Y-%m-%d %H:%M:%S]"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(str(log_file), encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt,
                        handlers=handlers, force=True)

log = logging.getLogger("run_daily")


# ── Estado del run ─────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    fecha: str = ""
    inicio: str = ""
    fin: str = ""
    pasos_ok: list  = field(default_factory=list)
    pasos_fail: list = field(default_factory=list)
    pipeline_completo: bool = False
    youtube_url: str = ""
    youtube_id: str = ""
    error_critico: str = ""

    def resumen(self) -> str:
        lineas = [
            "=" * 60,
            "  RESUMEN DEL RUN DIARIO",
            "=" * 60,
            f"  Fecha:     {self.fecha}",
            f"  Inicio:    {self.inicio}",
            f"  Fin:       {self.fin}",
            f"  Pasos OK:  {', '.join(self.pasos_ok) if self.pasos_ok else '—'}",
            f"  Fallidos:  {', '.join(self.pasos_fail) if self.pasos_fail else 'ninguno'}",
        ]
        if self.error_critico:
            lineas.append(f"  ⛔ Abortado en: {self.error_critico}")
        if self.youtube_url:
            lineas.append(f"  🎬 Publicado:  {self.youtube_url}")
            lineas.append(f"  Video ID:     {self.youtube_id}")
        elif self.pipeline_completo:
            lineas.append("  📤 Publisher: no corrió o falló")
        lineas.append("=" * 60)
        return "\n".join(lineas)


# ── Ejecución de subproceso con streaming ─────────────────────────────────────

def _correr_proceso(cmd: list[str], nombre: str) -> tuple[int, list[str]]:
    """
    Ejecuta cmd como subproceso, streameando stdout+stderr al log en tiempo real.
    Devuelve (exit_code, lineas_de_salida).
    """
    log.info(f"▶ Ejecutando: {' '.join(Path(c).name if c.endswith('.py') else c for c in cmd)}")
    lineas = []
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(BASE_DIR),
    )
    for linea in proc.stdout:
        linea = linea.rstrip()
        if linea:
            log.info(f"  │ {linea}")
            lineas.append(linea)
    proc.wait()
    return proc.returncode, lineas


def _detectar_pasos_completados(lineas: list[str]) -> set[str]:
    """Devuelve el conjunto de nombres de pasos cuyos banners aparecieron en la salida."""
    completados = set()
    for nombre, banner, _ in PASOS_PIPELINE:
        if any(banner in l for l in lineas):
            completados.add(nombre)
    return completados


# ── Pipeline principal ────────────────────────────────────────────────────────

def correr_pipeline() -> RunResult:
    resultado = RunResult()
    resultado.fecha  = datetime.now(MEX_TZ).strftime("%Y-%m-%d")
    resultado.inicio = datetime.now(MEX_TZ).strftime("%H:%M:%S")

    log.info("=" * 60)
    log.info("  PROFESOR GATO — Run diario")
    log.info(f"  {datetime.now(MEX_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    log.info("=" * 60)

    # ── MAIN.PY (pasos 1–8) ───────────────────────────────────────────────────
    log.info("\n▶ Fase principal: main.py")
    exit_code, lineas = _correr_proceso([PYTHON, "main.py"], "main")
    pasos_vistos = _detectar_pasos_completados(lineas)

    for nombre, banner, critico in PASOS_PIPELINE:
        if nombre == "cost_monitor":
            # cost_monitor se considera OK si el pipeline completó
            if "cost_monitor" in pasos_vistos or any("PIPELINE COMPLETADO" in l for l in lineas):
                resultado.pasos_ok.append(nombre)
            continue

        if nombre in pasos_vistos:
            resultado.pasos_ok.append(nombre)
        else:
            resultado.pasos_fail.append(nombre)
            if critico and nombre == "video_assembler":
                # Si el banner de PASO 6 nunca apareció = no llegó al ensamble
                # Si apareció pero pipeline no completó = falló en el ensamble
                resultado.error_critico = "video_assembler"

    pipeline_ok = exit_code == 0 and any("PIPELINE COMPLETADO" in l for l in lineas)
    resultado.pipeline_completo = pipeline_ok

    if not pipeline_ok and resultado.error_critico == "video_assembler":
        log.info("\n⛔ video_assembler falló o no se alcanzó — abortando sin publicar")
        resultado.fin = datetime.now(MEX_TZ).strftime("%H:%M:%S")
        log.info(resultado.resumen())
        return resultado

    if not pipeline_ok:
        log.info(f"\n⚠ Pipeline terminó con errores (exit={exit_code}) — intentando publicar de todos modos")

    # ── PUBLISHER.PY ─────────────────────────────────────────────────────────
    log.info("\n▶ Fase publicación: publisher.py")
    pub_code, pub_lineas = _correr_proceso([PYTHON, "publisher.py"], "publisher")

    if pub_code == 0:
        resultado.pasos_ok.append("publisher")
        # Extraer URL del output
        for l in pub_lineas:
            if "youtu.be/" in l:
                partes = l.split("youtu.be/")
                if len(partes) > 1:
                    resultado.youtube_id  = partes[1].split()[0].strip()
                    resultado.youtube_url = f"https://youtu.be/{resultado.youtube_id}"
            elif "Video ID:" in l:
                resultado.youtube_id = l.split("Video ID:")[-1].strip()
    else:
        resultado.pasos_fail.append("publisher")
        log.info(f"  ⚠ publisher.py terminó con exit={pub_code}")

    resultado.fin = datetime.now(MEX_TZ).strftime("%H:%M:%S")
    log.info(resultado.resumen())

    # Guardar resumen en JSON
    _guardar_resumen(resultado)
    return resultado


def _guardar_resumen(r: RunResult):
    ruta = LOGS_DIR / f"daily_{r.fecha}.json"
    datos = {
        "fecha":             r.fecha,
        "inicio":            r.inicio,
        "fin":               r.fin,
        "pasos_ok":          r.pasos_ok,
        "pasos_fail":        r.pasos_fail,
        "pipeline_completo": r.pipeline_completo,
        "youtube_url":       r.youtube_url,
        "youtube_id":        r.youtube_id,
        "error_critico":     r.error_critico,
    }
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"  Resumen guardado: {ruta.name}")


# ── Scheduler ─────────────────────────────────────────────────────────────────

_ultimo_run: date | None = None


def _tick():
    """Corre cada minuto. Dispara el pipeline si son las 7:00am en México y no corrió hoy."""
    global _ultimo_run
    ahora  = datetime.now(MEX_TZ)
    hoy    = ahora.date()
    h, m   = HORA_DIARIA

    if ahora.hour == h and ahora.minute == m and _ultimo_run != hoy:
        _ultimo_run = hoy
        correr_pipeline()


def _proxima_ejecucion() -> str:
    ahora = datetime.now(MEX_TZ)
    h, m  = HORA_DIARIA
    prox  = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    if prox <= ahora:
        from datetime import timedelta
        prox += timedelta(days=1)
    return prox.strftime("%Y-%m-%d %H:%M %Z")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scheduler diario Profesor Gato")
    parser.add_argument("--now",    action="store_true", help="Dispara el pipeline ahora mismo")
    parser.add_argument("--status", action="store_true", help="Muestra próxima ejecución y sale")
    args = parser.parse_args()

    # Configurar log en archivo con fecha de hoy
    hoy_str  = datetime.now(MEX_TZ).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"daily_{hoy_str}.log"
    _setup_logging(log_file)

    log.info(f"Profesor Gato — Scheduler iniciado")
    log.info(f"Log: {log_file}")

    if args.status:
        log.info(f"Próxima ejecución: {_proxima_ejecucion()}")
        log.info(f"Último run: {_ultimo_run or 'nunca en esta sesión'}")
        return

    if args.now:
        log.info("Modo --now: disparando pipeline inmediatamente...")
        correr_pipeline()
        return

    # Modo scheduler normal
    log.info(f"Próxima ejecución programada: {_proxima_ejecucion()}")
    log.info("Corriendo check cada minuto. Ctrl+C para detener.\n")
    schedule.every().minute.do(_tick)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # resolución de 30s, más que suficiente para un job de minuto
    except KeyboardInterrupt:
        log.info("\nScheduler detenido por el usuario.")


if __name__ == "__main__":
    main()
