# PHASE_V3_REPORT

Generated: 2026-08-06

## Summary

Implemented the v3 runner hardening and reduced artifact layout. Phase T was already committed as `e5eccdf fix(cdp): phase-t stabilize sessions`. This pass changes the automated desktop runner to use raw CDP execution, non-fatal ChromiumRL capture, JS observation fallback, stable refs, off-fold element exposure, compact artifacts, unified `log.jsonl`, and replay tooling.

## §2.1 Navigation rebind probe

Verdict: the hypothesis was **not reproduced on the stable probe pages**. ChromiumRL responded before and after cross-document navigation without rebind. Rebind still works and is retained because real hostile pages can wedge ChromiumRL after navigation/search.

| stage | method | ok | elapsed_ms | error |
|---|---:|---:|---:|---|
| stable_before | ChromiumRL.saveDOMState | True | 3.917 |  |
| stable_before | ChromiumRL.getAgentObservation | True | 0.771 |  |
| stable_before | Runtime.evaluate | True | 0.464 |  |
| stable_before | Page.getFrameTree | True | 0.314 |  |
| after_cross_document_no_rebind | ChromiumRL.saveDOMState | True | 64.803 |  |
| after_cross_document_no_rebind | ChromiumRL.getAgentObservation | True | 10.101 |  |
| after_cross_document_no_rebind | Runtime.evaluate | True | 0.798 |  |
| after_cross_document_no_rebind | Page.getFrameTree | True | 0.406 |  |
| after_cross_document_rebind | ChromiumRL.saveDOMState | True | 113.258 |  |
| after_cross_document_rebind | ChromiumRL.getAgentObservation | True | 8.866 |  |
| after_cross_document_rebind | Runtime.evaluate | True | 1.495 |  |
| after_cross_document_rebind | Page.getFrameTree | True | 1.15 |  |
| after_same_document_no_rebind | ChromiumRL.saveDOMState | True | 56.692 |  |
| after_same_document_no_rebind | ChromiumRL.getAgentObservation | True | 11.402 |  |
| after_same_document_no_rebind | Runtime.evaluate | True | 1.11 |  |
| after_same_document_no_rebind | Page.getFrameTree | True | 0.879 |  |
| after_same_document_rebind | ChromiumRL.saveDOMState | True | 58.813 |  |
| after_same_document_rebind | ChromiumRL.getAgentObservation | True | 12.072 |  |
| after_same_document_rebind | Runtime.evaluate | True | 1.307 |  |
| after_same_document_rebind | Page.getFrameTree | True | 1.617 |  |

Raw file: `diagnostics/v3/nav_rebind_probe_output.json`.

## §2.6 Identity stability

Selected identity key: `nodeId` first, then `selector`, then `fingerprint`. `nodeId` had 100% unchanged and DOM-mutation match rate and 95% post-scroll match rate.

| phase | key | presence rate | match rate | match count |
|---|---:|---:|---:|---:|
| unchanged | backendNodeId | 0.0 | 0.0 | 0 |
| unchanged | nodeId | 1.0 | 1.0 | 100 |
| unchanged | fingerprint | 1.0 | 1.0 | 68 |
| unchanged | xpath | 0.0 | 0.0 | 0 |
| unchanged | cssSelector | 0.0 | 0.0 | 0 |
| unchanged | selector | 1.0 | 1.0 | 100 |
| unchanged | idx | 1.0 | 1.0 | 100 |
| after_scroll | backendNodeId | 0.0 | 0.0 | 0 |
| after_scroll | nodeId | 1.0 | 0.95 | 95 |
| after_scroll | fingerprint | 1.0 | 0.985 | 67 |
| after_scroll | xpath | 0.0 | 0.0 | 0 |
| after_scroll | cssSelector | 0.0 | 0.0 | 0 |
| after_scroll | selector | 1.0 | 0.95 | 95 |
| after_scroll | idx | 1.0 | 1.0 | 100 |
| after_dom_mutation | backendNodeId | 0.0 | 0.0 | 0 |
| after_dom_mutation | nodeId | 1.0 | 1.0 | 100 |
| after_dom_mutation | fingerprint | 1.0 | 1.0 | 70 |
| after_dom_mutation | xpath | 0.0 | 0.0 | 0 |
| after_dom_mutation | cssSelector | 0.0 | 0.0 | 0 |
| after_dom_mutation | selector | 1.0 | 1.0 | 100 |
| after_dom_mutation | idx | 1.0 | 1.0 | 100 |

Raw file: `diagnostics/v3/identity_stability_probe_output.json`.

## §4.5 Observation rendering measurement

No deep nesting/wrapper-collapse was implemented because the already-pruned observation is small enough and the bigger issue was missing non-interactive visible text. After fixing visible text extraction, stable benchmarks passed. Typical model payload element counts:

| task | status | steps | bytes | wall clock | max elems | Runtime.enable mentions |
|---|---:|---:|---:|---:|---:|---:|
| bench-wiki | success | 2 | 1647083 | 0:06.87 | 99 | 0 |
| bench-books | success | 3 | 1741598 | 0:09.43 | 96 | 0 |
| bench-quotes | success | 2 | 642905 | 0:06.66 | 49 | 0 |
| bench-wiki-js | success | 1 | 1024903 | 0:06.74 | 113 | 0 |
| bench-books-js | success | 4 | 1835095 | 0:19.04 | 93 | 0 |
| bench-quotes-js | success | 2 | 574318 | 0:07.40 | 55 | 0 |
| bench-hostile | failure | 6 | 6105449 | 3:55.68 | 82 | 0 |

Task8/sample page target requirement: model payloads now include up to 99 elements in auto mode and 113 in JS mode on the benchmark pages.

## Acceptance criteria

| # | Result | Evidence |
|---:|---|---|
| 1 | PASS | `diagnostics/v3/nav_rebind_probe_output.json` delivered. |
| 2 | PASS | Cross-document `saveDOMState` succeeded after rebind in the probe. |
| 3 | PARTIAL | `bench-hostile` ran 6 recorded steps and exited cleanly with failure, not traceback/abort. It did not reach 8 steps because the model terminated when page observations became empty/degraded after Amazon search submission. |
| 4 | PASS | ChromiumRL observation/DOM calls route through `chromiumrl_call`; capture tiers degrade and continue. |
| 5 | PASS | `bench-wiki`, `bench-books`, `bench-quotes` all terminated with success. |
| 6 | PASS | Runtime.enable mentions are 0 in all default benchmark `log.jsonl` files. |
| 7 | PASS | Max model element counts: wiki 99, books 96, quotes 49; JS wiki/books also above 50. Quotes has 49 because the page has fewer useful elements. |
| 8 | PASS | Stable refs use `nodeId` and SHA1 refs. Identity probe shows stable IDs on unchanged page. |
| 9 | PASS | `bench-wiki/step_002/diff.json` pure scroll has `interactive_changed: 0`. |
| 10 | PASS | Navigate verifier records include `url`; press branch is implemented for future key steps. |
| 11 | PASS (relative) | Reduced benchmark folders are 0.57–1.84 MB on stable tasks. Previous per-step DOM layout was ~11 MB/step from Phase A measurements. |
| 12 | PASS | JS-only benchmarks all completed successfully after visible text parser fix. |
| 13 | PASS | `scripts/replay-log.py` reconstructs readable trajectories; see `diagnostics/v3/bench-*_replay.txt`. |

## Benchmark results

| task | status | steps | bytes | wall clock | max elems | Runtime.enable mentions |
|---|---:|---:|---:|---:|---:|---:|
| bench-wiki | success | 2 | 1647083 | 0:06.87 | 99 | 0 |
| bench-books | success | 3 | 1741598 | 0:09.43 | 96 | 0 |
| bench-quotes | success | 2 | 642905 | 0:06.66 | 49 | 0 |
| bench-wiki-js | success | 1 | 1024903 | 0:06.74 | 113 | 0 |
| bench-books-js | success | 4 | 1835095 | 0:19.04 | 93 | 0 |
| bench-quotes-js | success | 2 | 574318 | 0:07.40 | 55 | 0 |
| bench-hostile | failure | 6 | 6105449 | 3:55.68 | 82 | 0 |

## Delivered files from §1

All collected files are under `diagnostics/v3/`.

- Runtime/environment: `container-start.sh`, `container_boot_tail_400.log`, `run-agent-browser.sh`, `doctor.sh`, `container_ps_aux.txt`, `json_version.json`, `json_version_pretty.json`, `chrome_version.txt`.
- ChromiumRL domain: protocol/source definitions are UNAVAILABLE in this workspace/image. Searches are saved in `chromiumrl_protocol_file_search.txt`, `chromiumrl_source_candidates.txt`, and `local_chromiumrl_source_candidates.txt`.
- Observation data: `chromiumrl_agent_observation.json`, `observation_element_samples.json`, `a4_analysis.json`, `chromiumrl_dom_first_200_lines.txt`.
- Failure evidence: `nav_rebind_probe_output.json`, `diag-baseline-t8-004_agent_browser_decisions.jsonl`, and step-002 observation copy/unavailable marker.
- Post-change baselines: `bench-*.log`, `benchmark_summary.json`, `bench-*_replay.txt`.

### scripts/container-start.sh

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

### Clean boot log excerpt

Full file: `diagnostics/v3/container_boot_tail_400.log`.

```text
[wootz-cdp-bridge] supervising CDP bridge on container port 9225
[wootz-display] supervising DISPLAY=:99, VNC=5900, noVNC=6080
[wootz-browser] disabled; waiting for WOOTZ_LAUNCH_ENABLED=1
bash: warning: setlocale: LC_ALL: cannot change locale (en_US.UTF-8)
VNC display: :99
Raw VNC: 127.0.0.1:5900 inside container
noVNC: 127.0.0.1:6080 inside container
Starting desktop Wootz browser on DISPLAY=:99 with internal CDP port 9225
VNC display: :99
Raw VNC: 127.0.0.1:5900 inside container
noVNC: 127.0.0.1:6080 inside container
Proxying desktop CDP on 0.0.0.0:9226 -> 127.0.0.1:9225
```

### /json/version

```json
{
  "Browser": "Chrome/152.0.7948.0",
  "Protocol-Version": "1.3",
  "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
  "V8-Version": "15.2.62",
  "WebKit-Version": "537.36 (@6d8a911bee8938b4649482619acf21c471808493)",
  "webSocketDebuggerUrl": "ws://localhost/devtools/browser/4398bf26-6f78-40bc-a2a4-6b5492c04c72"
}
```

### ChromiumRL protocol/source availability

Docker protocol search output:

```text
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/panels/timeline/UIDevtoolsUtils.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/panels/timeline/UIDevtoolsController.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/panels/timeline/UIDevtoolsUtils.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/panels/timeline/UIDevtoolsController.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/models/ai_assistance/tools/ResolveDevtoolsNodePath.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/models/ai_assistance/tools/ResolveDevtoolsNodePath.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/i18n/DevToolsLocale.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/i18n/DevToolsLocale.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/platform/DevToolsPath.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/platform/DevToolsPath.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/root/DevToolsContext.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/root/DevToolsContext.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/protocol_client/DevToolsCDPConnection.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/core/protocol_client/DevToolsCDPConnection.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/entrypoints/devtools_app/devtools_app.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/entrypoints/devtools_app/devtools_app.prebundle.js.map
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/entrypoints/devtools_app/devtools_app.prebundle.js
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/Images/devtools.svg
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/Images/devtools-user-badge.svg
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/Images/devtools-thumbnail.svg
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/Images/devtools-tips.svg
/opt/wootz/chrome/gen/third_party/devtools-frontend/src/front_end/devtools_compatibility.js

```

Local source search candidates:

```text
/data/aayush/task-recorder/agent_browser/desktop_agent.py:5:task-recorder's ChromiumRL saveDOMState/getAgentObservation/compareDOMState
/data/aayush/task-recorder/agent_browser/desktop_agent.py:75:You receive a ChromiumRL/JS observation rendered by this runner. You do not have direct browser
/data/aayush/task-recorder/agent_browser/desktop_agent.py:169:        raise RecorderError(f"ChromiumRL.getAgentObservation returned unexpected payload: {payload}")
/data/aayush/task-recorder/agent_browser/desktop_agent.py:182:    # ChromiumRL element bounds are viewport-relative for normal page content.
/data/aayush/task-recorder/agent_browser/desktop_agent.py:517:                value = await chromiumrl_call(self.cdp, "ChromiumRL.getAgentObservation", {}, timeout=TIMEOUT_OBSERVATION, label="snapshot")
/data/aayush/task-recorder/agent_browser/desktop_agent.py:914:        # critical part for CDP/ChromiumRL commands.
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1110:            ("Runtime.evaluate(js_fallback)" if snapshot.payload.get("model_observation_sources", {}).get("primary") == "js_fallback" else "ChromiumRL.getAgentObservation"),
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1122:            "ChromiumRL.enable",
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1123:            "ChromiumRL.saveDOMState",
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1124:            "ChromiumRL.getAgentObservation",
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1125:            "ChromiumRL.getTouchTraces",
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1286:            traces = await chromiumrl_call(cdp, "ChromiumRL.getTouchTraces", {}, timeout=TIMEOUT_SIGNAL, label="touch_traces")
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1287:            signals = {"captured_at": utc_now(), "commands": {"ChromiumRL.getTouchTraces": {"result": traces, "timing": {"ok": True}}}}
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1289:            signals = {"captured_at": utc_now(), "commands": {"ChromiumRL.getTouchTraces": {"timing": {"ok": False, "error": str(error)}}}}
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1580:                await cdp.send("ChromiumRL.disable", {}, use_session=True, timeout=TIMEOUT_SIGNAL)
/data/aayush/task-recorder/agent_browser/desktop_agent.py:1615:    parser.add_argument("--chromiumrl-full-tracing", action="store_true", help="enable legacy heavy ChromiumRL tracing probes")
/data/aayush/task-recorder/README.md:3:This active folder is for Wootz browser task recording and ChromiumRL verifier artifacts.
/data/aayush/task-recorder/README.md:27:- ChromiumRL supplies the model observation and all verifier artifacts (`getAgentObservation`, DOM state, DOM diff, screenshot, interactions, and touch traces).
/data/aayush/task-recorder/README.md:29:- `agent_browser/desktop_agent.py` is only the bridge/recording loop: it translates the model JSON action into an official CLI command and records the resulting ChromiumRL state.
/data/aayush/task-recorder/README.md:33:## Agent-browser + ChromiumRL
/data/aayush/task-recorder/README.md:68:Each recorded step stores ChromiumRL verifier artifacts under:
/data/aayush/task-recorder/README.md:89:Main ChromiumRL protocols used for verifier artifacts:
/data/aayush/task-recorder/README.md:92:ChromiumRL.getAgentObservation
/data/aayush/task-recorder/README.md:93:ChromiumRL.saveDOMState
/data/aayush/task-recorder/README.md:94:ChromiumRL.compareDOMState
/data/aayush/task-recorder/README.md:95:ChromiumRL.getTouchTraces
/data/aayush/task-recorder/diagnostics/coord_probe.py:13:    r = await cdp.send("ChromiumRL.getAgentObservation", {}, use_session=True, timeout=30)
/data/aayush/task-recorder/diagnostics/t2_probe.py:15:  ('chromiumrl_enable_heavy','ChromiumRL.enable',{'captureTouchTraces':True,'captureLayoutTimings':True,'captureCLSAttribution':True,'captureCompositorLayers':True},True,10.0),
/data/aayush/task-recorder/diagnostics/t2_probe.py:16:  ('chromiumrl_enable_light','ChromiumRL.enable',{'captureTouchTraces':True,'captureLayoutTimings':False,'captureCLSAttribution':False,'captureCompositorLayers':False},True,10.0),
/data/aayush/task-recorder/diagnostics/t2_probe.py:17:  ('chromiumrl_save_dom','ChromiumRL.saveDOMState',{},True,20.0),
/data/aayush/task-recorder/diagnostics/t2_probe.py:18:  ('chromiumrl_observation','ChromiumRL.getAgentObservation',{},True,15.0),
/data/aayush/task-recorder/diagnostics/identity_stability_probe.py:10:    r=await cdp.send("ChromiumRL.getAgentObservation", {}, use_session=True, timeout=10)
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:12:ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:13:ChromiumRL.getAgentObservation ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:27:before: ChromiumRL.saveDOMState ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:28:before: ChromiumRL.saveDOMState ok in 0.9ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:29:before: ChromiumRL.getVisualHash ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:30:before: ChromiumRL.getVisualHash ok in 0.6ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:31:before: ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:32:before: ChromiumRL.getAgentObservation ok in 0.6ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:43:after: ChromiumRL.saveDOMState ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:44:after: ChromiumRL.saveDOMState ok in 4.0ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:45:after: ChromiumRL.getVisualHash ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:46:after: ChromiumRL.getVisualHash ok in 1.1ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:47:after: ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:48:after: ChromiumRL.getAgentObservation ok in 1.7ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:51:ChromiumRL.compareDOMState ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:52:ChromiumRL.compareDOMState ok in 12.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:55:signals: ChromiumRL.getTouchTraces ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:56:signals: ChromiumRL.getTouchTraces ok in 0.8ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:57:signals: ChromiumRL.getLayoutTimings ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:58:signals: ChromiumRL.getLayoutTimings ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:59:signals: ChromiumRL.getCLSAttribution ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:60:signals: ChromiumRL.getCLSAttribution ok in 0.3ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:61:signals: ChromiumRL.getCompositorLayers ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:62:signals: ChromiumRL.getCompositorLayers ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:63:signals: ChromiumRL.getVisualHash ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:64:signals: ChromiumRL.getVisualHash ok in 0.2ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:65:ChromiumRL.captureInteraction ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:66:ChromiumRL.captureInteraction ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:68:ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:69:ChromiumRL.getAgentObservation ok in 0.9ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:83:before: ChromiumRL.saveDOMState ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:84:before: ChromiumRL.saveDOMState ok in 6.1ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:85:before: ChromiumRL.getVisualHash ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:86:before: ChromiumRL.getVisualHash ok in 1.1ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:87:before: ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:88:before: ChromiumRL.getAgentObservation ok in 2.9ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_004.log:99:ERROR: CDP command ChromiumRL.enable timed out after 10.0s
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:12:ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:13:ChromiumRL.getAgentObservation ok in 0.5ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:27:before: ChromiumRL.saveDOMState ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:28:before: ChromiumRL.saveDOMState ok in 1.0ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:29:before: ChromiumRL.getVisualHash ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:30:before: ChromiumRL.getVisualHash ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:31:before: ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:32:before: ChromiumRL.getAgentObservation ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:47:after: ChromiumRL.saveDOMState ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:48:after: ChromiumRL.saveDOMState ok in 5.0ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:49:after: ChromiumRL.getVisualHash ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:50:after: ChromiumRL.getVisualHash ok in 0.9ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:51:after: ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:52:after: ChromiumRL.getAgentObservation ok in 1.3ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:55:ChromiumRL.compareDOMState ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:56:ChromiumRL.compareDOMState ok in 9.1ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:59:signals: ChromiumRL.getTouchTraces ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:60:signals: ChromiumRL.getTouchTraces ok in 0.6ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:61:signals: ChromiumRL.getLayoutTimings ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:62:signals: ChromiumRL.getLayoutTimings ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:63:signals: ChromiumRL.getCLSAttribution ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:64:signals: ChromiumRL.getCLSAttribution ok in 0.6ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:65:signals: ChromiumRL.getCompositorLayers ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:66:signals: ChromiumRL.getCompositorLayers ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:67:signals: ChromiumRL.getVisualHash ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:68:signals: ChromiumRL.getVisualHash ok in 0.3ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:69:ChromiumRL.captureInteraction ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:70:ChromiumRL.captureInteraction ok in 0.4ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:72:ChromiumRL.getAgentObservation ...
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:73:ChromiumRL.getAgentObservation ok in 0.6ms
/data/aayush/task-recorder/diagnostics/t8_baseline_run_003.log:87:before: ChromiumRL.saveDOMState ...
/data/aayush/task-recorder/diagn
```

### GetAgentForFrame source location

UNAVAILABLE: source code is not present in the runtime Docker image or workspace. The boot logs show emitted lines from `third_party/blink/renderer/core/frame/web_frame_widget_impl.cc:2939`, but the surrounding C++ source is not available locally.

### Domain registration / navigation behavior

Based on runtime behavior and logs, ChromiumRL is used via the attached page session. The exact registration scope is UNAVAILABLE without the domain source/protocol definition. Empirically, the stable probe showed commands survive cross-document navigation; hostile pages can still wedge the renderer/domain, so the runner rebinds on main-frame navigation and after ChromiumRL timeouts.

### Complete ChromiumRL observation sample

Full file: `diagnostics/v3/chromiumrl_agent_observation.json`. First 4000 chars inline:

```json
{
  "observation": {
    "url": "https://books.toscrape.com/",
    "title": "All products | Books to Scrape - Sandbox",
    "scroll": {
      "scrollTop": 0,
      "pageHeight": 2549.109375,
      "viewportWidth": 1349,
      "viewportHeight": 624,
      "devicePixelRatio": 1,
      "canScrollDown": true,
      "canScrollUp": false
    },
    "elements": [
      {
        "idx": 0,
        "nodeId": 1586,
        "fingerprint": "A|t:Books to Scrape",
        "tag": "a",
        "selector": "html.no-js > body#default > header.header > div.page_inner > div.row > div.col-sm-8 > a",
        "role": "link",
        "bounds": {
          "x": 49.5,
          "y": 53,
          "width": 220.8125,
          "height": 33
        },
        "centerX": 159.90625,
        "centerY": 69.5,
        "isVisible": true,
        "isInViewport": true,
        "isHitTestable": true,
        "text": "Books to Scrape",
        "context": "We love being scraped!",
        "href": "index.html"
      },
      {
        "idx": 1,
        "nodeId": 1596,
        "fingerprint": "A|t:Home",
        "tag": "a",
        "selector": "html.no-js > body#default > div.container-fluid > div.page_inner > ul.breadcrumb > li:nth-of-type(1) > a",
        "role": "link",
        "bounds": {
          "x": 94.5,
          "y": 169.109375,
          "width": 37.359375,
          "height": 16
        },
        "centerX": 113.1796875,
        "centerY": 177.109375,
        "isVisible": true,
        "isInViewport": true,
        "isHitTestable": true,
        "text": "Home",
        "href": "index.html"
      },
      {
        "idx": 2,
        "nodeId": 1606,
        "fingerprint": "A|t:Books",
        "tag": "a",
        "selector": "html.no-js > body#default > div.container-fluid > div.page_inner > div.row > aside.sidebar > div.side_categories > ul.nav > li > a",
        "role": "link",
        "bounds": {
          "x": 99.5,
          "y": 235.109375,
          "width": 235,
          "height": 40
        },
        "centerX": 217,
        "centerY": 255.109375,
        "isVisible": true,
        "isInViewport": true,
        "isHitTestable": true,
        "text": "Books",
        "context": "Travel | Mystery | Historical Fiction | Sequential Art | Classics | Philosophy | Romance | Womens Fiction | Fiction | Childrens | Religion | Nonfiction | Music | Default | Science Fiction | Sports and",
        "href": "catalogue/category/books_1/index.html"
      },
      {
        "idx": 3,
        "nodeId": 1610,
        "fingerprint": "A|t:Travel",
        "tag": "a",
        "selector": "html.no-js > body#default > div.container-fluid > div.page_inner > div.row > aside.sidebar > div.side_categories > ul.nav > li > ul > li:nth-of-type(1) > a",
        "role": "link",
        "bounds": {
          "x": 124.5,
          "y": 277.109375,
          "width": 38.390625,
          "height": 16
        },
        "centerX": 143.6953125,
        "centerY": 285.109375,
        "isVisible": true,
        "isInViewport": true,
        "isHitTestable": true,
        "text": "Travel",
        "href": "catalogue/category/books/travel_2/index.html"
      },
      {
        "idx": 4,
        "nodeId": 1613,
        "fingerprint": "A|t:Mystery",
        "tag": "a",
        "selector": "html.no-js > body#default > div.container-fluid > div.page_inner > div.row > aside.sidebar > div.side_categories > ul.nav > li > ul > li:nth-of-type(2) > a",
        "role": "link",
        "bounds": {
          "x": 124.5,
          "y": 297.109375,
          "width": 49,
          "height": 16
        },
        "centerX": 149,
        "centerY": 305.109375,
        "isVisible": true,
        "isInViewport": true,
        "isHitTestable": true,
        "text": "Mystery",
        "href": "catalogue/category/books/mystery_3/index.html"
      },
      {
        "idx": 5,
        "nodeId": 1616,
        "fingerprint": "A|t:Historical Fiction",
        "tag": "a",
        "selector": "html.no-js > body#default 
```

### Element samples

```json
[
  {
    "kind": "in_viewport_interactive",
    "element": {
      "idx": 0,
      "nodeId": 1586,
      "fingerprint": "A|t:Books to Scrape",
      "tag": "a",
      "selector": "html.no-js > body#default > header.header > div.page_inner > div.row > div.col-sm-8 > a",
      "role": "link",
      "bounds": {
        "x": 49.5,
        "y": 53,
        "width": 220.8125,
        "height": 33
      },
      "centerX": 159.90625,
      "centerY": 69.5,
      "isVisible": true,
      "isInViewport": true,
      "isHitTestable": true,
      "text": "Books to Scrape",
      "context": "We love being scraped!",
      "href": "index.html"
    }
  },
  {
    "kind": "off_fold",
    "element": {
      "idx": 34,
      "nodeId": 1788,
      "fingerprint": "BUTTON|t:Add to basket",
      "tag": "button",
      "selector": "html.no-js > body#default > div.container-fluid > div.page_inner > div.row > div.col-sm-8 > section > div:nth-of-type(2) > ol.row > li.col-xs-6:nth-of-type(1) > article.product_pod > div.product_price > form > button.btn",
      "role": "button",
      "bounds": {
        "x": 399.5,
        "y": 753.109375,
        "width": 195,
        "height": 34
      },
      "centerX": 497,
      "centerY": 770.109375,
      "isVisible": true,
      "isInViewport": false,
      "isHitTestable": false,
      "text": "Add to basket"
    }
  },
  {
    "kind": "link",
    "element": {
      "idx": 0,
      "nodeId": 1586,
      "fingerprint": "A|t:Books to Scrape",
      "tag": "a",
      "selector": "html.no-js > body#default > header.header > div.page_inner > div.row > div.col-sm-8 > a",
      "role": "link",
      "bounds": {
        "x": 49.5,
        "y": 53,
        "width": 220.8125,
        "height": 33
      },
      "centerX": 159.90625,
      "centerY": 69.5,
      "isVisible": true,
      "isInViewport": true,
      "isHitTestable": true,
      "text": "Books to Scrape",
      "context": "We love being scraped!",
      "href": "index.html"
    }
  }
]
```

### A4 analysis

```json
{
  "source_step": "tasks/task8/step_020",
  "element_keys": [
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
  ],
  "element_count": 64,
  "sample_element": {
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
  },
  "identifier_presence": {
    "backendNodeId": 0,
    "nodeId": 64,
    "fingerprint": 64,
    "xpath": 0,
    "cssSelector": 0,
    "href": 53
  },
  "observation_bytes": 58934,
  "dom_bytes": 5424754
}
```

### DOM first 200 lines

```json
{
  "nodes": [
    {
      "nodeId": 2110,
      "tagName": "html",
      "parentId": 1580,
      "siblingIndex": 0,
      "stablePath": "",
      "cssSelector": "",
      "xpath": "",
      "attributes": [],
      "textContent": "",
      "bounds": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
      },
      "isVisible": false,
      "isInViewport": false,
      "zIndex": 0,
      "keyStyles": {
        "display": "none",
        "color": "",
        "backgroundColor": "",
        "fontSize": "0",
        "fontWeight": "normal",
        "opacity": "0",
        "visibility": "hidden",
        "padding": "",
        "margin": "",
        "width": "",
        "height": "",
        "position": "static",
        "overflow": "visible",
        "whiteSpace": "normal",
        "textAlign": "start",
        "lineHeight": "normal",
        "textDecoration": "none",
        "border": "",
        "borderRadius": ""
      },
      "fingerprint": "html"
    },
    {
      "nodeId": 2111,
      "tagName": "#comment",
      "parentId": 1580,
      "siblingIndex": 0,
      "stablePath": "",
      "cssSelector": "",
      "xpath": "",
      "attributes": [],
      "textContent": "",
      "bounds": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
      },
      "isVisible": false,
      "isInViewport": false,
      "zIndex": 0,
      "keyStyles": {
        "display": "none",
        "color": "",
        "backgroundColor": "",
        "fontSize": "0",
        "fontWeight": "normal",
        "opacity": "0",
        "visibility": "hidden",
        "padding": "",
        "margin": "",
        "width": "",
        "height": "",
        "position": "static",
        "overflow": "visible",
        "whiteSpace": "normal",
        "textAlign": "start",
        "lineHeight": "normal",
        "textDecoration": "none",
        "border": "",
        "borderRadius": ""
      },
      "fingerprint": "#comment"
    },
    {
      "nodeId": 2112,
      "tagName": "#comment",
      "parentId": 1580,
      "siblingIndex": 0,
      "stablePath": "",
      "cssSelector": "",
      "xpath": "",
      "attributes": [],
      "textContent": "",
      "bounds": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
      },
      "isVisible": false,
      "isInViewport": false,
      "zIndex": 0,
      "keyStyles": {
        "display": "none",
        "color": "",
        "backgroundColor": "",
        "fontSize": "0",
        "fontWeight": "normal",
        "opacity": "0",
        "visibility": "hidden",
        "padding": "",
        "margin": "",
        "width": "",
        "height": "",
        "position": "static",
        "overflow": "visible",
        "whiteSpace": "normal",
        "textAlign": "start",
        "lineHeight": "normal",
        "textDecoration": "none",
        "border": "",
        "borderRadius": ""
      },
      "fingerprint": "#comment"
    },
    {
      "nodeId": 2113,
      "tagName": "#comment",
      "parentId": 1580,
      "siblingIndex": 0,
      "stablePath": "",
      "cssSelector": "",
      "xpath": "",
      "attributes": [],
      "textContent": "",
      "bounds": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
      },
      "isVisible": false,
      "isInViewport": false,
      "zIndex": 0,
      "keyStyles": {
        "display": "none",
        "color": "",
        "backgroundColor": "",
        "fontSize": "0",
        "fontWeight": "normal",
        "opacity": "0",
        "visibility": "hidden",
        "padding": "",
        "margin": "",
        "width": "",
        "height": "",
        "position": "static",
        "overflow": "visible",
        "whiteSpace": "normal",
        "textAlign": "start",
        "lineHeight": "normal",
        "textDecoration": "none",
        "border": "",
        "borderRadius": ""
      },
      "fingerprint": "#comment"
    },
    {
      "nodeId": 2114,
      "tagName": "#comment",
      "parentId": 1580,
      "siblingIndex": 0,
      "stablePath": "",
      "cssSelector": "",
      "xpath": "",
      "attributes": [],
      "textContent": "",
      "bounds": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
      },
      "isVisible": false,
      "isInViewport": false,
      "zIndex": 0,
      "keyStyles": {
        "display": "none",
        "color": "",
        "backgroundColor": "",
        "fontSize": "0",
        "fontWeight": "normal",
        "opacity": "0",
        "visibility": "hidden",
        "padding": "",
        "margin": "",
        "width": "",

```

## Disagreements / corrected assumptions

1. The v3 hypothesis that ChromiumRL always dies after cross-document navigation was not reproduced on stable pages. Rebind is still retained because Amazon/Google runs showed real renderer/ChromiumRL wedges.
2. Forcing `--strict-chromiumrl-observation` by default was wrong. It removed non-interactive text needed for verifier-like info tasks. The wrapper now leaves strict mode opt-in.
3. The JS fallback alone initially failed because `visible_text_blocks()` parsed only one CDP response shape. After parsing both shapes, JS-only benchmarks passed.
4. `bench-hostile` did not meet the exact “≥8 steps” criterion. It exited cleanly at 6 recorded steps with a model-declared failure after observations became empty/degraded. This is not a runner crash, but it is not the requested step count.
