# task-recorder v6 artifact layout

V5 restored per-step DOM capture because DOM-diff verifier evidence is the product. V6 hardens that artifact for verifier use: cross-document navigations are represented as document replacement plus text delta, every diff declares frame coverage, form property enrichment has explicit provenance, and scroll-only `active`/`current` class churn is retained only as flagged artifact data.

```text
tasks/<task-id>/
├── manifest.json
├── log.jsonl
├── agent_browser_final.json
├── VERIFIER.md
├── step_001/
│   ├── action.json
│   ├── page_state_before.json
│   ├── page_state_after.json
│   ├── dom_diff.json
│   ├── evidence/
│   │   ├── dom_state_before.json.gz
│   │   ├── dom_state_after.json.gz
│   │   └── after.jpg
│   └── agent/
│       ├── observation_before.json.gz
│       ├── observation_after.json.gz
│       └── observation_diff.json
└── final_state/
    ├── dom_full.json.gz
    ├── dom_state.json.gz
    ├── page_state.json
    ├── observation.json
    └── screenshot.jpg
```

Old-to-new mapping:

| Old artifact | New location | Note |
|---|---|---|
| `trajectory.jsonl` | `log.jsonl` | Use `scripts/replay-log.py tasks/<task-id>` for a readable trajectory. |
| `agent_browser_decisions.jsonl` | `log.jsonl` events `model_request` / `model_response` | Model inputs are consolidated into the log. |
| `model_inputs/request_*.json` | `log.jsonl` event `model_request` | Snapshot text is truncated only in the log copy at 8000 chars. |
| `step.json` + `verifier_action.json` | `step_NNN/action.json` | Step metadata and verifier action are merged. |
| root final claim in logs only | `agent_browser_final.json` | Final answer/status/termination reason is restored as a required first-class verifier file. |
| old page state inside nested capture folders | `step_NNN/page_state_before.json`, `page_state_after.json`, `final_state/page_state.json` | Tiny URL/title/viewport state files are restored and left uncompressed. |
| final slim DOM `dom.json.gz` | `final_state/dom_state.json.gz` | Slim projection only; not interchangeable with raw DOM. |
| final raw DOM opt-in only | `final_state/dom_full.json.gz` | Raw final `saveDOMState`, gzipped, written by default with `--final-state-dom both`. |
| `dom_diff_summary.json` | `step_NNN/observation_diff.json` | Important: the old file was based on capped `getAgentObservation` interactive elements, not the full DOM. Conclusions about non-interactive text, totals, confirmations, or status changes were not supportable. |
| v4 `step_NNN/diff.json` | `step_NNN/observation_diff.json` | Same observation-based progress signal, renamed for provenance clarity. |
| per-step raw `chromiumrl_dom.json` | `step_NNN/evidence/dom_state_before.json.gz` / `dom_state_after.json.gz` | Default per-step evidence is a slim semantic projection. Use `--dom-capture full` for per-step raw audit copies. |
| `ChromiumRL.compareDOMState` output | folded into `step_NNN/dom_diff.json.source.compareDOMState` | The compact local diff uses saveDOMState projections; browser compare timing/summary is kept as provenance. |

Verifier guidance: consume `step_NNN/dom_diff.json`. Use `observation_diff.json` only as supporting progress/debug evidence.

V6 verifier notes:

- `dom_diff.json` is the verifier artifact. It is derived from real `ChromiumRL.saveDOMState` projections, not from the capped interactive observation.
- Cross-document steps set `cross_document: true` and do not emit node-level `changed` entries, because structural keys can collide across pages. Use `document_added`, `document_removed`, `text_delta`, and `interactive_added`.
- Every diff has `frames`. Current browser DOM capture is main-frame scoped; same-origin iframe nodes are added through JS fallback projection and marked `source: js_iframe`; cross-origin frames are listed but not traversed.
- Every diff has `enrichment`. Form `value`, `checked`, and `selected` can come from `Runtime.evaluate`; enriched attributes are marked with `{"v": ..., "src": "prop"}`. If enrichment fails, verifier confidence for form changes should be downgraded.
- `active` and `current` class changes are preserved. On pure scroll steps they are moved to `flagged_changes` with `likely_scroll_artifact: true`; `stats.changed_total` counts only unflagged semantic changes.
- `--validate-diff` records a count-level comparison against browser `ChromiumRL.compareDOMState` operations in `dom_diff.json.compare_validation`.

V7 note: `final_state/observation.json` is not a DOM snapshot under any setting. It is capped interactive observation data. Final-state DOM diff is intentionally absent; use the last step's `dom_diff.json`.

V8 note: step folders are flat again. `page_state_before.json` / `page_state_after.json` were replaced by a single after-state `page_state.json`. Per-step observations moved behind `--keep-observations`; when enabled they are written at the step root. `evidence/` and `agent/` subdirectories are no longer created.
