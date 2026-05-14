#!/bin/bash
# Dashboard LLM — Development instance on port 5001
# Uses conda environment dashboard-llm and config.yaml in the repo directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Kill previous dev instance
"$SCRIPT_DIR/kill_dev.sh" 2>/dev/null || true
sleep 1

# Launch
setsid env DASHBOARD_HOST=0.0.0.0 DASHBOARD_PORT=5001 \
    conda run -n dashboard-llm python -m llm_dashboard > /tmp/dash-dev.log 2>&1 &
disown
sleep 3

# Health check
if curl -sf http://127.0.0.1:5001/health > /dev/null; then
    echo "Dashboard dev pret sur http://localhost:5001"
else
    echo "ERREUR: Dashboard ne repond pas sur le port 5001"
    echo "Logs: tail -f /tmp/dash-dev.log"
    exit 1
fi
echo "Logs: tail -f /tmp/dash-dev.log"
echo "Kill: $SCRIPT_DIR/kill_dev.sh"