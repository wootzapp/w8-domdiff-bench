# Evaluation Protocol

The comparison uses one recorded task, one final answer, one action history,
and one frozen rubric for both evidence modes.

## Inputs

Each paired task contains:

- ordered screenshots for the screenshot verifier;
- ordered `dom_modelN.txt` states for the DOM-model verifier;
- the same `web_surfer.log` action history;
- the same final answer;
- the same task definition and frozen rubric.

The preflight checks task identity, action alignment, state ordering, rubric
shape, and required files before model clients are created.

## Controlled scoring

Both sides use the same judge model, action model, rubric threshold, evidence
count, majority-vote count, and success rule. Only the evidence loader differs.
The comparison command fails if those controls drift.

One rubric is generated or imported first. Its canonical SHA-256 and point
denominator are recorded, then the unchanged object is passed to both sides.

## Evidence-loss audit

The audit asks whether a rubric fact is present in each ordered evidence
source. It keeps missing source evidence separate from judge disagreement.
The headline counts are therefore evidence-availability measurements, not a
general claim that one verifier always scores tasks better.

## Commands

Download and validate one pair without paid calls or evaluation output:

```bash
./scripts/run-comparison --task task_01
```

Run the controlled comparison:

```bash
./scripts/run-comparison --task task_01 --execute
```

Run every paired task:

```bash
./scripts/run-comparison --all --execute
```

Generated runs are written under `evaluation/`, which is ignored by Git.

