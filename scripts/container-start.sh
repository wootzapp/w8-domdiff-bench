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
    --no-first-run \
    --disable-first-run-ui \
    --window-size=1365,768 \
    '$START_URL'" &

for _ in $(seq 1 100); do
  if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

echo "Proxying desktop CDP on 0.0.0.0:${CDP_PROXY_PORT} -> 127.0.0.1:${CDP_PORT}"
exec socat \
  "TCP-LISTEN:${CDP_PROXY_PORT},fork,reuseaddr,bind=0.0.0.0" \
  "TCP:127.0.0.1:${CDP_PORT}"
