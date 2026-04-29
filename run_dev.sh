#!/bin/bash
# Dashboard LLM - Dev instance on port 5001
# Kill previous dev instance first
/opt/dashboard-llm-dev/kill_dev.sh 2>/dev/null
sleep 1
cd /opt/dashboard-llm-dev
setsid env DASHBOARD_HOST=0.0.0.0 DASHBOARD_PORT=5001 /opt/dashboard-llm-dev/venv/bin/python /opt/dashboard-llm-dev/monitor.py > /tmp/dash-dev.log 2>&1 &
disown
sleep 3
curl -s http://127.0.0.1:5001/health && echo " — Dashboard dev pret sur http://localhost:5001"
echo "Logs: tail -f /tmp/dash-dev.log"
echo "Kill: /opt/dashboard-llm-dev/kill_dev.sh"
