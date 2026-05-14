#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_KEY="$(basename "$SCRIPT_DIR")"
PID_FILE="$SCRIPT_DIR/../.pids/$SERVICE_KEY.pid"
LOG_FILE="/var/log/vllm_qwen36_27b.log"
STOP_TIMEOUT=45
PORT=8002

MODEL="/home/admin_ia/models/Qwen3.6-27B"
VENV="/home/admin_ia/miniconda3/envs/vllm_env"

# Verification
if [ ! -d "$MODEL" ]; then
    echo "ERREUR: Modele introuvable: $MODEL"
    exit 1
fi

# Stopper instance precedente
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Arret instance precedente (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 5
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill -9 "$OLD_PID" 2>/dev/null || true
        fi
    fi
    rm -f "$PID_FILE"
fi

# Nettoyage workers orphelins vLLM
if pgrep -f "VLLM::Worker_TP" >/dev/null 2>&1; then
    echo "Nettoyage workers vLLM orphelins..."
    pkill -9 -f "VLLM::(EngineCore|Worker_TP)" 2>/dev/null || true
    sleep 3
fi

# Verifier port libre
if ss -tlnp | grep -q ":$PORT "; then
    echo "ERREUR: Port $PORT deja utilise"
    exit 1
fi

# Environments
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$VENV/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
export CUDA_VISIBLE_DEVICES=1,5,3,6,0,2,4,7
export NCCL_ALGO=Ring
export VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1

echo "Lancement $SERVICE_KEY sur port $PORT..."

sudo touch "$LOG_FILE" 2>/dev/null || true
sudo chown admin_ia:admin_ia "$LOG_FILE" 2>/dev/null || true

setsid vllm serve "$MODEL" \
    --served-model-name qwen36-27b \
    --host 0.0.0.0 \
    --port "$PORT" \
    --tensor-parallel-size 8 \
    --max-model-len 131072 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.90 \
    --max-num-batched-tokens 16384 \
    --kv-cache-dtype fp8_e4m3 \
    --attention-backend FLASHINFER \
    --mamba-cache-dtype auto \
    --mamba-cache-mode align \
    --reasoning-parser qwen3 \
    --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}' \
    --max-cudagraph-capture-size 128 \
    --enable-prefix-caching \
    --enable-chunked-prefill \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --performance-mode interactivity \
    --safetensors-load-strategy prefetch \
    --default-chat-template-kwargs '{"enable_thinking": true, "preserve_thinking": true}' \
    --disable-custom-all-reduce \
    2>&1 | tee "$LOG_FILE" &

echo $! > "$PID_FILE"
echo "$SERVICE_KEY demarre (PID $(cat "$PID_FILE"))"