#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-}"
DEFAULT_VENV_PYTHON="$ROOT_DIR/backend/venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$DEFAULT_VENV_PYTHON" ]]; then
    PYTHON_BIN="$DEFAULT_VENV_PYTHON"
  else
    PYTHON_BIN="python3.11"
  fi
fi

if [[ "$PYTHON_BIN" == */* ]]; then
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "找不到 Python 3.11 解释器：$PYTHON_BIN" >&2
    exit 1
  fi
elif ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "找不到 Python 3.11 解释器：$PYTHON_BIN" >&2
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

if [[ -z "$BACKEND_ENV_FILE" ]]; then
  if [[ -f "$ROOT_DIR/backend/.env" ]]; then
    BACKEND_ENV_FILE="$ROOT_DIR/backend/.env"
  else
    BACKEND_ENV_FILE="$ROOT_DIR/backend/.env.example"
  fi
fi

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "找不到后端环境文件：$BACKEND_ENV_FILE" >&2
  exit 1
fi

echo "[1/3] 载入后端环境：$BACKEND_ENV_FILE"
eval "$(load_env_exports "$BACKEND_ENV_FILE")"

cd "$ROOT_DIR"

echo "[2/3] 运行后端 Story Engine 关键测试"
PYTHONPATH=backend "$PYTHON_BIN" -m pytest \
  backend/tests/test_story_engine_* \
  backend/tests/test_preference_service.py \
  backend/tests/test_model_gateway.py \
  -q

echo "[3/3] 运行前端类型检查"
(
  cd "$ROOT_DIR/frontend"
  npm run type-check
)

if [[ "${RUN_MODEL_VERIFY:-0}" == "1" ]]; then
  echo "[附加] 校验模型网关可见模型"
  (
    cd "$ROOT_DIR/backend"
    PYTHONPATH=. "$PYTHON_BIN" scripts/verify_story_engine_models.py
  )
fi

echo "交付级基础检查已完成。"
