#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
export VNC_PORT="${VNC_PORT:-5900}"
export NOVNC_PORT="${NOVNC_PORT:-6080}"
export VNC_SCREEN="${VNC_SCREEN:-1365x768x24}"
export CDP_PORT="${CDP_PORT:-9225}"
export CDP_PROXY_PORT="${CDP_PROXY_PORT:-9226}"
export CDP_ADDRESS="${CDP_ADDRESS:-127.0.0.1}"
export START_URL="${START_URL:-about:blank}"
export WTZ_USER_DATA_DIR="${WTZ_USER_DATA_DIR:-/home/wootz/wootz-browser-sessions/default}"
export BROWSER_LANG="${BROWSER_LANG:-en-US}"
export BROWSER_ACCEPT_LANGUAGE="${BROWSER_ACCEPT_LANGUAGE:-en-US,en;q=0.9}"

if [[ ! -x /opt/wootz/chrome/chrome ]]; then
  echo "Wootz browser is missing at /opt/wootz/chrome/chrome" >&2
  exit 1
fi

mkdir -p /tmp/.X11-unix /home/wootz/wootz-browser-sessions "$WTZ_USER_DATA_DIR"
chmod 1777 /tmp/.X11-unix
chown -R wootz:wootz /home/wootz/wootz-browser-sessions

/usr/local/bin/wootz-vnc-start

echo "Starting desktop Wootz browser on DISPLAY=$DISPLAY with internal CDP port $CDP_PORT"

su -s /bin/bash wootz -c \
  "DISPLAY='$DISPLAY' /opt/wootz/chrome/chrome \
    --no-sandbox \
    --disable-dev-shm-usage \
    --remote-debugging-address='$CDP_ADDRESS' \
    --remote-debugging-port='$CDP_PORT' \
    --user-data-dir='$WTZ_USER_DATA_DIR' \
    --lang='$BROWSER_LANG' \
    --accept-lang='$BROWSER_ACCEPT_LANGUAGE' \
    --no-first-run \
    --disable-first-run-ui \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-background-timer-throttling \
    --disable-features=CalculateNativeWinOcclusion \
    --force-device-scale-factor=1 \
    --window-size=1365,768 \
    '$START_URL'" &
browser_pid="$!"

for _ in $(seq 1 100); do
  if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$browser_pid" >/dev/null 2>&1; then
    echo "Wootz browser exited before CDP became ready" >&2
    wait "$browser_pid" || true
    exit 1
  fi
  sleep 0.1
done

if ! curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
  echo "Wootz browser CDP did not become ready on 127.0.0.1:${CDP_PORT}" >&2
  exit 1
fi

echo "Proxying desktop CDP on 0.0.0.0:${CDP_PROXY_PORT} -> 127.0.0.1:${CDP_PORT}"
socat \
  "TCP-LISTEN:${CDP_PROXY_PORT},fork,reuseaddr,bind=0.0.0.0" \
  "TCP:127.0.0.1:${CDP_PORT}" &
proxy_pid="$!"

trap 'kill "$browser_pid" "$proxy_pid" >/dev/null 2>&1 || true' EXIT INT TERM

while true; do
  if ! kill -0 "$browser_pid" >/dev/null 2>&1; then
    echo "Wootz browser exited; stopping CDP proxy so the container can restart" >&2
    wait "$browser_pid" || true
    exit 1
  fi
  if ! kill -0 "$proxy_pid" >/dev/null 2>&1; then
    echo "CDP proxy exited; stopping container" >&2
    wait "$proxy_pid" || true
    exit 1
  fi
  sleep 1
done
