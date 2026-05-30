#!/usr/bin/env bash
# start_scheduler.sh — Lanza run_daily.py en background con nohup
# Uso: bash start_scheduler.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOGS_DIR/daily_${DATE}.log"

# Verificar que existe el venv
if [ ! -f ".venv/bin/python" ] && [ ! -f ".venv/Scripts/python.exe" ]; then
    echo "ERROR: No se encontró .venv — corre: python -m venv .venv && pip install -r requirements.txt"
    exit 1
fi

# Detectar python del venv (Unix o Windows/WSL)
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON=".venv/Scripts/python.exe"
fi

# Verificar que pytz está instalado
"$PYTHON" -c "import pytz, schedule" 2>/dev/null || {
    echo "Instalando dependencias faltantes..."
    "$PYTHON" -m pip install pytz schedule --quiet
}

# Matar instancia anterior si existe
if [ -f logs/scheduler.pid ]; then
    OLD_PID=$(cat logs/scheduler.pid)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Deteniendo instancia anterior (PID $OLD_PID)..."
        kill "$OLD_PID"
        sleep 1
    fi
fi

# Lanzar en background
nohup "$PYTHON" run_daily.py >> "$LOG_FILE" 2>&1 &
PID=$!

echo $PID > logs/scheduler.pid
echo "============================================"
echo "  Scheduler iniciado (PID $PID)"
echo "  Log: $LOG_FILE"
echo "  Para detener: kill \$(cat logs/scheduler.pid)"
echo "  Para ver logs: tail -f $LOG_FILE"
echo "============================================"
