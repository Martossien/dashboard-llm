#!/bin/bash
# Kill the dev dashboard instance on port 5001
set -euo pipefail

PID=$(ss -tlnp 2>/dev/null | grep ':5001' | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null
    echo "Dashboard dev (PID $PID, port 5001) stopped."
else
    echo "No dashboard found on port 5001."
fi