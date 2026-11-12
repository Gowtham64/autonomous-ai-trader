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
  # STRATEGY_MODE=daily_trend (default): the backtested daily trend strategy, PAPER unless
  #   TRADING_MODE=live, LIVE_TRADING_ENABLED=true and DAILY_TREND_ALLOW_LIVE=true.
  # STRATEGY_MODE=hourly: the old hourly scanner + AI debate bot. Its backtests show NO
  #   edge after costs (-0.13R/trade over ~3,000 trades); kept only for comparison.
  MODE="${STRATEGY_MODE:-daily_trend}"
  if [ -f .env ] && [ -z "${STRATEGY_MODE:-}" ]; then
    MODE_FROM_ENV=$(grep -E '^STRATEGY_MODE=' .env | tail -1 | cut -d= -f2 | tr -d "\"' ")
    [ -n "$MODE_FROM_ENV" ] && MODE="$MODE_FROM_ENV"
  fi
  PY=.venv/bin/python
  [ -x "$PY" ] || PY=python3
  if [ "$MODE" = "hourly" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor: mode=hourly (no backtested edge)" >> logs/supervisor.log
    "$PY" run_unified_live.py --focus-broker delta >> logs/live.log 2>&1
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor: mode=daily_trend" >> logs/supervisor.log
    "$PY" run_daily_trend.py >> logs/daily_trend.log 2>&1
  fi
  EXIT_CODE=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor: engine exited (code=$EXIT_CODE). Restarting in 30s..." >> logs/supervisor.log
  sleep 30
done
