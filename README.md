# Universal Verifier Screenshot vs. DOM-Model Experiment

`benchmarks-2/` is a self-contained, controlled comparison between Microsoft's
original screenshot verifier and a DOM-model evidence verifier. No file under
`benchmarks/` or `ms-paper-execution/` is imported at verifier runtime or
modified by this experiment.

## Structure

```text
benchmarks-2/
├── microsoft_verifier/   # complete, unchanged Microsoft screenshot package
├── dom_model/            # complete verifier package with DOM-model evidence hooks
├── scripts/              # shared Phase A/Phase B control plane and offline tests
├── config/               # experiment-local endpoint model declarations
├── data/                 # isolated staged dataset copies only
├── manifests/            # fixed local package hashes
├── rubrics/              # canonical rubrics and Phase A metrics
├── results/              # isolated Phase B inputs and comparison artifacts
├── IMPLEMENTATION_PLAN.md
└── RUNBOOK.md
```

Both packages independently contain their runner, clients, prompts, resources,
rubric generation/evaluation, relevance, top-K, evidence analysis, scoring,
outcome, failure, penalty, validity, metrics, and tests. Neither imports the
other package or shared orchestration code.

## Dependency graph

```text
scripts/generate_frozen_rubric.py
    └── microsoft_verifier (local Phase A rubric generation)

scripts/run_comparison.py
    ├── microsoft_verifier subprocess (PYTHONPATH = microsoft_verifier/src only)
    └── dom_model subprocess          (PYTHONPATH = dom_model/src only)

microsoft_verifier ──X── dom_model
dom_model          ──X── microsoft_verifier
either verifier    ──X── benchmarks/ or ms-paper-execution/
```

Microsoft's local package is the fixed baseline and remains byte-for-byte equal
to the original copied source. The DOM-model package reproduces that pipeline
locally; its intentional behavioral boundary is evidence loading, relevance,
and analysis for ordered complete `dom_model0..N.txt` states. It does not use
the existing DOM-diff verifier.

## Frozen-rubric control

Phase A invokes Microsoft's rubric workflow once, or validates an existing
rubric import, and freezes one canonical rubric. It records its calls and tokens
separately and writes identical sidecars only inside isolated staged dataset
copies. Phase B passes the exact same `--rubric-file` path to both runners and
requires matching task ID, hash, criterion order, descriptions, maximum points,
denominator, sidecars, and Phase A metrics. Normalized scoring artifacts require
`rubric_generation_calls: 0`.

Commands are offline by default. Paid clients are not constructed unless an
operator explicitly supplies `--execute`; no paid evaluation was run during
implementation. See [RUNBOOK.md](RUNBOOK.md).
