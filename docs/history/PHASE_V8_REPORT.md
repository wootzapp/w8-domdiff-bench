# Phase V8 Report

## Summary

Implemented v8 cleanup and hardening:

- Step folders are flat again; no `evidence/` or `agent/` subdirectories.
- Default per-step output has 6 files and 2 gzip files; `--screenshot-mode both` has 7 files.
- Per-step observations are opt-in behind `--keep-observations`.
- Non-resume runs clean stale tabs before starting and close their own task tab on every exit path.
- Added browser health preflight, `scripts/reset-browser.sh`, `scripts/export-verifier-bundle.py`, and a README scripts inventory.
- Phase reports moved to `docs/history/`.

## Step layout validation

`task-v8-layout-both-001/step_001` with `--screenshot-mode both` contains exactly:

```text
action.json
after.jpg
before.jpg
dom_after.json.gz
dom_before.json.gz
dom_diff.json
page_state.json
```

`task-v8-leak-check-005/step_001` with default `after_only` contains exactly:

```text
action.json
after.jpg
dom_after.json.gz
dom_before.json.gz
dom_diff.json
page_state.json
```

Default gzip count per step: `2`.

`--keep-observations` validated on `task-v8-observations-001`; it adds top-level:

```text
observation_after.json.gz
observation_before.json.gz
observation_diff.json
```

## Browser tab leak fix

Implemented:

- health preflight before connecting, stored in `manifest.json` as `browser_health_start` and logged as `browser_health_start`.
- non-resume preflight target cleanup via `Target.getTargets` / `Target.closeTarget`, logged as `preflight_cleanup`.
- guaranteed teardown in `finally`: `ChromiumRL.disable` then `Target.closeTarget` for the task tab, logged as `teardown_complete`.
- clean `KeyboardInterrupt` handling; Ctrl-C exits 130 without traceback and still closes the task tab.

Five consecutive runs without restarting the container:

| task | elapsed seconds | targets after | docker stats after |
|---|---:|---:|---|
| task-v8-leak-check-001 | 9.8 | 1 | 11.78% 521.2MiB / 251.4GiB |
| task-v8-leak-check-002 | 13.25 | 1 | 19.17% 552.2MiB / 251.4GiB |
| task-v8-leak-check-003 | 11.45 | 1 | 17.45% 557.9MiB / 251.4GiB |
| task-v8-leak-check-004 | 10.88 | 1 | 12.37% 556.7MiB / 251.4GiB |
| task-v8-leak-check-005 | 12.22 | 1 | 14.86% 558.8MiB / 251.4GiB |

Result: target count returned to 1 after every run; CPU did not accumulate.

Ctrl-C test:

- task: `task-v8-interrupt-002`
- exit code: 130
- target count after interrupt: 1
- log contains `teardown_complete` with `close_target.ok: true`

## Repository cleanup

Moved phase reports to `docs/history/`:

- `PHASE_V3_REPORT.md`
- `PHASE_V4_REPORT.md`
- `PHASE_V5_REPORT.md`
- `PHASE_V6_REPORT.md`
- `PHASE_V7_ADDENDUM_REPORT.md`
- `PHASE_A_REPORT.md`
- `PHASE_T_REPORT.md`

Deleted explicit obsolete task folders:

- `bench-wiki-v6-250`
- `diag-baseline-001`
- `diag-baseline-t8-001`
- `diag-baseline-t8-002`
- `diag-baseline-t8-003`
- `diag-baseline-t8-004`
- `regress-amazon-old`
- `regress-amazon-old-valid`
- `task8`

Ambiguous task folders left in place instead of guessing:

- `bench-books`
- `bench-books-js`
- `bench-hostile`
- `bench-quotes`
- `bench-quotes-js`
- `bench-wiki`
- `bench-wiki-js`
- `lean-smoke-001`
- `my-manual-task-001`
- `my-manual-task-002`
- `my-manual-task-003`
- `my-manual-task-04`
- `task-v6-books-mystery-001`
- `task-v7-books-check-001`
- `task-v7-books-check-002`
- `task-v8-interrupt-001`
- `task-v8-interrupt-002`
- `task-v8-layout-both-001`
- `task-v8-leak-check-001`
- `task-v8-leak-check-002`
- `task-v8-leak-check-003`
- `task-v8-leak-check-004`
- `task-v8-leak-check-005`
- `task-v8-observations-001`
- `task1`
- `task14`
- `task17`
- `task2`
- `task3`
- `task4`
- `task5`
- `task7`
- `test01`
- `test02`
- `test03`
- `test04`

Diagnostics policy used: archived old top-level diagnostics to `diagnostics/archive/`, kept `diagnostics/v6/`, `diagnostics/v7/`, and `diagnostics/v8/`.

Reusable probes kept under `diagnostics/probes/`: `coord_probe.py`, `identity_stability_probe.py`, `nav_rebind_probe.py`, `t2_probe.py`.

Canonical example retained and migrated to v8 layout: `tasks/task-v7-books-check-003`.

## Acceptance criteria

| # | Result | Evidence |
|---|---|---|
| 1 | PASS | `task-v8-layout-both-001/step_001` has exactly 7 files and no subdirectories. |
| 2 | PASS | New steps write one after-state `page_state.json`; before state remains in `dom_diff.json` / `log.jsonl`. |
| 3 | PASS | Default step has exactly 2 gzip files: `dom_before.json.gz`, `dom_after.json.gz`. |
| 4 | PASS | `--keep-observations` restored observation files at step top level in `task-v8-observations-001`. |
| 5 | PASS | Five-run table above: target count stayed at 1 after every run, CPU stayed below 20%. |
| 6 | PASS | Ctrl-C test closed the task tab and logged `teardown_complete`; no traceback after handler patch. |
| 7 | PASS | Phase reports are under `docs/history/`; no phase reports remain at repo root. Current user-facing docs are `README.md` and `MIGRATION.md`. |
| 8 | PARTIAL | Explicit obsolete folders were removed and listed. Ambiguous folders were left and flagged for safety. |
| 9 | PASS | README artifact layout matches v8 flat layout and includes scripts inventory. |

## Notes

The initial broad deletion plan was rejected as too risky because it would remove every task except one. I switched to bounded cleanup: delete only explicitly obsolete patterns and flag ambiguous folders for manual review.
