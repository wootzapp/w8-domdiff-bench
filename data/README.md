# Browser tasks

`tasks.jsonl` contains 40 public, read-only browser tasks: 10 each at easy, medium,
hard and complex difficulty. Each task identifies a `start_url` and a
`stopping_condition` describing the required final deliverables.

The catalog and frozen rubrics are hosted on the
[`paired-capture` dataset branch](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/tree/paired-capture).
The [runbook](../docs/runbook.md#get-the-benchmark-and-install-python) downloads
them into the local `data/` directory.

| Field | Description |
| --- | --- |
| `task_id` | Stable task identifier. |
| `task_name` | Short task title. |
| `category` | Type of research or comparison. |
| `instruction` | Scope, required findings and answer format. |
| `start_url` | Public website entry point. |
| `stopping_condition` | Required deliverables before finishing. |
| `constraints` | Shared browser, access and read-only rules. |
| `difficulty` | Easy, medium, hard or complex, based on the required work. |

Difficulty describes the research scope; every task uses the same configured
turn cap. The turn ranges below are planning guidance, not measured task lengths.

| Difficulty | Task IDs | Scope | Turn guidance |
| --- | --- | --- | --- |
| Easy | `task_01`–`task_10` | One site, one to three pages, a few facts or a simple filter or search. | 5–15 |
| Medium | `task_11`–`task_20` | Filters, sorting or detail pages with several related findings. | 15–40 |
| Hard | `task_21`–`task_30` | Deep navigation or two to three sites with multiple constraints. | 40–100 |
| Complex | `task_31`–`task_40` | Several sites, comparing or calculating across many items. | Generally under 150 |

Report changing values as observed during the run and cite the source
pages used. The actor receives the instruction, stopping condition and constraints
together. See the [runbook](../docs/runbook.md) for catalog validation, rubric
preparation and recording commands.

## Storage

| Dataset path | Contents |
| --- | --- |
| `tasks.jsonl` | Catalog, with the eight fields above. |
| `rubrics/` | Frozen task criteria and catalog bindings. |
| `recordings/runN/` | One trial's ledger, catalog copy and raw actor attempts. |
| `trajectories/runN/<arm>/<task>/` | Paired verifier inputs and source hashes for that recording. |
| `evaluations/runN/<arm>/<task>/` | Shared completion, profile-specific native results, audit and call receipts. |
| `results/runN/` | Aggregated summaries, pairs, per-task metrics and report. |
| `manifests/` | Verifier package integrity records. |

Each `runN` contains one trial of the selected tasks in both arms. Formats are
paired only within a recording; earlier technical attempts remain separate from
the final attempt. Diagnostic logs stay under local `logs/runN/`.

Prepare the trajectories for a saved run:

```bash
: "${BENCH_RUN:?Set the saved run name}"
.venv/bin/python -m w8bench.task_recorder.prepare_verifier_data \
  "recordings/$BENCH_RUN" trajectories
```

The evaluator also prepares and reuses these inputs. Existing bound trajectories
are validated before reuse.

Authenticate for uploads:

```bash
hf auth login
hf auth whoami
```

Upload finalized recordings, trajectories, evaluations and aggregation output:

```bash
: "${BENCH_RUN:?Set the saved run name}"
: "${BENCH_RESULT_DIR:?Set the printed aggregation output directory}"
hf upload WootzappLab/browser-agent-tasks \
  "recordings/$BENCH_RUN" "recordings/$BENCH_RUN" \
  --type dataset --revision paired-capture
hf upload WootzappLab/browser-agent-tasks \
  "trajectories/$BENCH_RUN" "trajectories/$BENCH_RUN" \
  --type dataset --revision paired-capture
hf upload WootzappLab/browser-agent-tasks \
  "evaluations/$BENCH_RUN" "evaluations/$BENCH_RUN" \
  --type dataset --revision paired-capture
hf upload WootzappLab/browser-agent-tasks \
  "$BENCH_RESULT_DIR" "results/$BENCH_RUN" \
  --type dataset --revision paired-capture
```

`web_surfer.log` is part of the recorded action history and remains included.
Credentials, diagnostic logs, private curation and solution notes are not dataset
artifacts. Recording and projection hashes in the receipts bind the published
formats to the same task, arm and trial.
