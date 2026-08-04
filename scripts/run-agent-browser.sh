#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "$#" -lt 2 ]]; then
  echo "Usage: ./scripts/run-agent-browser.sh <task-id> <task prompt> [extra args...]" >&2
  exit 2
fi

TASK_ID="$1"
TASK_PROMPT="$2"
shift 2

CDP_HOST_PORT="${CDP_HOST_PORT:-49325}"

python3 agent_browser/desktop_agent.py \
  --task-id "$TASK_ID" \
  --task "$TASK_PROMPT" \
  --cdp-url "http://127.0.0.1:${CDP_HOST_PORT}" \
  --max-steps 80 \
  --yes \
  --strict-chromiumrl-observation \
  "$@"
