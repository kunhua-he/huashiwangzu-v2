#!/usr/bin/env bash
# 起 Agent 后端 sandbox（端口 38010）+ 前端 sandbox（端口 5180）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

# 后端（用主框架的 .venv，连生产库）
cd "$HERE/../../../backend"
.venv/bin/python -m uvicorn --app-dir "$HERE/backend" main:app --port 38010 &
BACKEND_PID=$!

# 前端（proxy 到 Agent 自己的后端 38010，不是主框架）
cd "$HERE" && VITE_SANDBOX_PORT=5180 VITE_API_TARGET=http://127.0.0.1:38010 npm run dev

kill $BACKEND_PID 2>/dev/null || true
