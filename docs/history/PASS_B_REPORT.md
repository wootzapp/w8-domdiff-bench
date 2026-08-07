# Pass B Report — compact DOM diff

Generated: 2026-08-07T09:19:03.518149+00:00

## Scope

Pass B was applied only to the Python recorder/diff path. It does not depend on a Chromium build and does not change `saveDOMState` capture semantics. The reference C++ repeated-group work is still deferred, so repeated-group collapse was implemented directly in the Python diff builder using sibling structural signatures: `>=3` members with matching tag/class/role/structural leaf signature.

## Implemented

- Short ids plus `paths` map in compact `dom_diff.json`.
- Repeated group collapse for same-document added/removed entries.
- Compact cross-document representation: `navigation`, `document` counts, `text_delta`, `top_actions`; no `document_added` / `document_removed` blocks in compact mode.
- `dom_diff.txt` generated from the same builder as `dom_diff.json`.
- `--dom-diff-verbosity {compact,full}`, default `compact`.
- Redundant changed-entry substructure omitted in compact mode; changed entries carry only `changes` plus id/path metadata.
- Sensitive form-property values remain redacted but now include `filled` and `length`, so verifier checks can detect value changes without leaking passwords.
- README, MIGRATION, verifier-bundle export, and verify-example updated for `dom_diff.txt`.

## Validation

- `python3 -m py_compile recorder.py agent_browser/desktop_agent.py scripts/run-diff-benchmarks.py scripts/export-verifier-bundle.py scripts/verify-example.py` passed. Existing invalid-escape warnings remain in older JS string literals.
- `git diff --check` passed.
- `python3 scripts/run-diff-benchmarks.py --output-root diagnostics/pass_b_diff_benchmarks_final4 --collapse-text-chars 500` ran successfully. 13/14 benchmark entries passed; the only failure was `diff-modal-real`, explained below.

## Benchmark-suite result

| Benchmark | Steps | dom_diff.json bytes | Result |
|---|---:|---:|---|
| `diff-checkbox` | 1 | 2659 | PASS except if noted |
| `diff-checkbox-real` | 1 | 2434 | PASS except if noted |
| `diff-dynamic` | 1 | 2311 | PASS except if noted |
| `diff-form` | 3 | 10401 | PASS except if noted |
| `diff-modal` | 1 | 3826 | PASS except if noted |
| `diff-modal-real` | 1 | 2826 | FAIL: no removed subtree or visibility change |
| `diff-navigate-same-site` | 1 | 6633 | PASS except if noted |
| `diff-scroll` | 1 | 2996 | PASS except if noted |
| `diff-select` | 1 | 3773 | PASS except if noted |
| `diff-text` | 1 | 6633 | PASS except if noted |
| `regress-form-observation` | 0 | 0 | PASS except if noted |
| `regress-key-enter` | 0 | 0 | PASS except if noted |
| `regress-overlay-classifier` | 0 | 0 | PASS except if noted |
| `regress-prompt-grounding` | 0 | 0 | PASS except if noted |

`diff-modal-real` remains unresolved as a live-site benchmark/precondition issue: the generic run did not observe a real modal removed/hidden transition. I did not add a site-specific setup click, URL condition, or selector. The synthetic modal benchmark still passes and validates the generic collapse mechanism.

## Size measurements over existing `tasks/tests`

Detailed per-step CSV: `diagnostics/pass_b_task_measurements/per_step_report.csv`

| Metric | Value |
|---|---:|
| Steps measured | 96 |
| Previous total `dom_diff.json` bytes | 1032977 |
| New compact total `dom_diff.json` bytes | 342305 |
| New / old ratio | 0.3314 |
| Reduction | 66.9% |

Critical evidence preservation checks from `tasks/tests`:

| Task / step | Old bytes | New bytes | txt lines | Evidence checked |
|---|---:|---:|---:|---|
| `t1-spa-counter-v2/step_005` | 7829 | 5518 | 10 | `1 item left`, `2 items left` preserved |
| `t2-books-scifi-v4/step_003` | 32304 | 7202 | 124 | `£43.30`, `In stock (15 available)`, `9270575728a13a61` preserved |
| `t9-infinite-scroll-v3/step_011` | 9612 | 4128 | 13 | `George Eliot` preserved |

The 100–200 line target is met for the critical measured steps: T1 counter step is 10 lines, T2 final product step is 124 lines, and T9 appended-quote step is 13 lines. The JSON target of under 5 KB is met on many steps but not all: the T2 final product step is 7,202 bytes. I did not tighten caps because that would risk dropping verifier evidence.

## Files changed

- `recorder.py` — compact diff transform, repeated-group collapse, text renderer, full/compact verbosity, safe redacted form-state metadata.
- `agent_browser/desktop_agent.py` — writes `dom_diff.txt`, passes `--dom-diff-verbosity` into the diff builder.
- `scripts/run-diff-benchmarks.py` — writes text diffs and accepts `--dom-diff-verbosity`; benchmark harness updated for redacted filled/length metadata.
- `scripts/export-verifier-bundle.py` — includes `dom_diff.txt`.
- `scripts/verify-example.py` — requires `dom_diff.txt` and updated docstring.
- `README.md`, `MIGRATION.md` — current layout and compact diff behavior documented.

## Not changed

- No Chromium/reference C++ files were touched in this pass.
- No task-specific selector or URL special case was added to recorder/agent execution.
- No verifier evidence detection was intentionally filtered out; the compact format changes representation, not semantic detection.
