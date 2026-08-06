# task-recorder v3 artifact layout

New runs use a reduced artifact layout:

```
tasks/<task-id>/
├── manifest.json
├── log.jsonl
├── step_001/
│   ├── action.json
│   ├── observation_before.json.gz
│   ├── observation_after.json.gz
│   ├── diff.json
│   ├── before.png
│   └── after.png
└── final_state/
    ├── dom.json.gz
    ├── observation.json
    └── screenshot.png
```

Old-to-new mapping:

| Old artifact | New location | Note |
|---|---|---|
| `trajectory.jsonl` | `log.jsonl` | Use `scripts/replay-log.py tasks/<task-id>` for a readable trajectory. |
| `agent_browser_decisions.jsonl` | `log.jsonl` events `model_request` / `model_response` | Model inputs are consolidated into the log. |
| `model_inputs/request_*.json` | `log.jsonl` event `model_request` | Snapshot text is truncated only in the log copy at 8000 chars. |
| `step.json` + `verifier_action.json` | `step_NNN/action.json` | Human-readable step metadata and verifier action are merged. |
| `dom_diff_summary.json` | `step_NNN/diff.json` | Computed by the recorder from before/after observations. |
| per-step `before/after/chromiumrl_dom.json` | removed | Full DOM is kept only at `final_state/dom.json.gz`. |
| `chromiumrl_signals.json` | removed | Only `getTouchTraces` is retained, and only when the action has coordinates. |
| `interaction_capture.json`, `all_targets/`, visual hash files | removed | Not needed by the reduced verifier artifact set. |

The model-facing observation now includes visible off-fold elements grouped as `above fold`, `in viewport`, and `below fold`. Off-fold refs remain actionable; the runner scrolls them into view before clicking or filling.
