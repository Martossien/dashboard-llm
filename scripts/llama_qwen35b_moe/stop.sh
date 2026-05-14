#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_KEY="$(basename "$SCRIPT_DIR")"
PID_FILE="$SCRIPT_DIR/../.pids/$SERVICE_KEY.pid"
STOP_TIMEOUT=15

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
kill -TERM "$PID" 2>/dev/null || true

for i in $(seq 1 "$STOP_TIMEOUT"); do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "Arret propre apres ${i}s"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

kill -KILL "$PID" 2>/dev/null || true
sleep 2
rm -f "$PID_FILE"
echo "$SERVICE_KEY force-kill"
exit 1