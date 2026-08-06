# Phase A Report

## A1 CLI surface

### A1.a Target/page/tab identifier

UNAVAILABLE: `agent_browser/official_runtime/bin/agent-browser-linux-x64` does not exist in the restored repository, so no CLI flags can be verified. Per rule 3, I am not assuming support for `--target-id`, `--page`, or `--tab`.

### A1.b Click primitive

UNAVAILABLE: CLI binary missing. I cannot verify whether it supports single-call `click x y` or requires `mouse move` + `mouse down` + `mouse up`.

### A1.c Wait-for-load primitive

UNAVAILABLE: CLI binary missing. I cannot verify `wait --load`, `wait --selector`, or `wait --network-idle` support.

### A1.d Snapshot/observation command

UNAVAILABLE: CLI binary missing. I cannot verify whether it exposes `snapshot` or `observe`.

### A1.e Full list of subcommands and flags

UNAVAILABLE: CLI binary missing. The attempted help collection is below.

### Raw --help output

```text
UNAVAILABLE: agent_browser/official_runtime/bin/agent-browser-linux-x64 does not exist

```

## A2 Scripts and container

### A2.a Chrome/Wootz command line

`container-start.sh` launches:

```bash
DISPLAY="$DISPLAY" /opt/wootz/chrome/chrome \
  --no-sandbox \
  --disable-dev-shm-usage \
  --remote-debugging-address="$CDP_ADDRESS" \
  --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$WTZ_USER_DATA_DIR" \
  --lang="$BROWSER_LANG" \
  --accept-lang="$BROWSER_ACCEPT_LANGUAGE" \
  --no-first-run \
  --disable-first-run-ui \
  --window-size=1365,768 \
  "$START_URL"
```

### A2.b Important browser flags

| Flag / behavior | Present? | Evidence |
|---|---:|---|
| `--remote-allow-origins` | no | not present in `container-start.sh` |
| `--disable-dev-shm-usage` | yes | line with `--disable-dev-shm-usage` |
| `--no-first-run` | yes | line with `--no-first-run` |
| `--no-default-browser-check` | no | not present |
| popup blocking configuration | no explicit setting | no `--disable-popup-blocking` / popup flag |
| notification blocking configuration | no explicit setting | no `--disable-notifications` flag |

### A2.c 9225 → 9226 proxy

Implemented by `socat`:

```bash
socat \
  "TCP-LISTEN:${CDP_PROXY_PORT},fork,reuseaddr,bind=0.0.0.0" \
  "TCP:127.0.0.1:${CDP_PORT}"
```

This is a raw TCP proxy. It does not parse WebSocket frames, so it forwards WebSocket bytes unmodified. There is no explicit timeout or max WebSocket frame/message size in the `socat` command; limits are OS/process/socket-level only.

### A2.d START_URL boot tab

Yes. `START_URL` defaults to `about:blank` and is passed as the final Chrome argument. That opens an initial tab at boot. It can compete with the runner's own fresh tab unless the runner pins a target and consistently attaches/captures that target.

### Full text of the three scripts

#### `scripts/run-agent-browser.sh`

```bash
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

```

#### `scripts/container-start.sh`

```bash
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

```

#### `scripts/doctor.sh`

```bash
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

```

## A3 Doctor timings

Live CDP `/json/version` responded, but page-session CDP commands timed out at `Runtime.enable`. Therefore timings for `saveDOMState`, `compareDOMState`, and `getAgentObservation` are unavailable for both blank and heavy states.

| method | blank page ms | heavy page ms | ok? |
|---|---:|---:|---|
| `Runtime.enable` | 30005.1 | 30009.9 | false |
| `saveDOMState` | UNAVAILABLE | UNAVAILABLE | not reached |
| `compareDOMState` | UNAVAILABLE | UNAVAILABLE | not reached |
| `getAgentObservation` | UNAVAILABLE | UNAVAILABLE | not reached |

Optional ChromiumRL methods returning `ok: true`: UNAVAILABLE, doctor did not progress past `Runtime.enable`.

Raw blank doctor:

```text
Runtime.enable ...
Runtime.enable failed after 30005.1ms: CDP command Runtime.enable timed out after 30.0s
ERROR: CDP command Runtime.enable timed out after 30.0s

```

Raw heavy doctor:

```text
Runtime.enable ...
Runtime.enable failed after 30009.9ms: CDP command Runtime.enable timed out after 30.0s
ERROR: CDP command Runtime.enable timed out after 30.0s

```

## A4 Observation payload

Source: `tasks/task8/step_020`.

### A4.a Keys on `result.observation.elements[]`

```json
[
  "accessibleName",
  "bounds",
  "centerX",
  "centerY",
  "context",
  "expanded",
  "fingerprint",
  "href",
  "idx",
  "isHitTestable",
  "isInViewport",
  "isVisible",
  "nodeId",
  "placeholder",
  "role",
  "selected",
  "selector",
  "tag",
  "text",
  "type",
  "value"
]
```

### A4.b Stable node identifiers

Present identifier-like fields and counts:

```json
{
  "backendNodeId": 0,
  "nodeId": 64,
  "fingerprint": 64,
  "xpath": 0,
  "cssSelector": 0,
  "href": 53
}
```

Observed fields: `nodeId`, `fingerprint`, `selector`, and `href`; no `backendNodeId`, no `xpath`, no `cssSelector` key. Stability across two consecutive live observations is UNAVAILABLE because live CDP stalled at `Runtime.enable`. Based only on field semantics, `nodeId` is a CDP frontend node id and should not be treated as stable across sessions; `fingerprint`/`selector` are better candidates but were not live-verified in Phase A.

### A4.c Visible / viewport filtering

The observation is not strictly in-viewport. In the copied step: total elements = 64; `isVisible: false` count = 0; `isInViewport: false` count = 53. So it includes visible off-screen elements.

### A4.d Byte sizes

| artifact | bytes |
|---|---:|
| `chromiumrl_agent_observation.json` | 58934 |
| `chromiumrl_dom.json` | 5424754 |

### Sample element

```json
{
  "idx": 0,
  "nodeId": 6536,
  "fingerprint": "INPUT#search-field-en-small--desktop",
  "tag": "input",
  "selector": "html > body.wp-singular > header.usa-header > div.usa-nav-container > div.grid-col-5 > form.hds-search > input#search-field-en-small--desktop",
  "role": "textbox",
  "bounds": {
    "x": 160.84375,
    "y": 29.484375,
    "width": 200,
    "height": 32
  },
  "centerX": 260.84375,
  "centerY": 45.484375,
  "isVisible": true,
  "isInViewport": true,
  "isHitTestable": true,
  "context": "Search",
  "value": "",
  "placeholder": "Search",
  "type": "search"
}
```

## A5 Coordinate space

### VERDICT: inconclusive

Live probe could not reach observation collection because `Runtime.enable` timed out. No coordinate-space verdict can be made.

### Raw probe output

```text
Runtime.enable ...
Runtime.enable failed after 30009.9ms: CDP command Runtime.enable timed out after 30.0s
Traceback (most recent call last):
  File "/usr/lib/python3.12/asyncio/tasks.py", line 520, in wait_for
    return await fut
           ^^^^^^^^^
  File "/data/aayush/task-recorder/recorder.py", line 332, in wait_for_response
    message = await self.ws.receive()
              ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/ubuntu/.local/lib/python3.12/site-packages/aiohttp/client_ws.py", line 334, in receive
    msg = await self._reader.read()
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "aiohttp/_websocket/reader_c.py", line 118, in read
  File "aiohttp/_websocket/reader_c.py", line 115, in aiohttp._websocket.reader_c.WebSocketDataQueue.read
asyncio.exceptions.CancelledError

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/data/aayush/task-recorder/recorder.py", line 349, in send
    return await asyncio.wait_for(wait_for_response(), timeout=deadline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/tasks.py", line 519, in wait_for
    async with timeouts.timeout(timeout):
  File "/usr/lib/python3.12/asyncio/timeouts.py", line 115, in __aexit__
    raise TimeoutError from exc_val
TimeoutError

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/data/aayush/task-recorder/diagnostics/coord_probe.py", line 40, in <module>
    asyncio.run(main())
  File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/data/aayush/task-recorder/diagnostics/coord_probe.py", line 19, in main
    await enable_page_domains(cdp); await reset_chromiumrl_tracing(cdp)
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/data/aayush/task-recorder/recorder.py", line 585, in enable_page_domains
    _, outcomes[method] = await timed_command(cdp, method, required=required)
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/data/aayush/task-recorder/recorder.py", line 367, in timed_command
    result = await cdp.send(method, params, use_session=True, timeout=timeout)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/data/aayush/task-recorder/recorder.py", line 351, in send
    raise RecorderError(f"CDP command {method} timed out after {deadline:.1f}s") from error
recorder.RecorderError: CDP command Runtime.enable timed out after 30.0s

```

## A6 Baseline

The exact brief command failed because the current wrapper takes positional arguments, not `--task-id/--task` before the wrapper. I then ran the equivalent current-wrapper command; it failed at `Runtime.enable` after 90s.

### Timing table, byte counts, file-type counts

| run | result | wall-clock | task bytes | file-type counts |
|---|---|---:|---:|---|
| exact brief command | argparse error | 0:00.29 | 0 | no task dir |
| current wrapper equivalent | CDP timeout at `Runtime.enable` | 1:30.34 | 377 | `manifest.json`: 1, `actions.json`: 1 |

Exact command output:

```text
usage: desktop_agent.py [-h] --task-id TASK_ID --task TASK [--cdp-url CDP_URL]
                        [--target-url-contains TARGET_URL_CONTAINS]
                        [--output-root OUTPUT_ROOT]
                        [--command-timeout COMMAND_TIMEOUT]
                        [--input-timeout INPUT_TIMEOUT]
                        [--official-agent-browser-binary OFFICIAL_AGENT_BROWSER_BINARY]
                        [--official-agent-browser-timeout OFFICIAL_AGENT_BROWSER_TIMEOUT]
                        [--model-timeout MODEL_TIMEOUT]
                        [--settle-seconds SETTLE_SECONDS]
                        [--max-steps MAX_STEPS] [--max-elements MAX_ELEMENTS]
                        [--resume] [--fresh-tab-url FRESH_TAB_URL]
                        [--keep-browser-data]
                        [--browser-locale BROWSER_LOCALE]
                        [--accept-language ACCEPT_LANGUAGE]
                        [--strict-chromiumrl-observation] [--yes]
                        [--no-capture-all-targets] [--capture-all-targets]
                        [--screenshot-source {cdp,none}]
                        [--screenshot-container SCREENSHOT_CONTAINER]
desktop_agent.py: error: argument --task-id: expected one argument
Command exited with non-zero status 2
	Command being timed: "./scripts/run-agent-browser.sh --task-id diag-baseline-001 --task Search for wireless mouse and open the first product page --yes --max-steps 12"
	User time (seconds): 0.27
	System time (seconds): 0.01
	Percent of CPU this job got: 99%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 0:00.29
	Average shared text size (kbytes): 0
	Average unshared data size (kbytes): 0
	Average stack size (kbytes): 0
	Average total size (kbytes): 0
	Maximum resident set size (kbytes): 38400
	Average resident set size (kbytes): 0
	Major (requiring I/O) page faults: 0
	Minor (reclaiming a frame) page faults: 6967
	Voluntary context switches: 6
	Involuntary context switches: 0
	Swaps: 0
	File system inputs: 0
	File system outputs: 8
	Socket messages sent: 0
	Socket messages received: 0
	Signals delivered: 0
	Page size (bytes): 4096
	Exit status: 2

```

Current-wrapper command output:

```text
Connecting to desktop Wootz CDP at http://127.0.0.1:49325 ...
Runtime.enable ...
Runtime.enable failed after 90008.0ms: CDP command Runtime.enable timed out after 90.0s
ERROR: CDP command Runtime.enable timed out after 90.0s
Command exited with non-zero status 1
	Command being timed: "./scripts/run-agent-browser.sh diag-baseline-001 Search for wireless mouse and open the first product page --yes --max-steps 12"
	User time (seconds): 0.26
	System time (seconds): 0.03
	Percent of CPU this job got: 0%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 1:30.34
	Average shared text size (kbytes): 0
	Average unshared data size (kbytes): 0
	Average stack size (kbytes): 0
	Average total size (kbytes): 0
	Maximum resident set size (kbytes): 38016
	Average resident set size (kbytes): 0
	Major (requiring I/O) page faults: 0
	Minor (reclaiming a frame) page faults: 6981
	Voluntary context switches: 22
	Involuntary context switches: 4
	Swaps: 0
	File system inputs: 0
	File system outputs: 32
	Socket messages sent: 0
	Socket messages received: 0
	Signals delivered: 0
	Page size (bytes): 4096
	Exit status: 1

```

## A7 Static audit

### Table: file | line | issue class | current timeout | note

| file | line | issue class | current timeout | note |
|---|---:|---|---|---|
| `recorder.py` | 249 | `cdp.send` no explicit `timeout=` | recorder `command_timeout`, default 30s | `Target.getTargets` in `page_targets` |
| `recorder.py` | 300 | `cdp.send` no explicit `timeout=` | recorder `command_timeout`, default 30s | `Target.attachToTarget` |
| `recorder.py` | 411 | `cdp.send` no explicit `timeout=` | recorder `command_timeout`, default 30s | `Page.captureScreenshot` |
| `recorder.py` | 591 | `cdp.send` no explicit `timeout=` | recorder `command_timeout`, default 30s | `ChromiumRL.disable` |
| `recorder.py` | 600 | `cdp.send` no explicit `timeout=` | recorder `command_timeout`, default 30s | `ChromiumRL.enable` |
| `recorder.py` | 1346 | `cdp.send` no explicit `timeout=` | recorder `command_timeout`, default 30s | final `ChromiumRL.disable` in doctor |
| `agent_browser/desktop_agent.py` | 674 | `cdp.send` no explicit `timeout=` | agent `command_timeout`, default 90s | `Page.navigate` |
| `agent_browser/desktop_agent.py` | 817 | `cdp.send` no explicit `timeout=` | agent `command_timeout`, default 90s | `Runtime.evaluate` in `selector_center` |
| `agent_browser/desktop_agent.py` | 877 | `cdp.send` no explicit `timeout=` | agent `command_timeout`, default 90s | `Target.createTarget` |
| `agent_browser/desktop_agent.py` | 882 | `cdp.send` no explicit `timeout=` | agent `command_timeout`, default 90s | `Target.activateTarget` |
| `agent_browser/desktop_agent.py` | 148 | subprocess exception surface | official CLI timeout default 30s | `subprocess.run(... timeout=...)` can raise `subprocess.TimeoutExpired`; current `main()` catches `RecorderError`, `aiohttp.ClientError`, `asyncio.TimeoutError`, not `TimeoutExpired` |
| `recorder.py` | 654 | subprocess exception surface | ADB screenshot timeout from config | `asyncio.create_subprocess_exec` catches `FileNotFoundError` and communicate timeout, but other `OSError` process-launch failures may propagate |
| `recorder.py` | 584-589 | `Page.enable` missing | n/a | `enable_page_domains` calls `Runtime.enable`, `DOM.enable`; not `Page.enable` |
| `recorder.py` | 332-335 | CDP events discarded | n/a | `send()` reads WebSocket messages in a per-call loop and ignores messages whose `id` is not the current request. CDP events have no `id`, so they are skipped and not handled/logged. Concurrent sends can also steal each other's responses. |

## Blockers

1. `agent_browser/official_runtime/bin/agent-browser-linux-x64` is missing, so A1 CLI surface questions and any CLI flag-gated B2 decisions are unanswered.
2. Live CDP page-session commands are currently stalled: both doctor and coordinate probe timed out on `Runtime.enable`. This blocks A3 timing details, A5 coordinate verdict, and a meaningful A6 behavioral baseline.
3. The A6 command in the brief does not match the current `scripts/run-agent-browser.sh` interface. The wrapper expects positional `<task-id> <task prompt> [extra args...]`.

**STOP:** Phase A is complete. Phase B has not been started.
