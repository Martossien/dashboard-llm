#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_KEY="$(basename "$SCRIPT_DIR")"
PID_FILE="$SCRIPT_DIR/../.pids/$SERVICE_KEY.pid"
LOG_FILE="/var/log/llama_qwen36_35b_moe.log"
STOP_TIMEOUT=15
PORT=8030

MODEL_DIR="/home/admin_ia/models/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive"
MODEL="$MODEL_DIR/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf"
MMPROJ="$MODEL_DIR/mmproj-Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-f16.gguf"
LLAMA_SERVER="/home/admin_ia/llama.cpp/build/bin/llama-server"

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

echo "Lancement $SERVICE_KEY sur port $PORT..."

setsid $LLAMA_SERVER \
    --model "$MODEL" \
    --mmproj "$MMPROJ" \
    --port "$PORT" \
    --host 0.0.0.0 \
    --ctx-size 131072 \
    --batch-size 8192 \
    --ubatch-size 4096 \
    --n-gpu-layers 999 \
    --split-mode layer \
    --flash-attn on \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --cache-reuse 512 \
    --parallel 1 \
    --mlock \
    --context-shift \
    --jinja \
    --reasoning auto \
    --metrics \
    --swa-full \
    --temp 0.6 \
    --top-k 20 \
    --top-p 0.95 \
    --min-p 0.0 \
    --repeat-penalty 1.0 \
    --presence-penalty 0.0 \
    --threads 16 \
    --defrag-thold 0.1 \
    --tensor-split 1,1,1,1,1,1,1,1 \
    2>&1 | tee "$LOG_FILE" &

echo $! > "$PID_FILE"
echo "$SERVICE_KEY demarre (PID $(cat "$PID_FILE"))"