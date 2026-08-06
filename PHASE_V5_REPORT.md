# Phase V5 Report — DOM diff is the product

## Corrections carried forward

- v1-v4 removal of per-step DOM capture was wrong for this repo's actual product. Verifier evidence must be based on a real DOM diff, not only the ChromiumRL agent observation.
- The old `dom_diff_summary.json`/v4 `diff.json` was observation-derived. It never read `chromiumrl_dom.json`, so it could miss non-interactive text, totals, confirmations, and status changes.
- v4's navigation hypothesis was wrong. The Amazon failure is better explained by renderer occlusion/background throttling; the v5 A/B reproduced that distinction.

## Implemented changes

### Occlusion/background throttling

Added Chrome flags in `scripts/container-start.sh`:

```text
--disable-backgrounding-occluded-windows
--disable-renderer-backgrounding
--disable-background-timer-throttling
--disable-features=CalculateNativeWinOcclusion
--force-device-scale-factor=1
```

The runner now also calls `Target.activateTarget` and `Page.bringToFront` best-effort before captures and actions, logging `activate_failed` on failure.

Added `--fresh-tab-mode {new_context,new_tab,reuse}`, default `new_tab`. `new_context` remains available for stronger isolation, but it can create separate OS windows and reintroduce window-ordering/occlusion risk.

### DOM diff pipeline

Per step, the runner now writes:

```text
step_NNN/dom_before.json.gz        slim saveDOMState projection
step_NNN/dom_after.json.gz         slim saveDOMState projection
step_NNN/dom_diff.json             compact semantic DOM diff; verifier artifact
step_NNN/observation_diff.json     renamed observation-based progress diff
```

`--dom-capture slim` is default. `--dom-capture full` also writes raw audit DOM gzip files.

`dom_diff.json` is computed from slim projections of `ChromiumRL.saveDOMState`, with `ChromiumRL.compareDOMState` timing/summary stored as source metadata. The compact diff:

- keeps semantic text, selected semantic attributes, visibility, viewport flags, and selected state-ish CSS/classes;
- enriches form controls with live `value`, `checked`, and `selected` properties;
- excludes geometry and scroll-position noise;
- collapses whole added/removed subtrees into root entries with descendant counts, visible text, and up to 20 interactive descendants;
- reports true totals and emitted counts with `truncated`.

## Amazon occlusion A/B (§1.4)

| run | flags | completed steps | renderer_wedged events | outcome |
|---|---:|---:|---:|---|
| bench-hostile-v5-applied | enabled | 10 | 0 | failure / model overlay failure |
| bench-hostile-v5-reverted | reverted | 5 | 6 | failure / renderer_unresponsive |

Verdict: occlusion/background throttling accounts for the renderer wedge in this bounded test. With flags enabled, Amazon reached 10 recorded steps and failed cleanly because of a persistent Amazon overlay. With flags reverted, the same task hit `renderer_unresponsive` at step 5 with repeated `Runtime.evaluate` timeouts.

Failure-time screenshot: unavailable for the reverted wedge. The renderer was unresponsive, and final screenshot capture also timed out; this is recorded in `diagnostics/v5/amazon_reverted.log` and the task log.

## DOM key population (§2.2)

Measured on Books to Scrape before opening the first product page:

```json
{
  "total_nodes": 704,
  "fields": {
    "stablePath": {
      "count": 699,
      "rate": 0.9929
    },
    "cssSelector": {
      "count": 699,
      "rate": 0.9929
    },
    "xpath": {
      "count": 699,
      "rate": 0.9929
    }
  }
}
```

`stablePath`, `cssSelector`, and `xpath` are populated for 99.29% of nodes on this real page. The fallback structural path remains in place for roots/edge nodes where these are empty.

## Size table (§2.7)

| id | raw after saveDOMState JSON bytes | slim after gzip bytes | dom_diff.json bytes | stats |
|---|---:|---:|---:|---|
| bench-books-open-first | 142485 | 3613 | 15550 | `{"added_total":84,"added_roots_total":4,"added_emitted":4,"removed_total":650,"removed_roots_total":1,"removed_emitted":1,"changed_total":10,"changed_emitted":10,"truncated":false}` |
| bench-wiki-navigate | 9865248 | 192562 | 8114 | `{"added_total":6200,"added_roots_total":2,"added_emitted":2,"removed_total":3,"removed_roots_total":1,"removed_emitted":1,"changed_total":0,"changed_emitted":0,"truncated":false}` |
| bench-wiki-scroll | 9873188 | 193319 | 1212 | `{"added_total":0,"added_roots_total":0,"added_emitted":0,"removed_total":0,"removed_roots_total":0,"removed_emitted":0,"changed_total":0,"changed_emitted":0,"truncated":false}` |


Books steps are under the ~50 KB target. Wikipedia navigation is also under 50 KB because subtree collapse reduces thousands of inserted nodes to collapse roots. Wikipedia slim DOM gzip remains large because it is the full projected page state, but the verifier-facing `dom_diff.json` is compact.

## Diff-quality benchmarks (§4.1)

Automated assertions were run by `scripts/run-diff-benchmarks.py`; final output is in `diagnostics/v5/diff_benchmarks_v3/`.

| id | pass | dom_diff bytes | stats | assertion |
|---|---:|---:|---|---|
| diff-checkbox | True | 2061 | `{"added_total":0,"added_roots_total":0,"added_emitted":0,"removed_total":0,"removed_roots_total":0,"removed_emitted":0,"changed_total":1,"changed_emitted":1,"truncated":false}` | ok |
| diff-modal | True | 2257 | `{"added_total":0,"added_roots_total":0,"added_emitted":0,"removed_total":5,"removed_roots_total":1,"removed_emitted":1,"changed_total":0,"changed_emitted":0,"truncated":false}` | ok |
| diff-text | True | 15550 | `{"added_total":84,"added_roots_total":4,"added_emitted":4,"removed_total":650,"removed_roots_total":1,"removed_emitted":1,"changed_total":10,"changed_emitted":10,"truncated":false}` | ok |
| diff-form | True | 12393 | `{"added_total":261,"added_roots_total":2,"added_emitted":2,"removed_total":22,"removed_roots_total":2,"removed_emitted":2,"changed_total":0,"changed_emitted":0,"truncated":false}` | fill=ok; submit=ok |
| diff-scroll | True | 1211 | `{"added_total":0,"added_roots_total":0,"added_emitted":0,"removed_total":0,"removed_roots_total":0,"removed_emitted":0,"changed_total":0,"changed_emitted":0,"truncated":false}` | ok |


Notes:

- `diff-modal` uses a controlled `data:` modal because public cookie banners vary by region/session. It validates the actual subtree-collapse behavior required by v5.
- `diff-checkbox` uses a controlled checkbox that mirrors its property into the `checked` attribute; this validates attribute-change capture.
- `diff-form` uses Quotes to Scrape login and validates live form value enrichment plus post-submit result.
- `diff-scroll` passes with `added_total: 0` and `changed_total: 0`.

Complete judge artifacts requested by v5:

- `diagnostics/v5/diff_benchmarks_v3/diff-modal/step_001/dom_diff.json`
- `diagnostics/v5/diff_benchmarks_v3/diff-form/step_001/dom_diff.json`
- `diagnostics/v5/diff_benchmarks_v3/diff-form/step_003/dom_diff.json`

## ChromiumRL source findings (§3)

### 3.1 Element cap

Source: `/data/Aayush/chromium/src/third_party/blink/renderer/core/inspector/inspector_chromiumrl_agent.cc:3014-3016`.

`getAgentObservation` defaults `max_elements` to 100, then uses it as `interactive_limit` unless `maxInteractiveElements` is supplied. The protocol exposes `maxElements`, `maxInteractiveElements`, `maxContentBlocks`, and related parameters in `ChromiumRL.pdl:110-119`. This is configurable, not hard-coded only. The runner now exposes `--observation-max-elements` defaulting to 250 and sends both `maxElements` and `maxInteractiveElements`.

### 3.2 Frame scope

`saveDOMState` and `getAgentObservation` both start from `inspected_frames_->Root()->GetDocument()` and traverse from that document/root (`inspector_chromiumrl_agent.cc:1406-1425` and `2959-3020`). No child-frame traversal is visible in these methods. Conclusion: ChromiumRL DOM/observation traversal is root/main-frame scoped. The JS fallback iframe traversal remains load-bearing for same-origin iframes; cross-origin iframes remain inaccessible from page JS.

### 3.3 Shadow DOM

`captureStateSnapshot` has a comment at `inspector_chromiumrl_agent.cc:905-906`: "Skip internal nodes (shadow roots etc unless needed)" and uses standard traversal. Hit testing calls `SetToShadowHostIfInUAShadowRoot` at line 2568. I did not find explicit piercing of closed shadow roots in `saveDOMState`/`getAgentObservation`. Treat closed shadow DOM as not guaranteed to be represented; open shadow handling depends on Blink traversal behavior and should be tested per site.

### 3.4 compareDOMState semantics

Protocol: `ChromiumRL.pdl:99-106` returns `DOMDiffResult` with arrays of `insertions`, `deletions`, `moves`, `attributeChanges`, `textChanges`, `layoutChanges`, `styleChanges`, and `typeChanges` (`ChromiumRL.pdl:450+`). Source at `inspector_chromiumrl_agent.cc:1610-1665` collects reference nodes and live nodes, then performs fingerprint/content/fuzzy matching and generates operation arrays. It does not expose max-entry/filter parameters except optional `deltaNodes`, so local semantic compaction is still necessary.

### 3.5 GetAgentForFrame returned null

`GetAgentForFrame` returns `nullptr` if the frame is missing or not in the agent map (`inspector_chromiumrl_agent.cc:93-99`). `DidCommitLoadForLocalFrame` re-registers only when `frame == inspected_frames_->Root()` (`108-111`). I did not find the exact log string `GetAgentForFrame returned null` in the inspected source; the null itself is returned synchronously by helper code, not inherently a dropped DevTools response in the snippets inspected.

### 3.6 stablePath population

`BuildRichNode` sets `stablePath` and `cssSelector` from `BuildSelectorPath(node)` and `xpath` from `BuildXPath(node)` at `inspector_chromiumrl_agent.cc:1337-1343`. Empty values occur on a small set of root/internal nodes; measured real-page population was 99.29% for all three fields on Books to Scrape.

## Acceptance criteria

| # | Result | Evidence |
|---|---|---|
| 1 | PASS | `diff-scroll` stats show `added_total: 0`, `changed_total: 0`. |
| 2 | PASS | `diff-checkbox`, `diff-text`, `diff-modal`, `diff-form` all passed automated assertions in `diff_benchmark_summary.json`. |
| 3 | PASS for Books; reported for Wiki | Books diff 15,550 bytes. Wiki navigate diff 8,114 bytes; wiki scroll diff 1,212 bytes. |
| 4 | PASS | Every `dom_diff.json` includes `stats` with true totals, emitted counts, and `truncated`. |
| 5 | PASS | `diff-modal` removed 5 nodes but emitted 1 removed collapse root. |
| 6 | PASS | Amazon A/B verdict above. |
| 7 | PASS | §3.1 and §3.2 answered from source with file/line references. |
| 8 | PASS | New output uses `observation_diff.json`; `dom_diff_summary.json` is no longer produced by current code paths. Existing old tasks may still contain old files. |

## Disagreements / caveats

- The v5 request said `diff-checkbox` on Quotes login, but that page has no checkbox. I used a controlled checkbox page for that specific assertion and kept Quotes for the form benchmark.
- Form `value` and checkbox `checked` are live DOM properties that may not appear as HTML attributes in `saveDOMState`. I added generic form-control state enrichment via `Runtime.evaluate`; this is still real live DOM state, but it is not solely from `saveDOMState`.
- `active/current` CSS class tokens were removed from the semantic class whitelist because Wikipedia scroll-spy turns pure scroll into false semantic changes. `star/rating/selected/checked/open/error/...` remain preserved.
