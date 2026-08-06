#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CDP_HOST_PORT="${CDP_HOST_PORT:-49325}"

has_arg() {
  local needle="$1"
  shift
  for arg in "$@"; do
    if [[ "$arg" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

if has_arg "--task-id" "$@" || has_arg "--task" "$@"; then
  ARGS=("$@")
elif [[ "$#" -ge 2 ]]; then
  echo "Deprecated: positional form is supported, prefer --task-id <id> --task <prompt>." >&2
  TASK_ID="$1"
  TASK_PROMPT="$2"
  shift 2
  ARGS=(--task-id "$TASK_ID" --task "$TASK_PROMPT" "$@")
else
  echo "Usage: ./scripts/run-agent-browser.sh --task-id <id> --task <prompt> [extra args...]" >&2
  echo "   or: ./scripts/run-agent-browser.sh <task-id> <task prompt> [extra args...]" >&2
  exit 2
fi

if ! has_arg "--cdp-url" "${ARGS[@]}"; then
  ARGS+=(--cdp-url "http://127.0.0.1:${CDP_HOST_PORT}")
fi
if ! has_arg "--max-steps" "${ARGS[@]}"; then
  ARGS+=(--max-steps 80)
fi
if ! has_arg "--yes" "${ARGS[@]}"; then
  ARGS+=(--yes)
fi
if ! has_arg "--strict-chromiumrl-observation" "${ARGS[@]}"; then
  ARGS+=(--strict-chromiumrl-observation)
fi

python3 agent_browser/desktop_agent.py "${ARGS[@]}"
