#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CONTAINER=${1:-wootz-desktop-browser-replay-001}
CDP_URL=${CDP_URL:-http://127.0.0.1:49325}

docker compose restart

for i in $(seq 1 60); do
  if curl -fsS "$CDP_URL/json/version" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" = "60" ]; then
    echo "ERROR: CDP endpoint did not become healthy: $CDP_URL" >&2
    exit 1
  fi
done

targets=$(curl -fsS "$CDP_URL/json/list" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(sum(1 for x in data if x.get("type")=="page" and not str(x.get("url","")).startswith("devtools://")))')
stats=$(docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' "$CONTAINER" 2>/dev/null || true)
echo "Browser reset complete"
echo "CDP: $CDP_URL"
echo "page_targets: $targets"
echo "stats: ${stats:-unavailable}"
