#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON_BIN="${PYTHON_BIN:-$BACKEND_DIR/venv/bin/python}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-$BACKEND_DIR/.env}"
EFFECTIVE_ENV_FILE="$BACKEND_ENV_FILE"
API_BASE_URL="${PLAYWRIGHT_API_URL:-http://127.0.0.1:8000}"
BACKEND_HOST="${STORY_ROOM_E2E_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${STORY_ROOM_E2E_BACKEND_PORT:-8000}"
BACKEND_LOG_FILE="${STORY_ROOM_E2E_BACKEND_LOG_FILE:-/tmp/novel-agent-story-room-e2e.log}"
POSTGRES_CONTAINER_NAME="${STORY_ROOM_E2E_POSTGRES_CONTAINER:-novel-agent-postgres}"
E2E_DB_NAME="${STORY_ROOM_E2E_DB_NAME:-novel_agent_e2e}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "找不到后端 Python 解释器：$PYTHON_BIN" >&2
  echo "请先执行：python3.11 -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements-dev.txt" >&2
  exit 1
fi

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "找不到后端环境文件：$BACKEND_ENV_FILE" >&2
  echo "请先准备 backend/.env，或通过 BACKEND_ENV_FILE 指定可用环境文件。" >&2
  exit 1
fi

load_env_exports() {
  "$PYTHON_BIN" - "$1" <<'PY'
from __future__ import annotations

import shlex
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(f"export {key}={shlex.quote(value)}")
PY
}

create_e2e_env_file() {
  "$PYTHON_BIN" - "$BACKEND_ENV_FILE" "$EFFECTIVE_ENV_FILE" "$E2E_DB_NAME" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

source_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
db_name = sys.argv[3]

lines: list[str] = []
for raw_line in source_path.read_text(encoding="utf-8").splitlines():
    if raw_line.startswith("DATABASE_URL="):
        key, value = raw_line.split("=", 1)
        raw_value = value.strip()
        quote = raw_value[0] if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {"'", '"'} else ""
        normalized = raw_value[1:-1] if quote else raw_value
        parts = urlsplit(normalized)
        replaced = urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment))
        lines.append(f"{key}={quote}{replaced}{quote}")
        continue
    lines.append(raw_line)

target_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

if ! command -v nc >/dev/null 2>&1; then
  echo "当前环境缺少 nc，无法做端口预检。" >&2
  exit 1
fi

if ! nc -z 127.0.0.1 5432 >/dev/null 2>&1; then
  echo "未检测到本机 PostgreSQL（127.0.0.1:5432）。" >&2
  echo "story-room 的本地 E2E 需要先有可用数据库。" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "前端依赖未安装，请先在 frontend 目录执行 npm ci。" >&2
  exit 1
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${TEMP_ENV_FILE:-}" && -f "${TEMP_ENV_FILE:-}" ]]; then
    rm -f "$TEMP_ENV_FILE"
  fi
}

trap cleanup EXIT

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx "$POSTGRES_CONTAINER_NAME"; then
  echo "[预处理] 检测到 Docker PostgreSQL，重建独立 E2E 数据库：$E2E_DB_NAME"
  docker exec "$POSTGRES_CONTAINER_NAME" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$E2E_DB_NAME' AND pid <> pg_backend_pid();" >/dev/null
  docker exec "$POSTGRES_CONTAINER_NAME" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c \
    "DROP DATABASE IF EXISTS \"$E2E_DB_NAME\";" >/dev/null
  docker exec "$POSTGRES_CONTAINER_NAME" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c \
    "CREATE DATABASE \"$E2E_DB_NAME\";" >/dev/null

  TEMP_ENV_FILE="$(mktemp /tmp/novel-agent-e2e-env.XXXXXX)"
  EFFECTIVE_ENV_FILE="$TEMP_ENV_FILE"
  create_e2e_env_file
fi

eval "$(load_env_exports "$EFFECTIVE_ENV_FILE")"

echo "[预处理] 执行数据库迁移"
(
  cd "$BACKEND_DIR"
  "$PYTHON_BIN" -m alembic upgrade head
)

echo "[1/4] 启动后端"
(
  cd "$BACKEND_DIR"
  nohup "$PYTHON_BIN" -m uvicorn api.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" >"$BACKEND_LOG_FILE" 2>&1 &
  echo $! > /tmp/novel-agent-story-room-e2e.pid
)
BACKEND_PID="$(cat /tmp/novel-agent-story-room-e2e.pid)"

echo "[2/4] 等待后端健康检查"
for attempt in {1..60}; do
  if curl -fsS "$API_BASE_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [[ "$attempt" == "60" ]]; then
    echo "后端未能在预期时间内启动：" >&2
    cat "$BACKEND_LOG_FILE" >&2 || true
    exit 1
  fi
done

echo "[3/4] 运行 story-room Playwright 冒烟"
(
  cd "$FRONTEND_DIR"
  CI=1 PLAYWRIGHT_API_URL="$API_BASE_URL" npx playwright test tests/e2e/story-room-smoke.spec.ts
)

echo "[4/4] story-room E2E 已完成"
