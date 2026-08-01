#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

read_dotenv_value() {
  key="$1"
  if [ ! -f .env ]; then
    return 1
  fi
  line="$(grep -E "^[[:space:]]*${key}=" .env | tail -n 1 || true)"
  if [ -z "$line" ]; then
    return 1
  fi
  value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

if [ "$#" -lt 2 ]; then
  echo "Usage: ./scripts/run-task.sh <task-id> <task prompt> [extra args...]" >&2
  echo "Example: ./scripts/run-task.sh task1 \"Go to example.com and summarize the page\" --max-steps 80" >&2
  exit 2
fi

TASK_ID="$1"
TASK_PROMPT="$2"
shift 2

HEADLESS_VALUE="${HEADLESS:-$(read_dotenv_value HEADLESS || printf false)}"
HEADLESS_VALUE="$(printf '%s' "$HEADLESS_VALUE" | tr '[:upper:]' '[:lower:]')"

if [ "$HEADLESS_VALUE" = "true" ]; then
  echo "HEADLESS=true: visible browser and noVNC are disabled."
  echo "To watch the browser, set HEADLESS=false in .env or run: unset HEADLESS"
fi

if [ "$HEADLESS_VALUE" != "true" ] && [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  DISPLAY_NUM="${STAGEHAND_DISPLAY_NUM:-$(read_dotenv_value STAGEHAND_DISPLAY_NUM || printf 92)}"
  VNC_PORT="${STAGEHAND_VNC_PORT:-$(read_dotenv_value STAGEHAND_VNC_PORT || printf 15992)}"
  NOVNC_PORT="${STAGEHAND_NOVNC_PORT:-$(read_dotenv_value STAGEHAND_NOVNC_PORT || printf 16092)}"
  SCREEN="${STAGEHAND_SCREEN:-$(read_dotenv_value STAGEHAND_SCREEN || printf 1365x768x24)}"
  STATE_DIR="/tmp/pure-stagehand-display-${DISPLAY_NUM}"

  mkdir -p "$STATE_DIR"

  if [ ! -s "$STATE_DIR/xvfb.pid" ] || ! kill -0 "$(cat "$STATE_DIR/xvfb.pid")" 2>/dev/null; then
    Xvfb ":${DISPLAY_NUM}" -screen 0 "$SCREEN" -ac >"$STATE_DIR/xvfb.log" 2>&1 &
    echo "$!" >"$STATE_DIR/xvfb.pid"
    sleep 0.5
  fi

  export DISPLAY=":${DISPLAY_NUM}"

  if command -v openbox >/dev/null 2>&1; then
    if [ ! -s "$STATE_DIR/openbox.pid" ] || ! kill -0 "$(cat "$STATE_DIR/openbox.pid")" 2>/dev/null; then
      openbox >"$STATE_DIR/openbox.log" 2>&1 &
      echo "$!" >"$STATE_DIR/openbox.pid"
      sleep 0.2
    fi
  fi

  if command -v x11vnc >/dev/null 2>&1; then
    if [ ! -s "$STATE_DIR/x11vnc.pid" ] || ! kill -0 "$(cat "$STATE_DIR/x11vnc.pid")" 2>/dev/null; then
      x11vnc -display "$DISPLAY" -localhost -rfbport "$VNC_PORT" -forever -shared -nopw >"$STATE_DIR/x11vnc.log" 2>&1 &
      echo "$!" >"$STATE_DIR/x11vnc.pid"
      sleep 0.5
    fi
  fi

  if [ -f "scripts/novnc-bridge.mjs" ]; then
    if [ ! -s "$STATE_DIR/novnc.pid" ] || ! kill -0 "$(cat "$STATE_DIR/novnc.pid")" 2>/dev/null; then
      NOVNC_PORT="$NOVNC_PORT" VNC_PORT="$VNC_PORT" node scripts/novnc-bridge.mjs >"$STATE_DIR/novnc.log" 2>&1 &
      echo "$!" >"$STATE_DIR/novnc.pid"
      sleep 0.5
    fi
  fi

  echo "Visible browser display: DISPLAY=$DISPLAY"
  echo "VNC server: 127.0.0.1:$VNC_PORT"
  echo "noVNC server: 127.0.0.1:$NOVNC_PORT"
  echo "From Windows, tunnel it with:"
  echo "ssh -N -L \"[::1]:39${DISPLAY_NUM}:127.0.0.1:${NOVNC_PORT}\" ubuntu@static.235.31.55.162.clients.your-server.de"
  echo "Then open:"
  echo "http://[::1]:39${DISPLAY_NUM}/vnc.html?resize=scale&autoconnect=1&path=websockify"
fi

npm run run -- --task-id "$TASK_ID" --task "$TASK_PROMPT" "$@"
