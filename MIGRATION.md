# task-recorder v5 artifact layout

V5 restores per-step DOM capture because DOM-diff verifier evidence is the product. The v4 reduced layout treated DOM capture as overhead; that was incorrect for verifier work.

```text
tasks/<task-id>/
├── manifest.json
├── log.jsonl
├── step_001/
│   ├── action.json
│   ├── observation_before.json.gz
│   ├── observation_after.json.gz
│   ├── dom_before.json.gz
│   ├── dom_after.json.gz
│   ├── dom_diff.json
│   ├── observation_diff.json
│   └── after.jpg
└── final_state/
    ├── dom.json.gz
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
| `dom_diff_summary.json` | `step_NNN/observation_diff.json` | Important: the old file was based on `getAgentObservation`, not the full DOM. It was not valid DOM-diff verifier evidence. |
| v4 `step_NNN/diff.json` | `step_NNN/observation_diff.json` | Same observation-based progress signal, renamed for provenance clarity. |
| per-step raw `chromiumrl_dom.json` | `step_NNN/dom_before.json.gz` / `dom_after.json.gz` | Default is a slim semantic projection. Use `--dom-capture full` for raw audit copies. |
| `ChromiumRL.compareDOMState` output | folded into `step_NNN/dom_diff.json.source.compareDOMState` | The compact local diff uses saveDOMState projections; browser compare timing/summary is kept as provenance. |

Verifier guidance: consume `step_NNN/dom_diff.json`. Use `observation_diff.json` only as supporting progress/debug evidence.
