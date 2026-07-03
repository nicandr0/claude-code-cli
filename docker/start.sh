#!/bin/bash
set -e

CC_BRIDGE_PORT="${CC_BRIDGE_PORT:-8642}"
TTYD_PORT="${TTYD_PORT:-7681}"

/home/claude/.venvs/cc-bridge/bin/uvicorn cc_bridge.main:app \
    --host 0.0.0.0 --port "$CC_BRIDGE_PORT" --app-dir /home/claude/cc-bridge &

exec ttyd -p "$TTYD_PORT" -W claude
