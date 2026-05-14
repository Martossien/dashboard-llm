#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_KEY="$(basename "$SCRIPT_DIR")"
PID_FILE="$SCRIPT_DIR/../.pids/$SERVICE_KEY.pid"
LOG_FILE="/var/log/llama_qwen36_27b_base_mtp_ikllama.log"
STOP_TIMEOUT=15
PORT=8030

MODEL_DIR="/home/admin_ia/models/Qwen3.6-27B-ubergarm-MTP"
MODEL="$MODEL_DIR/Qwen3.6-27B-MTP-IQ4_KS.gguf"
LLAMA_SERVER="/home/admin_ia/ik_llama.cpp/build/bin/llama-server"

if [ ! -f "$MODEL" ]; then
    echo "ERREUR: Modele introuvable: $MODEL"
    exit 1
fi

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill -TERM "$OLD_PID" 2>/dev/null || true
        sleep 5
        kill -KILL "$OLD_PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
fi

if ss -tlnp | grep -q ":$PORT "; then
    echo "ERREUR: Port $PORT deja utilise"
    exit 1
fi

sudo touch "$LOG_FILE" 2>/dev/null || true
sudo chown admin_ia:admin_ia "$LOG_FILE" 2>/dev/null || true

export LD_LIBRARY_PATH="$(dirname "$LLAMA_SERVER"):${LD_LIBRARY_PATH:-}"

echo "Lancement $SERVICE_KEY sur port $PORT..."

setsid $LLAMA_SERVER \
    -m "$MODEL" \
    --alias Qwen3.6-27B-MTP \
    --port "$PORT" \
    --host 0.0.0.0 \
    -c 131072 \
    -ngl 999 \
    -sm graph \
    -fa 1 \
    -mqkv \
    -muge \
    -mtp \
    --draft-max 4 \
    --draft-p-min 0.75 \
    -ctk q8_0 \
    -ctv q8_0 \
    -cram 32768 \
    -np 1 \
    -t 16 \
    --no-mmap \
    --mlock \
    --jinja \
    --reasoning auto \
    --metrics \
    -gr \
    --ctx-checkpoints 32 \
    --temp 0.6 \
    --top-k 20 \
    --top-p 0.95 \
    --min-p 0.0 \
    --repeat-penalty 1.0 \
    --presence-penalty 0.0 \
    2>&1 | tee "$LOG_FILE" &

echo $! > "$PID_FILE"
echo "$SERVICE_KEY demarre (PID $(cat "$PID_FILE"))"