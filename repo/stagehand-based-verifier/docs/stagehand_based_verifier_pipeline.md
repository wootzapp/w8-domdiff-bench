# Implemented Stagehand Verifier Pipeline

## Scope and isolation

The package under `src/stagehand_verifier` is a standalone implementation of
the Universal-Verifier-style evaluation flow. It has no runtime imports from
Microsoft `fara`, `webeval`, or the earlier `fara-dom-verifier`. The read-only
reference commit and protected hashes are recorded in
`UPSTREAM_VERIFIER.lock.json`.

Only the evidence modality is Stagehand-specific. Canonical judge roles remain:

- GPT-5.2: rubric generation/dependencies, semantic criterion judgment,
  side effects, outcome, and first failure;
- o4-mini: action/rubric and task-validity judgments.

## Accepted evidence

The loader selects only:

- task instruction and initial URL;
- final answer text;
- ordered Stagehand action names and supplied arguments;
- bounded tool success/error/result fields;
- `aria.txt` semantic states;
- `page_state.json` URL, title, readiness, scroll, viewport, and bounded body text.

It removes reasoning and image/binary fields. Screenshots, evidence images,
model request/prompt files, agent input/output, Stagehand logs, and trajectory
JSONL are excluded from the evidence path. Recorder success fields do not
affect scoring.

## State model and alignment

`loader.py` validates the recording and builds:

```text
action 1: synthetic about:blank -> step_001 state
action 2: step_001 state        -> step_002 state
...
action N: step_N-1 state        -> step_N state
terminal:                         step_N+1 state
```

The synthetic state is legal only for a first `goto` when the recorder
declares `about:blank`. Gaps, duplicate ordinals, missing tool results, extra
action-bearing terminal states, and action-log mismatches fail before any API
client is created.

`aria_parser.py` retains Stagehand raw node references and constructs stable
semantic keys from role, accessible name, ancestry, and occurrence. Unknown
ARIA lines are retained as bounded parse diagnostics. `semantic_diff.py`
conservatively derives added, removed, and updated nodes plus URL, title, and
scroll transitions; the diff never replaces the full before/after state.

## Criterion retrieval

`evidence_projection.py` implements a criterion-by-transition relevance layer:

1. derive concepts at inference time from task, criterion, and final-answer claims;
2. score each normalized transition from 0 to 10;
3. rank changed nodes, relevant before/after nodes, actions, URLs, and errors;
4. select at most the configured top-k frames above the threshold;
5. enforce per-frame and per-criterion character budgets;
6. attach step, action ID, before/after URL, semantic node IDs, raw Stagehand
   references, and source paths.

No product-, website-, or task-family keywords are hard-coded. A criterion
judge receives only selected projections. Outcome receives the terminal state
and a deduplicated selection of relevant projections. Side-effect and failure
stages receive a separate bounded global transition summary because those
stages must reason across actions, but they still do not receive raw ARIA trees.

## Scoring stages

`agent.py` executes:

1. load and validate a frozen rubric, or generate and dependency-check a new rubric;
2. run an explicit deterministic check locally when the rubric supplies one;
3. for unresolved criteria, select evidence and run action-only analysis;
4. run semantic evidence judgment with `supported`, `contradicted`, `partial`,
   or `unknown` status;
5. enforce criterion conditions and dependencies;
6. compute earned/possible process score;
7. inspect the compact timeline for unintended effects and apply a grounded penalty;
8. evaluate terminal outcome and unsupported final-answer claims;
9. assess task validity with and without trajectory evidence;
10. classify the earliest failure when the outcome or evidence establishes one.

An evidence judge is instructed that actions prove attempts, `tool_result.ok`
does not prove task success, final answers are claims, persistent terminal state
is strongest, and pixel-only requirements are unknown.

## Deterministic checks

Deterministic checks are deliberately opt-in and auditable. A rubric item may
use one operator:

```json
{"deterministic_check": {"final_domain_equals": "example.com"}}
```

Supported checks cover exact URL/domain facts, exact terminal semantic text,
presence of an action name, and explicit tool errors. The implementation does
not infer a deterministic assertion from ordinary semantic prose. A matching
criterion bypasses both criterion action and semantic LLM calls.

## Result, usage, and cache behavior

`runner.py` writes a per-task Stagehand score and run JSONL report. The result
includes the frozen rubric hash, all criterion decisions and evidence links,
process/outcome/failure records, model roles, alignment/coverage, successful
LLM calls and tokens by role, and a cache key.

The cache key includes evidence mode/schema, adapter and prompt versions,
reference commit, rubric hash, judge models, thresholds, top-k/budgets,
majority-vote settings, and task alignment counts. It cannot collide with
screenshot, ChromiumRL full-DOM, or DOM-diff caches.

## Limitations

Stagehand ARIA cannot independently verify pixels, color, visual style, exact
layout or visibility, occlusion, image contents, or canvas/chart/map/video
content. Missing semantic evidence is never converted into success or failure.
The current loader supports the exact after-action recording contract inspected
in `task01` through `task04`; recordings with an explicit initial state will
need a schema-versioned extension.
