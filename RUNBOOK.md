# Frozen-Rubric Comparison Runbook

Run from the repository root. Shared orchestration needs both local packages;
each Phase B child process is subsequently restricted to its own package.

## Create the experiment-local environment

```bash
python3 -m venv benchmarks-2/.venv
benchmarks-2/.venv/bin/python -m pip install --upgrade pip
benchmarks-2/.venv/bin/python -m pip install -r benchmarks-2/requirements.txt
cp benchmarks-2/.env.example benchmarks-2/.env
# Edit benchmarks-2/.env and set OPENAI_API_KEY.
```

The local `.env` is ignored and must not be committed. Offline preflights and
tests make no paid calls. The `.env` is needed only for an explicitly
authorized `--execute` run.
Only dependencies are installed: the verifier packages are loaded from their
own isolated `src` directories through `PYTHONPATH`, preserving their fixed
package manifests.

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="benchmarks-2/microsoft_verifier/src:benchmarks-2/dom_model/src:benchmarks-2"
```

## Stage matching task copies

```text
benchmarks-2/data/data-new-screenshot/taskXX/
benchmarks-2/data/data-new-dom-model/taskXX/
```

Only experiment-owned staged copies are valid write targets. Source datasets
under `benchmarks/` and `ms-paper-execution/` must remain read-only.

The DOM folder must contain `task_data.json`, `web_surfer.log`,
`final_answer.json`, and contiguous `dom_model0.txt` through
`dom_modelN.txt`. For N actions, exactly N+1 states are required:
`dom_model0` is initial, state i is after action i, and state N is final.

## Phase A: freeze one rubric

Offline preflight (prints a receipt and writes nothing):

```bash
benchmarks-2/.venv/bin/python -m scripts.generate_frozen_rubric \
  --screenshot-task benchmarks-2/data/data-new-screenshot/taskXX \
  --dom-task benchmarks-2/data/data-new-dom-model/taskXX
```

After separate paid-call authorization, add `--execute` to invoke Microsoft's
unchanged rubric-generation workflow exactly once. To freeze an existing rubric
without LLM calls, use `--import-rubric PATH --execute`. Phase A writes the
canonical rubric, its generation metrics, and one matching rubric sidecar in
each staged task copy. Existing outputs require `--overwrite`.

## Phase B: score both evidence modes

Offline preflight:

```bash
benchmarks-2/.venv/bin/python -m scripts.run_comparison --task taskXX
```

This validates package manifests, paired task/action/final-answer identity,
N+1 evidence alignment, endpoint model declarations, both sidecars, the rubric
hash/order/descriptions/maxima/denominator, and Phase A generation metrics. It
also confirms both generated commands share the exact rubric path and
`--redo-eval`. It performs no writes, subprocess runs, or paid calls.

Only after review, add `--execute` to authorize scoring. Inputs and frozen
controls are first copied beneath the unique result directory. Microsoft's
screenshot subprocess receives only `microsoft_verifier/src` on
`PYTHONPATH`; the DOM subprocess receives only `dom_model/src`.

Results record process and outcome scores, criterion rescoring, failure and
validity outputs, penalties, logical LLM calls, API attempts, retries, prompt /
completion / reasoning tokens, warnings, evidence selections, context
omissions, and `rubric_generation_calls: 0`. Phase A usage remains separate.

## Evidence limits

Raw DOM-model states preserve source ordering, URLs, titles, action boundaries,
labels, values, roles, refs, controls, dialogs, alerts, validation messages,
errors, final state, hashes, and line provenance. Missing or truncated content
is unproven, not false, and is recorded as a warning or omission.

DOM text cannot prove pixel-only color, typography, borders, spacing, precise
geometry, overlap, clipping, z-order, responsive layout, visual emphasis, or
unrepresented image, chart, canvas, video, shadow-DOM, or cross-origin content.
It also cannot prove server-side success unless the captured browser state
exposes it.

## Offline tests

```bash
cd benchmarks-2/microsoft_verifier
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ../.venv/bin/python -m pytest -p no:cacheprovider -q

cd ../dom_model
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ../.venv/bin/python -m pytest -p no:cacheprovider -q

cd ..
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="microsoft_verifier/src:dom_model/src:." \
.venv/bin/python -m pytest -p no:cacheprovider -q scripts/tests
```
