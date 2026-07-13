#!/bin/zsh
# Keep the web process and the single DB task Dispatcher alive. Executors are
# children of the Dispatcher; this script must never scale or claim task work.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
HOST="127.0.0.1"
PORT="33000"
LOG="$BACKEND_DIR/logs/backend.log"
PIDFILE="$BACKEND_DIR/logs/.watchdog.pid"
LOCKDIR="$BACKEND_DIR/logs/.watchdog.lock"
WEB_PID=""
DISPATCHER_PID=""

cd "$BACKEND_DIR"
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  source venv/bin/activate
fi
PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="python3"
mkdir -p "$BACKEND_DIR/logs"

acquire_lock() {
  if mkdir "$LOCKDIR" 2>/dev/null; then
    print -r -- $$ > "$PIDFILE"
    return
  fi
  local old_pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    print -r -- "[watchdog] $(date '+%F %T') another watchdog is active pid=$old_pid" >> "$LOG"
    exit 0
  fi
  rm -rf "$LOCKDIR" "$PIDFILE"
  mkdir "$LOCKDIR"
  print -r -- $$ > "$PIDFILE"
}

stop_pid() {
  local pid="$1" label="$2"
  [[ -n "$pid" ]] || return
  if kill -0 "$pid" 2>/dev/null; then
    print -r -- "[watchdog] $(date '+%F %T') stopping $label pid=$pid" >> "$LOG"
    kill -TERM "$pid" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || return
      sleep 1
    done
    kill -KILL "$pid" 2>/dev/null || true
  fi
}

cleanup() {
  stop_pid "$DISPATCHER_PID" "task dispatcher"
  stop_pid "$WEB_PID" "backend"
  rm -rf "$LOCKDIR" "$PIDFILE"
}

trap cleanup EXIT INT TERM
acquire_lock

start_web() {
  print -r -- "[watchdog] $(date '+%F %T') starting uvicorn port=$PORT" >> "$LOG"
  TASK_WORKER_AUTOSTART=0 "$PYTHON_BIN" -m uvicorn app.main:app \
    --host "$HOST" --port "$PORT" --workers 3 >> "$LOG" 2>&1 &
  WEB_PID=$!
}

start_dispatcher() {
  print -r -- "[watchdog] $(date '+%F %T') starting single task dispatcher" >> "$LOG"
  "$PYTHON_BIN" -m app.task_worker_main >> "$LOG" 2>&1 &
  DISPATCHER_PID=$!
}

while true; do
  if [[ -z "$WEB_PID" ]] || ! kill -0 "$WEB_PID" 2>/dev/null; then
    [[ -n "$WEB_PID" ]] && wait "$WEB_PID" 2>/dev/null || true
    start_web
  fi
  if [[ -z "$DISPATCHER_PID" ]] || ! kill -0 "$DISPATCHER_PID" 2>/dev/null; then
    [[ -n "$DISPATCHER_PID" ]] && wait "$DISPATCHER_PID" 2>/dev/null || true
    start_dispatcher
  fi
  sleep 2
done
