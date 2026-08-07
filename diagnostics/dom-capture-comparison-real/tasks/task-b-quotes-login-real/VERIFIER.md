# Verifier artifact guide

Required files:

- `manifest.json` — run metadata and task id.
- `log.jsonl` — complete event stream and model/action trace.
- `agent_browser_final.json` — final claim/status to verify.
- `step_NNN/action.json` — normalized action and verifier action fields.
- `step_NNN/page_state.json` — after-step URL/title/viewport state.
- `step_NNN/dom_diff.json` — primary verifier evidence.
- `step_NNN/dom_diff.txt` — human-readable rendering of the same diff.

Default step files:

- `after.jpg` — after-step screenshot.
- `before.jpg` — present only with `--screenshot-mode both`.
- `dom_before.json.gz` and `dom_after.json.gz` — slim DOM projections used to produce the diff.

Optional agent-debug files, present only with `--keep-observations`:

- `observation_before.json.gz`
- `observation_after.json.gz`
- `observation_diff.json`

Final state:

- `final_state/dom_full.json.gz` — raw final ChromiumRL DOM snapshot when enabled.
- `final_state/dom_state.json.gz` — slim final DOM projection.
- `final_state/page_state.json` — final URL/title/viewport state.
- `final_state/observation.json` — final capped interactive observation; this is not a DOM snapshot.

Use the last step's `dom_diff.json` for the final transition. There is intentionally no `final_state/dom_diff.json`.
