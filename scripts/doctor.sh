#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env.agent-browser ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.agent-browser
  set +a
fi

CDP_HOST_PORT="${CDP_HOST_PORT:-49325}"

echo "Checking desktop Wootz CDP on http://127.0.0.1:${CDP_HOST_PORT} ..."
curl -fsS "http://127.0.0.1:${CDP_HOST_PORT}/json/version"
echo
python3 recorder.py doctor \
  --cdp-url "http://127.0.0.1:${CDP_HOST_PORT}" \
  --command-timeout 20
