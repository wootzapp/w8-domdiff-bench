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

| Difficulty | Scope | Turn guidance |
| --- | --- | --- |
| Easy | One site, one to three pages, a few facts or a simple filter or search. | 5–15 |
| Medium | Filters, sorting or detail pages with several related findings. | 15–40 |
| Hard | Deep navigation or two to three sites with multiple constraints. | 40–100 |
| Complex | Several sites, comparing or calculating across many items. | Generally under 150 |

Report changing values as observed during the run and cite the source
pages used. The actor receives the instruction, stopping condition and constraints
together. See the [runbook](../docs/runbook.md) for catalog validation, rubric
preparation and recording commands.

## Storage

| Dataset path | Contents |
| --- | --- |
| `tasks.jsonl` | Catalog, with the eight fields above. |
| `rubrics/` | Frozen task criteria and catalog bindings. |
| `recordings/<collection>/` | Ledger, catalog copy and raw actor attempts. |
| `trajectories/<collection>/` | Paired verifier inputs by trial, arm, task and recording hash. |
| `evaluations/<collection>/` | Completion, native results, audit, profile comparison and call receipts. |
| `results/<collection>/` | Aggregated summaries, pairs, per-task metrics and report. |
| `manifests/` | Verifier package integrity records. |

Use a distinct collection name and publish finalized artifacts. Dataset paths
retain all trials and technical attempts; formats are paired only within a run.

Prepare the trajectories:

```bash
: "${BENCH_COLLECTION_RUN:?Set the saved collection run name}"
.venv/bin/python -m w8bench.task_recorder.prepare_verifier_data \
  "recordings/$BENCH_COLLECTION_RUN" "trajectories/$BENCH_COLLECTION_RUN"
```

Authenticate for uploads:

```bash
hf auth login
hf auth whoami
```

Upload the raw recordings, trajectories and aggregation output:

```bash
: "${BENCH_COLLECTION_RUN:?Set the saved collection run name}"
: "${BENCH_RESULT_DIR:?Set the printed aggregation output directory}"
hf upload WootzappLab/browser-agent-tasks \
  "recordings/$BENCH_COLLECTION_RUN" "recordings/$BENCH_COLLECTION_RUN" \
  --type dataset --revision paired-capture \
  --exclude "evaluations/**" --exclude "**/evaluations/**"
hf upload WootzappLab/browser-agent-tasks \
  "trajectories/$BENCH_COLLECTION_RUN" "trajectories/$BENCH_COLLECTION_RUN" \
  --type dataset --revision paired-capture
hf upload WootzappLab/browser-agent-tasks \
  "$BENCH_RESULT_DIR" "results/$BENCH_COLLECTION_RUN" \
  --type dataset --revision paired-capture
```

Upload each evaluation directory with its collection-relative prefix:

```bash
(
  set -euo pipefail
  test -d "recordings/$BENCH_COLLECTION_RUN"
  while IFS= read -r -d '' bench_evaluation_dir; do
    bench_evaluation_prefix="${bench_evaluation_dir#recordings/}"
    bench_evaluation_prefix="${bench_evaluation_prefix%/evaluations}"
    hf upload WootzappLab/browser-agent-tasks \
      "$bench_evaluation_dir" "evaluations/$bench_evaluation_prefix" \
      --type dataset --revision paired-capture
  done < <(find "recordings/$BENCH_COLLECTION_RUN" -type d -name evaluations -prune -print0)
)
```

The `evaluations/` prefix mirrors each local evaluation directory's parent path.
Restoring evaluations places it beside the same actor directories; evaluation
receipts retain recording and source bindings. Credentials, private curation and
solution notes are not dataset artifacts.
