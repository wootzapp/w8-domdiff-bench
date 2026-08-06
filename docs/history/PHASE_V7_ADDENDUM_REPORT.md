# Phase V7 Addendum A Report

## Summary

Implemented Addendum A on top of v6. New runs now restore required page-state files, write `agent_browser_final.json`, always capture final raw DOM by default, and can produce a verifier bundle.

Validated on task: `task-v7-books-check-003`.

## A1 page_state.json restored

New step files:

- `step_NNN/page_state_before.json`
- `step_NNN/page_state_after.json`

New final file:

- `final_state/page_state.json`

These are uncompressed and greppable.

## A2 agent_browser_final.json restored

`tasks/task-v7-books-check-003/agent_browser_final.json` contains:

- `task_id`
- `task_prompt`
- `status`
- `final_answer`
- `terminated_at`
- terminate `action`
- `completed_steps`
- `termination_reason`
- `grounding_check`
- `verifier_bundle` when `--verifier-bundle` is used

Validation result:

```json
{
  "task_prompt_present": true,
  "termination_reason": "model_terminate",
  "grounding_ok": true,
  "verifier_bundle_bytes": 377631,
  "verifier_bundle_files": 39
}
```

## A3 final raw DOM

Default `--final-state-dom both` now writes:

- `final_state/dom_full.json.gz` — raw `ChromiumRL.saveDOMState`
- `final_state/dom_state.json.gz` — slim projection

Validation on `task-v7-books-check-003`:

```json
{
  "raw_bytes": 326535,
  "raw_gzip_bytes": 15214,
  "slim_gzip_bytes": 7103,
  "nodes": 283,
  "max_keyStyles_props": 19,
  "comment_nodes": 17
}
```

This confirms `dom_full.json.gz` is raw rather than projected: it contains comment nodes and full 19-property `keyStyles` objects.

## A3 size table

| page | nodes | raw JSON | raw gzip | slim gzip | max keyStyles props | comment nodes |
|---|---:|---:|---:|---:|---:|---:|
| bench-books | 283 | 318.9 KB | 14.9 KB | 7.0 KB | 19 | 17 |
| bench-wiki | 6230 | 9476.4 KB | 331.3 KB | 185.3 KB | 19 | 7 |

Recommendation: keep `--final-state-dom both` as the default. The largest measured raw-gzipped final DOM was Wikipedia at 331.3 KB, well below the ~2 MB warning threshold.

## A4 updated layout validated

`python3 scripts/verify-example.py tasks/task-v7-books-check-003` returned:

```text
OK: tasks/task-v7-books-check-003 has v7 verifier artifacts (3 steps)
```

Generated required files include:

- `manifest.json`
- `log.jsonl`
- `agent_browser_final.json`
- `VERIFIER.md`
- per-step `action.json`
- per-step `page_state_before.json`
- per-step `page_state_after.json`
- per-step `dom_diff.json`
- final `page_state.json`
- final `dom_full.json.gz`
- final `dom_state.json.gz`

## A5 README / MIGRATION updates

Updated:

- `README.md` file-tier table
- `MIGRATION.md` old-to-new mapping
- explicit distinction between raw final DOM, slim final DOM, and capped observation
- note that final-state DOM diff is intentionally absent; use the last step's `dom_diff.json`

## A6 acceptance additions

| # | Result | Evidence |
|---|---|---|
| 1 | PASS | `page_state_before/after.json` present on every step and `final_state/page_state.json` present in `task-v7-books-check-003`. |
| 2 | PASS | `agent_browser_final.json` present with `termination_reason: model_terminate` and `grounding_check.ok: true`. |
| 3 | PASS | `final_state/dom_full.json.gz` exists by default and contains comment nodes plus 19-property `keyStyles`. |
| 4 | PASS | Size table above for bench-books and bench-wiki; default recommendation is `both`. |
| 5 | PASS | `--verifier-bundle` produced `task-v7-books-check-003_verifier_bundle.zip`, 377631 bytes, 39 files. |

## Notes

- The repository did not have an existing `--verifier-bundle` flag or `scripts/verify-example.py`. I added both.
- The previous v6 task `task-v6-books-mystery-001` retains the old v6 layout. New tasks use the v7 layout.
