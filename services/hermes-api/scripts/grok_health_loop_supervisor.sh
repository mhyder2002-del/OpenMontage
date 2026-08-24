#!/bin/sh
# Detached 10-minute Grok health supervisor. No secrets. Survives agent turn end.
set -eu
ROOT="/Users/hyder/Documents/GitHub/OpenMontage/services/hermes-api"
TICK="$ROOT/scripts/grok_health_tick.py"
DATA="$ROOT/data"
LOG="$DATA/grok-health-supervisor.log"
SENTINEL="$DATA/grok-loop-sentinel.log"
PIDFILE="$DATA/grok-health-loop.pid"

mkdir -p "$DATA"
echo "$$" > "$PIDFILE"

while true; do
  sleep 600
  date -u +"%Y-%m-%dT%H:%M:%SZ supervisor_tick" >> "$LOG"
  python3 "$TICK" >> "$LOG" 2>&1 || echo "tick_failed" >> "$LOG"
  echo 'AGENT_LOOP_TICK_grok_site_health {"prompt":"Read .agents/skills/hermes-grok-health-loop/SKILL.md. Run python3 services/hermes-api/scripts/grok_health_tick.py. Report HTTP codes + flywheel origin only. Unpaid heal only; if prod /readyz is 503 wait for deploy agent, do not clobber VPS. Never log secrets. Keep this loop armed."}' >> "$SENTINEL"
done
