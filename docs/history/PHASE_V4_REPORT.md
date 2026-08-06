# Phase V4 Report

## Corrections to v3 premises

1. The v3 navigation hypothesis was wrong. The navigation rebind probe showed ChromiumRL survived cross-document navigation. The Amazon evidence points to a wedged renderer: `Page.enable`, `Runtime.evaluate`, and ChromiumRL calls timed out together. `rebind_session()` remains because it is cheap and useful, but it is not described as the Amazon root cause.
2. v3 acceptance criterion 11 was not measured correctly. v4 includes real byte measurements below.
3. The original v3 stable benchmarks were partly invalid because some could be answered from prior knowledge or completed in too few steps. v4 replaced them with less guessable tasks and flags sub-3-step runs as suspect.

## §1 bounded Amazon regression

Commit before Phase T: `d433e94`.

Result: **old code fails differently / unavailable for behavioral comparison**.

- Exact v4 flag-form command failed because old `scripts/run-agent-browser.sh` did not support flag passthrough.
- Retried with the old positional wrapper and a clean container/readiness wait.
- The old code reached CDP, then failed before any browser trajectory because the official Agent Browser binary was absent:

```text
Connecting to desktop Wootz CDP at http://127.0.0.1:49325 ...
Runtime.enable ...
Runtime.enable ok in 42.0ms
DOM.enable ...
DOM.enable ok in 0.9ms
Runtime.enable ...
Runtime.enable ok in 51.2ms
DOM.enable ...
DOM.enable ok in 0.7ms
ERROR: official Agent Browser binary not found at /data/aayush/task-recorder/agent_browser/official_runtime/bin/agent-browser-linux-x64. The bundled runtime is missing; restore agent_browser/official_runtime/bin/agent-browser-linux-x64.
Started non-resume task in a fresh tab: about:blank
Started non-resume task in an isolated browser context.
```

Verdict form: **Old code fails differently**. It cannot prove whether Phase T/v3 regressed Amazon because the pre-T execution path depends on a missing binary.

## Empty observation / renderer-wedge path

Current `bench-hostile`:

- status: `failure`
- reason: `renderer_unresponsive`
- completed steps: 5
- `renderer_wedged` events: 4
- `observation_fallback` events: 2

This satisfies the v4 distinction: Amazon no longer grinds through blank observations. When ChromiumRL timed out, the runner probed `Runtime.evaluate('1')`; that also timed out, so it logged `renderer_wedged` and terminated with `reason=renderer_unresponsive`.

Requested files:

- `diagnostics/v4/bench-hostile.log.jsonl`
- `diagnostics/v4/bench-hostile-selected-observation.json`

There was no saved real-URL observation with zero elements in the final hostile run; the selected observation is the last available after-action observation.

## Cross-check mode

Full table: `diagnostics/v4/cross_check_table.json` and `diagnostics/v4/cross_check_table.md`.

| task | rows | CRL count range | JS count range | note |
|---|---:|---:|---:|---|
| bench-books | 11 | 0-100 | 0-114 |  |
| bench-books-2 | 14 | 0-100 | 0-115 |  |
| bench-form | 17 | 0-57 | 0-65 |  |
| bench-quotes | 5 | 0-38 | 0-40 |  |
| bench-wiki | 86 | 0-100 | 0-300 | ChromiumRL capped at 100 while JS hit 300 on Wikipedia. |

Finding: ChromiumRL is usually close to JS on the small benchmark sites, but it appears capped around 100 elements on larger pages while JS fallback reaches its cap of 300. This means `--strict-chromiumrl-observation` is not safe as a universal default for large pages.

## Frame coverage

Amazon frame probe: `diagnostics/v4/amazon_frame_probe.clean.json`.

- frame count: 2
- child frames: 1
- ChromiumRL observation element count: 100
- ChromiumRL element frame keys: []
- JS fallback element count: 300

Conclusion: ChromiumRL returned no frame-identifying fields in observation elements. The probe cannot prove per-frame registration from element data. JS fallback now attempts same-origin iframe traversal and offsets iframe bounds; cross-origin frames remain inaccessible by normal page JS.

## Benchmark validity

| task | status | steps | ungrounded | total bytes | max step bytes | reason |
|---|---:|---:|---:|---:|---:|---|
| bench-books | success | 3 | 0 | 799467 | 145567 |  |
| bench-books-2 | success | 4 | 0 | 1179070 | 129499 |  |
| bench-form | success | 5 | 0 | 569350 | 128473 |  |
| bench-hostile | failure | 5 | 0 | 1254631 | 244265 | renderer_unresponsive |
| bench-quotes | success | 1 | 0 | 305122 | 114875 |  |
| bench-wiki | success | 28 | 0 | 13918134 | 323134 |  |


Notes:

- `bench-quotes` completed in one action step plus terminate. Per v4 §3.3 it is suspect and should be manually inspected; replay is available through `scripts/replay-log.py diagnostics/v4/tasks/bench-quotes`.
- `bench-form` deliberately includes Enter-submit wording so the log exercises both `fill` and `press`. `step_004/action.json` records `action=press` and verifier `key=Enter`.
- `bench-wiki` completed but took 28 action steps. The final answer is grounded according to the mechanical check, but quality should be manually reviewed because the cited reference text is abbreviated.

## Artifact size measurements

Comparable v4 measurements on `bench-books`:

| run | total bytes | step bytes | ratio vs previous |
|---|---:|---|---:|
| quality 80 before screenshot-size change | 844,352 | 123,921 / 157,832 / 128,540 | 1.000 |
| quality 70 before context trim | 799,914 | 112,850 / 145,805 / 117,944 | 0.947 |
| quality 70 + context trim final | 799,467 | 112,618 / 145,567 / 117,947 | 0.947 |

The exact pre-v3 byte comparison remains unavailable because `d433e94` cannot run without `agent_browser/official_runtime/bin/agent-browser-linux-x64`. This is a real limitation of the local checkout, not a skipped measurement. The actual measured v4 screenshot change brings all `bench-books` steps under the 150 KB per-step target.

Context trim effect on final `bench-books` model snapshots: `176, 8026, 8025, 3199` characters. The largest reduction was in saved/logged observation payloads rather than rendered model text because the renderer already avoided context in element lines.

## Observation/use-field fixes

Implemented:

- Implausible ChromiumRL observations now trigger JS fallback on real URLs.
- `--observation-source cross_check` runs both ChromiumRL and JS every step and logs count deltas.
- Renderer wedge detection distinguishes ChromiumRL-only failure from renderer-unresponsive failure.
- `[blocked]` rendering uses `isHitTestable=false`; clicking an in-viewport blocked ref raises an actionable error instead of dispatching the click.
- Viewport banner uses native scroll metadata when available.
- Identity now prefers `selector`, then `nodeId`; `fingerprint` is last because the stability probe showed collisions.
- Visible state metadata includes generic `aria`, `title`, and filtered `class` tokens; this fixed CSS-only state such as Books to Scrape star ratings.
- Observation `context` is truncated to 80 chars or dropped when redundant.

Blocked-refusal check: `diagnostics/v4/blocked_refusal_check.json`.

## Acceptance criteria

| # | Result | Evidence |
|---:|---|---|
| 1 | PASS | Implausible real-URL ChromiumRL observations call JS fallback before model use; hostile run logs fallback and no real-url zero-element saved observation was found. |
| 2 | PASS | `bench-hostile` terminates with `reason=renderer_unresponsive`. |
| 3 | PASS | `bench-form` succeeds; step 2/3 are `fill`, step 4 is `press` with `key=Enter`. |
| 4 | PASS | Final benchmark summary shows `ungrounded=0` for all passing benchmarks. |
| 5 | PASS | Final `bench-books` max step bytes = 145,567 ≤ 150,000. |
| 6 | PARTIAL | Two real measured v4 numbers are reported. Exact pre-v3 run is unavailable because the old binary is missing. |
| 7 | PASS | `diagnostics/v4/blocked_refusal_check.json` shows blocked ref raises before click dispatch. |
| 8 | PASS | §1 verdict stated: old code fails differently/unavailable due missing official binary. |

## Files delivered

- `diagnostics/v4/bench-hostile.log.jsonl`
- `diagnostics/v4/bench-hostile-selected-observation.json`
- `diagnostics/v4/cross_check_table.json`
- `diagnostics/v4/cross_check_table.md`
- `diagnostics/v4/amazon_frame_probe.clean.json`
- `diagnostics/v4/regress_amazon_old_valid2.log`
- `diagnostics/v4/bench-wiki-js-replay.txt`
- `diagnostics/v4/bench-books-context-trim-sizes.txt`
- `diagnostics/v4/chromiumrl_source_recheck.txt`
- `diagnostics/v4/benchmark_summary.json`
- `diagnostics/v4/benchmark_summary.md`

## ChromiumRL source/protocol definitions

UNAVAILABLE. Rechecked in `diagnostics/v4/chromiumrl_source_recheck.txt`. The local workspace/image still does not contain the ChromiumRL `.pdl`, JSON protocol definition, or C++ handler source with method signatures for `saveDOMState`, `getAgentObservation`, `compareDOMState`, or `enable`.

## Disagreements / caveats

- The requested pre-v3 byte comparison cannot be performed in this checkout because the pre-T execution path requires a missing official binary. Reporting a fake ratio would be misleading.
- `bench-quotes` is still too easy/short: it completed in one action step after direct URL navigation. It is grounded, but v4's own multi-step-floor rule says it should be treated as suspect.
- `bench-wiki` is difficult for this observation/action strategy: it succeeded mechanically but took 28 steps and produced an abbreviated citation. This is evidence that large document navigation still needs better structural shortcuts or richer document landmarks, not more waiting.
