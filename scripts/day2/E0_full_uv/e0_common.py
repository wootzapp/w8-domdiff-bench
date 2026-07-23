"""Shared paths and serialization helpers for Day 2 E0 only."""

import json
import sys
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

DATA_ROOT = PROJECT_ROOT / "data/materialized/day2/E0_full_uv"
TRAJ_ROOT = DATA_ROOT / "traj"
TASKS_PATH = DATA_ROOT / "tasks.json"
RUN_INPUTS_ROOT = DATA_ROOT / "run_inputs"
OUTPUT_ROOT = PROJECT_ROOT / "outputs/day2/E0_full_uv"
MANIFEST_ROOT = OUTPUT_ROOT / "manifests"
ENVIRONMENT_ROOT = OUTPUT_ROOT / "environment"
LOG_ROOT = OUTPUT_ROOT / "logs"
BATCH_REPORT_ROOT = OUTPUT_ROOT / "batch_reports"
RAW_SCORE_ROOT = OUTPUT_ROOT / "raw_scores"
VALIDATION_PATH = MANIFEST_ROOT / "validation_results.jsonl"
CORPUS_MANIFEST_PATH = MANIFEST_ROOT / "full_corpus_manifest.jsonl"
EXECUTION_PLAN_PATH = MANIFEST_ROOT / "execution_plan.json"

ALLOWED_INPUT_FIELDS = {
    "task_id",
    "instruction",
    "init_url",
    "web_surfer_log",
    "screenshots",
    "final_answer",
    "is_aborted",
}

FORBIDDEN_ANNOTATION_FIELDS = {
    "gpt_eval_json",
    "uv_rubric_score",
    "uv_outcome_success",
    "mm_is_success",
    "verifier_is_success",
    "final_human_outcome_label",
    "final_human_process_label",
    "median_human_rubric_score_agnostic",
    "majority_human_outcome_vote",
}


def ensure_output_dirs() -> None:
    for path in (
        DATA_ROOT,
        TRAJ_ROOT,
        RUN_INPUTS_ROOT,
        OUTPUT_ROOT,
        MANIFEST_ROOT,
        ENVIRONMENT_ROOT,
        LOG_ROOT,
        BATCH_REPORT_ROOT,
        RAW_SCORE_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def project_relative(path: Path) -> str:
    """Return a stable path relative to the experiment repository."""
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
