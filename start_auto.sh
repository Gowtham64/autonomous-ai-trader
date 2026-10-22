#!/bin/zsh
# Autonomous supervisor: keeps the live trading office running 24/7.
# - Restarts the engine automatically if it ever crashes or exits
# - 30s backoff between restarts to avoid hammering broker APIs
# - All output appended to logs/live.log; supervisor events to logs/supervisor.log

cd "$(dirname "$0")"
mkdir -p logs

# Keep Mac awake (display, system, disk, idle) while the autonomous supervisor is running
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -dimsu -w $$ &
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sleep inhibitor (caffeinate) active." >> logs/supervisor.log
fi

while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor: starting trading engine..." >> logs/supervisor.log
  .venv/bin/python run_unified_live.py --focus-broker delta >> logs/live.log 2>&1
  EXIT_CODE=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor: engine exited (code=$EXIT_CODE). Restarting in 30s..." >> logs/supervisor.log
  sleep 30
done
