#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_KEY="$(basename "$SCRIPT_DIR")"
PID_FILE="$SCRIPT_DIR/../.pids/$SERVICE_KEY.pid"
STOP_TIMEOUT=45

if [ ! -f "$PID_FILE" ]; then
    echo "PID file introuvable: $PID_FILE"
    exit 2
fi

PID=$(cat "$PID_FILE")
if ! kill -0 "$PID" 2>/dev/null; then
    echo "Processus $PID deja arrete"
    rm -f "$PID_FILE"
    exit 2
fi

echo "Arret $SERVICE_KEY (PID $PID)..."

kill "$PID" 2>/dev/null || true

echo "Attente ~${STOP_TIMEOUT}s..."
for i in $(seq 1 "$STOP_TIMEOUT"); do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "Arret propre apres ${i}s"
        rm -f "$PID_FILE"
        nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
        exit 0
    fi
    sleep 1
done

echo "SIGKILL apres timeout..."
kill -9 "$PID" 2>/dev/null || true
sleep 2

# Nettoyer les enfants vLLM
echo "Nettoyage processus enfants vLLM..."
pkill -9 -f "VLLM::(EngineCore|Worker_TP)" 2>/dev/null || true

rm -f "$PID_FILE"
echo "$SERVICE_KEY force-kill. VRAM finale:"
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
exit 1