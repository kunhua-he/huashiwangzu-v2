#!/bin/zsh
# backend_watchdog.sh —— 后端守护进程
# 职责：常驻看护后端 uvicorn，崩溃/退出后自动重启；日志超限自动归档，防止磁盘被打满（曾是后端"暴毙"的主因之一）。
# 由 start_backend.sh 通过 nohup 后台拉起；不要直接前台跑。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
HOST="127.0.0.1"
PORT=30004
LOG="$BACKEND_DIR/logs/backend.log"
MAX_LOG_BYTES=52428800   # 50MB，超过就归档清空

cd "$BACKEND_DIR"
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

mkdir -p "$BACKEND_DIR/logs"

while true; do
  # 日志超限归档，防止无限增长打满磁盘
  if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null)" -gt "$MAX_LOG_BYTES" ]; then
    mv "$LOG" "$LOG.old"
  fi
  echo "[watchdog] $(date '+%F %T') starting uvicorn" >> "$LOG"
  python3 -m uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers 1 \
    --log-level info >> "$LOG" 2>&1
  echo "[watchdog] $(date '+%F %T') uvicorn exited (code $?), restarting in 2s" >> "$LOG"
  sleep 2
done
