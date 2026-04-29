#!/bin/bash
# Kill only the dev dashboard instance on port 5001
# Does NOT touch the production dashboard on port 5000

PID=$(ss -tlnp | grep ':5001' | grep -oP 'pid=\K[0-9]+')
if [ -n "$PID" ]; then
    kill $PID 2>/dev/null
    echo "Dev dashboard (PID $PID, port 5001) stopped."
else
    echo "No dev dashboard found on port 5001."
fi
