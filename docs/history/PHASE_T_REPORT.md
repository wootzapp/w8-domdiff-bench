# Phase T Report

## Status

**Phase T did not fully pass.** CDP health, dialog handling, and coordinate-space checks now pass, but **T-8 exact baseline fails**: the model chooses Amazon, clicks Amazon's `Continue shopping` interstitial, and that page target stops answering ChromiumRL `saveDOMState` / `getAgentObservation`. Because T-8 is an exit criterion, I did **not** proceed to Phase B.

## T-1 Browser clean slate and boot log

Command run: `docker compose down && docker compose up -d`.

Boot log: `diagnostics/t1_container_boot.log`.

Assessment: Docker health became `healthy`. No renderer crash, OOM kill, segmentation fault, or shared-memory fatal error was found. The boot log is not perfectly quiet: it contains expected container/browser DBus and GCM errors plus ChromiumRL startup messages like `GetAgentForFrame returned null`, but no fatal boot blocker.

Crash/OOM/shm keyword hits: `none fatal found`.

## T-2 CDP command matrix

Probe script: `diagnostics/t2_probe.py`.

Results file: `diagnostics/t2_probe_results.json`.

| target | command | ok | elapsed_ms | error |
|---|---:|---:|---:|---|
| existing_about_or_selected | runtime_eval_no_enable | True | 90.735 |  |
| existing_about_or_selected | runtime_enable | True | 130.898 |  |
| existing_about_or_selected | dom_enable | True | 88.999 |  |
| existing_about_or_selected | page_enable | True | 90.731 |  |
| existing_about_or_selected | chromiumrl_enable_heavy | True | 89.838 |  |
| existing_about_or_selected | chromiumrl_enable_light | True | 89.34 |  |
| existing_about_or_selected | chromiumrl_save_dom | True | 47.992 |  |
| existing_about_or_selected | chromiumrl_observation | True | 90.277 |  |
| fresh_about_blank | runtime_eval_no_enable | True | 47.446 |  |
| fresh_about_blank | runtime_enable | True | 131.111 |  |
| fresh_about_blank | dom_enable | True | 89.41 |  |
| fresh_about_blank | page_enable | True | 90.089 |  |
| fresh_about_blank | chromiumrl_enable_heavy | True | 90.039 |  |
| fresh_about_blank | chromiumrl_enable_light | True | 89.329 |  |
| fresh_about_blank | chromiumrl_save_dom | True | 89.563 |  |
| fresh_about_blank | chromiumrl_observation | True | 88.796 |  |
| heavy_real_page | runtime_eval_no_enable | True | 89.847 |  |
| heavy_real_page | runtime_enable | True | 131.085 |  |
| heavy_real_page | dom_enable | True | 48.268 |  |
| heavy_real_page | page_enable | True | 88.714 |  |
| heavy_real_page | chromiumrl_enable_heavy | True | 89.429 |  |
| heavy_real_page | chromiumrl_enable_light | True | 90.028 |  |
| heavy_real_page | chromiumrl_save_dom | True | 867.282 |  |
| heavy_real_page | chromiumrl_observation | True | 108.625 |  |

Conclusion:

- `Runtime.evaluate` works without `Runtime.enable`.
- `Runtime.enable`, `DOM.enable`, and `Page.enable` all worked after clean restart.
- `DOM.enable` is not required by current recorder code because no DOM traversal commands are issued by the recorder.
- Heavy ChromiumRL page capture on Amazon search was: `saveDOMState` ~867 ms, `getAgentObservation` ~109 ms in T-2.

## T-3 / T-4 implemented triage changes

Implemented in code:

- `enable_page_domains()` now treats `Runtime.enable` as non-fatal with a 5s timeout.
- `DOM.enable` is skipped and logged as not required.
- `Page.enable` is added as non-fatal with a 5s timeout for event delivery.
- ChromiumRL tracing defaults are reduced to touch traces only: layout timings, CLS attribution, and compositor layers default false.
- `--chromiumrl-full-tracing` restores legacy heavy tracing.
- `ChromiumRL.disable` is best-effort on reset and connection close.

## T-5 JS dialog and CDP reader

Implemented in code:

- `CDPConnection.send()` now uses pending futures and a single background WebSocket reader task.
- ID-bearing responses resolve their matching futures.
- Events are logged into `cdp.event_log`.
- `Page.javascriptDialogOpening` is auto-dismissed with `Page.handleJavaScriptDialog`.
- `Page.frameNavigated`, `Target.targetCreated`, `Target.targetDestroyed`, and `Inspector.targetCrashed` are logged.
- `Inspector.targetCrashed` marks the connection as crashed and fails pending commands.

Sanity test: `diagnostics/t5_concurrent_send.json` shows two concurrent `Runtime.evaluate` calls both resolved correctly.

Dialog test: `diagnostics/t5_dialog_probe.json` navigated to `data:text/html,<script>alert('x')</script><p>ok</p>` and then successfully evaluated body text `ok`. Event log includes `Page.javascriptDialogOpening` and `javascript_dialog_dismissed`.

## T-6 Target pinning

Implemented in code:

- `CDPConnection.pinned_target_id` added.
- `refresh_page_session()` prefers the pinned target.
- If the pinned target is gone, it falls back to normal target selection and logs `target_switched`.
- `open_fresh_tab()` pins the fresh task tab.
- `reattach_to_target()` refreshes the pin.
- The forced post-action `cdp.reconnect()` was removed because it was fighting the pinned target/session and contributed to after-capture failures.

## T-7 Coordinate space verdict

Original required probe output: `diagnostics/t7_coord_probe_output.json`.

The unchanged probe produced mostly sticky/sidebar matches with deltas around `-112`, so by itself it was ambiguous. Supplemental probe `diagnostics/t7_coord_probe_plus.json` recorded actual `scrollY` and normal page-content matches.

**VERDICT: viewport-relative.**

Evidence from supplemental probe:

- `scrollY_before`: 0
- `scrollY_after`: 1000
- normal content samples moved by `delta: -1000.0`
- sticky/sidebar samples moved by a smaller amount because sticky layout changes their viewport position

Code comment added at `element_center()` recording this 2026-08-06 verdict: do not subtract `scrollY`/`scrollX` from ChromiumRL bounds.

Raw unchanged probe:

```text
Runtime.enable ...
Runtime.enable ok in 2.7ms
Page.enable ...
Page.enable ok in 1.7ms
{
  "scrolled_by": 1000,
  "samples": [
    {
      "id": "BUTTON|aria:Hide Contents|t:hide",
      "y_before": 136.84375,
      "y_after": 25,
      "delta": -111.84375
    },
    {
      "id": "BUTTON|t:Toggle Browser market subsecti",
      "y_before": 285.328125,
      "y_after": 173.484375,
      "delta": -111.84375
    },
    {
      "id": "BUTTON|t:Toggle Security subsection",
      "y_before": 357.328125,
      "y_after": 245.484375,
      "delta": -111.84375
    },
    {
      "id": "BUTTON|aria:Hide Appearance|t:hide",
      "y_before": 136.84375,
      "y_after": 25,
      "delta": -111.84375
    },
    {
      "id": "A|t:(Top)",
      "y_before": 172.328125,
      "y_after": 60.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:1\n\t\t\t\tFunction",
      "y_before": 200.328125,
      "y_after": 88.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:2\n\t\t\t\tHistory",
      "y_before": 228.328125,
      "y_after": 116.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:3\n\t\t\t\tFeatures",
      "y_before": 256.328125,
      "y_after": 144.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:4\n\t\t\t\tBrowser market",
      "y_before": 284.328125,
      "y_after": 172.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:4.1\n\t\t\t\t\tMarket share by type ",
      "y_before": 312.328125,
      "y_after": 200.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:5\n\t\t\t\tSecurity",
      "y_before": 356.328125,
      "y_after": 244.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:5.1\n\t\t\t\t\tPrivacy",
      "y_before": 384.328125,
      "y_after": 272.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:6\n\t\t\t\tSee also",
      "y_before": 412.328125,
      "y_after": 300.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:7\n\t\t\t\tReferences",
      "y_before": 440.328125,
      "y_after": 328.484375,
      "delta": -111.84375
    },
    {
      "id": "A|t:8\n\t\t\t\tExternal links",
      "y_before": 468.328125,
      "y_after": 356.484375,
      "delta": -111.84375
    }
  ]
}

```

Supplemental probe:

```text
Runtime.enable ...
Runtime.enable ok in 43.1ms
Page.enable ...
Page.enable ok in 2.9ms
{
  "scrollY_before": 0,
  "scrollY_after": 1000,
  "actual_delta": 1000,
  "match_count": 25,
  "samples": [
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 136.84375,
      "y_after": 25,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 285.328125,
      "y_after": 173.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 357.328125,
      "y_after": 245.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 136.84375,
      "y_after": 25,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 172.328125,
      "y_after": 60.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 200.328125,
      "y_after": 88.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 228.328125,
      "y_after": 116.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 256.328125,
      "y_after": 144.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 284.328125,
      "y_after": 172.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 312.328125,
      "y_after": 200.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 356.328125,
      "y_after": 244.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 384.328125,
      "y_after": 272.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 412.328125,
      "y_after": 300.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 440.328125,
      "y_after": 328.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 468.328125,
      "y_after": 356.484375,
      "delta": -111.84375
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 997.46875,
      "y_after": -2.53125,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1023.46875,
      "y_after": 23.46875,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1023.46875,
      "y_after": 23.46875,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1023.46875,
      "y_after": 23.46875,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1097.140625,
      "y_after": 97.140625,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1097.140625,
      "y_after": 97.140625,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1143.46875,
      "y_after": 143.46875,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1139.140625,
      "y_after": 139.140625,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1139.140625,
      "y_after": 139.140625,
      "delta": -1000.0
    },
    {
      "id": "html.client-js > body.skin--responsive > div.mw-page-container > div.mw-page-con",
      "y_before": 1169.46875,
      "y_after": 169.46875,
      "delta": -1000.0
    }
  ]
}

```

## T-8 Wrapper passthrough and baseline

Wrapper change implemented:

- New form supported: `./scripts/run-agent-browser.sh --task-id <id> --task <prompt> [extra args...]`
- Old positional form remains as deprecated fallback.
- Extra args pass through to `desktop_agent.py`.

Baseline command attempted:

```bash
/usr/bin/time -v ./scripts/run-agent-browser.sh \
  --task-id diag-baseline-t8-004 \
  --task 'Search for wireless mouse and open the first product page' \
  --yes --max-steps 12
```

Result: **failed at step 2**, not a successful baseline.

Observed sequence:

1. Step 1 navigated to `https://www.amazon.com/` and recorded successfully.
2. Step 2 clicked Amazon's `Continue shopping` interstitial.
3. After that click, `Page.enable` and `ChromiumRL.enable` began timing out.
4. A direct post-failure probe against the same Amazon target showed:
   - `ChromiumRL.saveDOMState` timed out after 20s
   - `ChromiumRL.getAgentObservation` timed out after 15s

This means the exact A6/T-8 baseline is blocked by the Amazon page target becoming unresponsive to ChromiumRL after the interstitial click. It is not fixed by raising timeouts.

T-8 failed-run bytes: `455110` bytes under `tasks/diag-baseline-t8-004`.

File counts from failed run:

```json
{
  "action.json": 2,
  "actions.json": 1,
  "agent_browser_decisions.jsonl": 1,
  "chromiumrl_agent_observation.json": 3,
  "chromiumrl_dom.json": 3,
  "chromiumrl_signals.json": 1,
  "chromiumrl_visual_hash.json": 3,
  "dom_diff.json": 1,
  "dom_diff_summary.json": 1,
  "interaction_capture.json": 1,
  "manifest.json": 1,
  "page_state.json": 3,
  "request_000001_step_001.json": 1,
  "request_000002_step_002.json": 1,
  "screenshot.png": 3,
  "state_index.json": 3,
  "step.json": 2,
  "trajectory.jsonl": 1,
  "verifier_action.json": 1
}
```

Baseline log excerpt:

```text
Connecting to desktop Wootz CDP at http://127.0.0.1:49325 ...
Runtime.enable ...
Runtime.enable ok in 42.3ms
Page.enable ...
Page.enable ok in 1.4ms
Runtime.enable ...
Runtime.enable ok in 41.8ms
Page.enable ...
Page.enable ok in 0.8ms
Started non-resume task in a fresh tab: about:blank
Started non-resume task in an isolated browser context.
ChromiumRL.getAgentObservation ...
ChromiumRL.getAgentObservation ok in 0.4ms

==============================================================================
PROPOSED STEP 001 (model)
{
  "action": "navigate",
  "url": "https://www.amazon.com/",
  "thoughts": "The page is blank, so I will start by opening Amazon, a popular site for searching and buying wireless mice."
}
==============================================================================
Runtime.enable ...
Runtime.enable ok in 40.9ms
Page.enable ...
Page.enable ok in 1.3ms
before: ChromiumRL.saveDOMState ...
before: ChromiumRL.saveDOMState ok in 0.9ms
before: ChromiumRL.getVisualHash ...
before: ChromiumRL.getVisualHash ok in 0.6ms
before: ChromiumRL.getAgentObservation ...
before: ChromiumRL.getAgentObservation ok in 0.6ms
before: Runtime.evaluate ...
before: Runtime.evaluate ok in 1.7ms
Runtime.enable ...
Runtime.enable ok in 1.2ms
Page.enable ...
Page.enable ok in 1.0ms
Runtime.enable ...
Runtime.enable ok in 0.8ms
Page.enable ...
Page.enable ok in 0.8ms
after: ChromiumRL.saveDOMState ...
after: ChromiumRL.saveDOMState ok in 4.0ms
after: ChromiumRL.getVisualHash ...
after: ChromiumRL.getVisualHash ok in 1.1ms
after: ChromiumRL.getAgentObservation ...
after: ChromiumRL.getAgentObservation ok in 1.7ms
after: Runtime.evaluate ...
after: Runtime.evaluate ok in 1.7ms
ChromiumRL.compareDOMState ...
ChromiumRL.compareDOMState ok in 12.4ms
Page.getFrameTree ...
Page.getFrameTree ok in 1.4ms
signals: ChromiumRL.getTouchTraces ...
signals: ChromiumRL.getTouchTraces ok in 0.8ms
signals: ChromiumRL.getLayoutTimings ...
signals: ChromiumRL.getLayoutTimings ok in 0.4ms
signals: ChromiumRL.getCLSAttribution ...
signals: ChromiumRL.getCLSAttribution ok in 0.3ms
signals: ChromiumRL.getCompositorLayers ...
signals: ChromiumRL.getCompositorLayers ok in 0.4ms
signals: ChromiumRL.getVisualHash ...
signals: ChromiumRL.getVisualHash ok in 0.2ms
ChromiumRL.captureInteraction ...
ChromiumRL.captureInteraction ok in 0.4ms
Recorded automated step 001 in /data/aayush/task-recorder/tasks/diag-baseline-t8-004/step_001
ChromiumRL.getAgentObservation ...
ChromiumRL.getAgentObservation ok in 0.9ms

==============================================================================
PROPOSED STEP 002 (model)
{
  "action": "click",
  "ref": "e1",
  "thoughts": "There is a 'Continue shopping' button, likely part of a consent or interstitial overlay. I will click it to proceed to the main Amazon page and access the search bar."
}
==============================================================================
Runtime.enable ...
Runtime.enable ok in 1.5ms
Page.enable ...
Page.enable ok in 1.5ms
before: ChromiumRL.saveDOMState ...
before: ChromiumRL.saveDOMState ok in 6.1ms
before: ChromiumRL.getVisualHash ...
before: ChromiumRL.getVisualHash ok in 1.1ms
before: ChromiumRL.getAgentObservation ...
before: ChromiumRL.getAgentObservation ok in 2.9ms
before: Runtime.evaluate ...
before: Runtime.evaluate ok in 2.2ms
Runtime.enable ...
Runtime.enable ok in 27.5ms
Page.enable ...
Page.enable ok in 75.0ms
Runtime.enable ...
Runtime.enable ok in 79.0ms
Page.enable ...
Page.enable failed after 5005.7ms: CDP command Page.enable timed out after 5.0s
ERROR: CDP command ChromiumRL.enable timed out after 10.0s
Command exited with non-zero status 1
	Command being timed: "./scripts/run-agent-browser.sh --task-id diag-baseline-t8-004 --task Search for wireless mouse and open the first product page --yes --max-steps 12"
	User time (seconds): 0.42
	System time (seconds): 0.06
	Percent of CPU this job got: 2%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 0:24.08
	Average shared text size (kbytes): 0
	Average unshared data size (kbytes): 0
	Average stack size (kbytes): 0
	Average total size (kbytes): 0
	Maximum resident set size (kbytes): 40704
	Average resident set size (kbytes): 0
	Major (requiring I/O) page faults: 0
	Minor (reclaiming a frame) page faults: 7736
	Voluntary context switches: 449
	Involuntary context switches: 2
	Swaps: 0
	File system inputs: 0
	File system outputs: 1168
	Socket messages sent: 0
	Socket messages received: 0
	Signals delivered: 0
	Page size (bytes): 4096
	Exit status: 1

```

## Final doctor evidence after changes

| page | ok | target | saveDOMState ms | compareDOMState ms | getAgentObservation ms |
|---|---:|---|---:|---:|---:|
| blank | True | about:blank | 1.037 | 1.612 | 1.738 |
| heavy | True | https://www.amazon.com/s?k=wireless+mouse | 785.608 | 951.809 | 61.21 |

Files:

- `diagnostics/t_final_doctor_blank.json`
- `diagnostics/t_final_doctor_heavy.json`

## Blockers

1. **T-8 exact baseline is blocked.** Amazon's post-interstitial page target stops answering ChromiumRL after clicking `Continue shopping`. The browser target remains listed in `/json/list`, but ChromiumRL capture calls do not return.
2. Because T-8 did not complete at least 8 steps, Phase T exit criteria are not satisfied.
3. I did not start Phase B.

## Disagreements / corrections from real data

1. The original Phase A `Runtime.enable` hang was stale browser/session state. After clean restart, `Runtime.enable` is fast. The fix is still correct: domain enabling should be non-fatal because a stale target can otherwise kill the whole run.
2. The exact A6 baseline using an unconstrained task prompt is unreliable because the model chooses Amazon, and Amazon's interstitial path wedges ChromiumRL in this browser build. A baseline should use a stable site or explicitly exclude Amazon if the goal is recorder performance measurement rather than anti-bot behavior measurement.
3. T-8 requiring a baseline before B1-a conflicted with the missing `agent-browser` binary. I made the minimal raw-CDP execution change during Phase T so T-8 could run at all. No artifact-reduction or prompt Phase B work was started.
