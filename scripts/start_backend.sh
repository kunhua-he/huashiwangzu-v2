#!/bin/zsh
# start_backend.sh
#
# Checks if the backend FastAPI server is running on port 33000.
# If not, starts it automatically.
#
# Usage:
#   ./scripts/start_backend.sh                 # start or verify running
#   ./scripts/start_backend.sh --restart       # force restart

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
HOST="127.0.0.1"
PORT=33000
PORT_FILE="$BACKEND_DIR/logs/.backend.port"

cd "$BACKEND_DIR"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

current_port() {
  if [ -f "$PORT_FILE" ]; then
    cat "$PORT_FILE" 2>/dev/null
  else
    echo "$PORT"
  fi
}

is_running_on_port() {
  local port="$1"
  lsof -i :"$port" -P -n 2>/dev/null | grep -q LISTEN
}

backend_pids() {
  local pid command cwd
  pid=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)
  if [ -z "$pid" ]; then
    return 0
  fi
  command=$(ps -p "$pid" -o command= 2>/dev/null)
  cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
  if [[ "$command" == *"uvicorn app.main:app"* && "$cwd" == "$BACKEND_DIR" ]]; then
    echo "$pid"
  fi
}

watchdog_pids() {
  ps -eo pid=,command= | awk -v script="$SCRIPT_DIR/backend_watchdog.sh" '
    index($0, "zsh " script) > 0 || index($0, "zsh " "\"" script "\"") > 0 { print $1 }
  '
}

start_watchdog() {
  mkdir -p "$BACKEND_DIR/logs"
  screen -dmS backend-watchdog zsh "$SCRIPT_DIR/backend_watchdog.sh" > "$BACKEND_DIR/logs/watchdog_screen.log" 2>&1
  echo "[start_backend] Watchdog started in screen session 'backend-watchdog' (auto-restarts backend if it dies)"
}

if [ "$1" = "--restart" ]; then
  echo "[start_backend] Forcing restart..."
  # 先杀守护进程，否则它会立刻把旧 uvicorn 拉起来
  WATCHDOG_PIDS=$(watchdog_pids)
  if [ -n "$WATCHDOG_PIDS" ]; then
    echo "$WATCHDOG_PIDS" | xargs kill 2>/dev/null && echo "[start_backend] Killed watchdog"
  fi
  sleep 1
  WATCHDOG_PIDS=$(watchdog_pids)
  if [ -n "$WATCHDOG_PIDS" ]; then
    echo "$WATCHDOG_PIDS" | xargs kill -9 2>/dev/null && echo "[start_backend] Force killed watchdog"
    sleep 1
  fi
  BACKEND_PIDS=$(backend_pids)
  if [ -n "$BACKEND_PIDS" ]; then
    echo "$BACKEND_PIDS" | xargs kill 2>/dev/null && echo "[start_backend] Killed old project uvicorn"
    sleep 2
  fi
  rm -rf "$BACKEND_DIR/logs/.watchdog.lock" "$BACKEND_DIR/logs/.watchdog.pid" "$PORT_FILE" 2>/dev/null
fi

PORT=$(current_port)
if is_running_on_port "$PORT"; then
  PID=$(lsof -i :"$PORT" -P -n 2>/dev/null | awk '/LISTEN/{print $2}' | head -1)
  echo "[start_backend] Backend already running on $HOST:$PORT (PID $PID)"
  echo "[start_backend] Health check: http://$HOST:$PORT/api/health"
  if [ -z "$(watchdog_pids)" ]; then
    echo "[start_backend] Watchdog not running; starting watchdog to supervise existing backend"
    rm -rf "$BACKEND_DIR/logs/.watchdog.lock" "$BACKEND_DIR/logs/.watchdog.pid" 2>/dev/null
    start_watchdog
  fi
  exit 0
fi

echo "[start_backend] Starting FastAPI on $HOST:$PORT (with auto-restart watchdog) ..."
# 通过守护进程拉起：uvicorn 崩溃/退出会被自动重启，日志超限自动归档（防磁盘打满导致暴毙）
start_watchdog

# Wait for startup
echo "[start_backend] Waiting for backend to become healthy..."
for i in $(seq 1 30); do
  PORT=$(current_port)
  if curl -s "http://$HOST:$PORT/api/health" >/dev/null 2>&1; then
    echo "[start_backend] Backend is healthy after ${i}s on $HOST:$PORT"
    exit 0
  fi
  sleep 1
done

echo "[start_backend] ERROR: Backend did not start within 30s. Check logs:"
echo "  tail -50 $BACKEND_DIR/logs/backend.log"
exit 1
