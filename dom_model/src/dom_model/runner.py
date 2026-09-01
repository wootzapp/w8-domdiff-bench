"""Controlled standalone runner over the package-local DOM-model pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .clients.graceful_client import GracefulRetryClient
from .rubric_agent import (
    MMRubricAgent,
    MMRubricAgentConfig,
    MMRubricOutcomeResult,
    MMRubricResult,
)
from .utils.action_schema import FARA_ACTION_DEFINITIONS
from .utils.metrics import rubric_receipt
from .utils.rubric import load_frozen_rubric, require_matching_embedded_rubric

from .control import (
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
    canonical_json_bytes,
    load_one_task,
    validate_generation_metrics,
    write_json,
)

from .adapter import create_datapoint
from .dom_model_agent import DomModelRubricAgent
from .alignment import validate_alignment
from .instrumentation import call_metrics, instrument_client_calls, usage_dict
from .package_manifest import source_receipt
from .state_parser import load_dom_model_states
from .trajectory_helpers import action_events, load_trajectory


logger = logging.getLogger("dom_model")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _read_task_data(task_dir: Path) -> dict[str, Any]:
    task = load_one_task(task_dir / "task_data.json")
    normalized = dict(task)
    normalized["id"] = str(task.get("id") or task.get("task_id") or task_dir.name)
    normalized["question"] = str(task.get("question") or task.get("confirmed_task") or "")
    normalized["init_url"] = str(task.get("init_url") or task.get("website") or "")
    if not normalized["question"] or not normalized["init_url"]:
        raise ValueError("Task data must contain instruction and initial URL")
    return normalized


def preflight_dom_model_task(
    task_dir: Path, *, rubric_file: str | Path, generation_metrics: str | Path
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    package = source_receipt()
    for filename in ("task_data.json", "web_surfer.log", "final_answer.json", "task_data_with_canonical_rubric.json"):
        if not (task_dir / filename).is_file():
            raise ValueError(f"Missing DOM-model control file: {task_dir / filename}")
    task = _read_task_data(task_dir)
    task_id = task["id"]
    frozen = load_frozen_rubric(rubric_file, expected_task_id=task_id)
    task = require_matching_embedded_rubric(task, frozen)
    sidecar = load_one_task(task_dir / "task_data_with_canonical_rubric.json")
    embedded = sidecar.pop("precomputed_rubric", None)
    base = load_one_task(task_dir / "task_data.json")
    base.pop("precomputed_rubric", None)
    if canonical_json_bytes(sidecar) != canonical_json_bytes(base):
        raise ValueError("Frozen-rubric sidecar task fields drifted")
    if canonical_json_bytes(embedded) != canonical_json_bytes(frozen.precomputed_rubric):
        raise ValueError("Frozen-rubric sidecar rubric drifted")
    metrics = validate_generation_metrics(generation_metrics, type("Frozen", (), {
        "task_id": task_id,
        "rubric": frozen.precomputed_rubric,
        "sha256": frozen.sha256,
        "denominator": sum(float(item["max_points"]) for item in frozen.precomputed_rubric["items"]),
    })())
    trajectory = load_trajectory(task_dir)
    actions = action_events(trajectory)
    states = load_dom_model_states(task_dir, action_count=len(actions))
    alignment = validate_alignment(
        task_id=task_id,
        initial_url=task["init_url"],
        actions=actions,
        states=states,
    )
    answer = json.loads((task_dir / "final_answer.json").read_text(encoding="utf-8"))
    if not isinstance(answer, dict) or not isinstance(answer.get("final_answer"), str):
        raise ValueError("final_answer.json must contain final_answer text")
    if "screenshots" in answer or answer.get("token_usage") != {}:
        raise ValueError("DOM-model final answer must omit screenshots and contain token_usage: {}")
    allowed = {
        "task_data.json", "web_surfer.log", "final_answer.json",
        "task_data_with_canonical_rubric.json", *(state.path.name for state in states),
    }
    unexpected = sorted(
        path.relative_to(task_dir).as_posix()
        for path in task_dir.rglob("*")
        if path.is_file() and path.relative_to(task_dir).as_posix() not in allowed
    )
    if unexpected:
        raise ValueError(f"Unexpected DOM-model task files: {unexpected}")
    receipt = {
        "task_id": task_id,
        "actions": len(actions),
        "dom_model_states": len(states),
        "initial_state": 0,
        "final_state": states[-1].index,
        "alignment": alignment.as_dict(),
        "frozen_rubric_sha256": frozen.sha256,
        "criterion_order": [item["criterion"] for item in frozen.precomputed_rubric["items"]],
        "maximum_points": [float(item["max_points"]) for item in frozen.precomputed_rubric["items"]],
        "criterion_denominator": sum(float(item["max_points"]) for item in frozen.precomputed_rubric["items"]),
        "sidecar_validated": True,
        "phase_a_metrics": str(Path(generation_metrics).resolve(strict=True)),
        "phase_a_rubric_generation_calls": metrics["rubric_generation_calls"],
        "rubric_generation_calls": 0,
        "package_manifest": package,
    }
    return task, receipt, trajectory


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    task_dir = Path(args.input).resolve(strict=True)
    task_data, preflight, trajectory = preflight_dom_model_task(
        task_dir,
        rubric_file=args.rubric_file,
        generation_metrics=args.generation_metrics,
    )
    if args.dry_run:
        return {
            "status": "preflight_passed",
            "paid_calls_authorized": False,
            "writes_performed": False,
            "preflight": preflight,
        }
    eval_config = Path(args.eval_config).resolve(strict=True)
    o4mini_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.o4mini_model
    )
    gpt5_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.judge_model
    )
    instrument_client_calls(o4mini_client)
    instrument_client_calls(gpt5_client)
    agent = DomModelRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=o4mini_client,
            gpt5_client=gpt5_client,
            max_images_per_criterion=args.max_evidence_per_criterion,
            min_relevance_threshold=args.min_relevance_threshold,
            majority_vote_instances=args.majority_vote_instances,
            dom_model_state_char_budget=args.dom_model_state_char_budget,
            redo_eval=args.redo_eval,
            rubric_score_threshold=args.rubric_threshold,
            action_definitions=FARA_ACTION_DEFINITIONS,
        )
    )
    datapoint = create_datapoint(task_data, trajectory)
    agent_input = MMRubricAgent._extract_input_from_datapoint(
        datapoint, screenshots_dir=str(task_dir), redo_eval=args.redo_eval
    )
    raw = asyncio.run(agent._generate_reply(agent_input))
    if not isinstance(raw, dict) or raw.get("error"):
        raise RuntimeError(f"Rubric agent failed: {raw.get('error') if isinstance(raw, dict) else raw}")
    wrapped = agent._wrap_result(raw)
    rubric_result = next(item for item in wrapped if isinstance(item, MMRubricResult))
    outcome_result = next(item for item in wrapped if isinstance(item, MMRubricOutcomeResult))
    outcome_pass = outcome_result.output_success is True
    process_pass = bool(rubric_result.rubric_is_success)
    if args.success == "process":
        score = int(process_pass)
    elif args.success == "both":
        score = int(process_pass and outcome_pass)
    else:
        score = int(outcome_pass)
    frozen = load_frozen_rubric(args.rubric_file, expected_task_id=task_data["id"])
    result = {
        "task_id": task_data["id"],
        "verifier": "dom_model",
        "evidence_mode": "dom_model",
        "score": score,
        "success_criterion": args.success,
        "rubric_score": rubric_result.score,
        "rubric_total_max_points": rubric_result.total_max_points,
        "rubric_total_earned_points": rubric_result.total_earned_points,
        "rubric_is_success": process_pass,
        "outcome": _jsonable(outcome_result),
        "preflight": preflight,
        **rubric_receipt(path=str(frozen.path), sha256=frozen.sha256, rubric=frozen.precomputed_rubric),
        "rubric_generation_calls": 0,
        "token_usage": {
            "judge": usage_dict(gpt5_client),
            "action_judge": usage_dict(o4mini_client),
        },
        "call_metrics": {
            "judge": call_metrics(gpt5_client),
            "action_judge": call_metrics(o4mini_client),
            "rubric_generation_calls": 0,
        },
        "intermediate_mm_rubric_steps": raw.get("intermediate_mm_rubric_steps"),
        "evidence_audit": agent.evidence_audit,
        "duration_sec": round(time.time() - started, 3),
    }
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "evidence_audit.json", agent.evidence_audit)
    output_path = write_json(output_dir / "result.json", result)
    result["result_path"] = str(output_path)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--rubric-file", required=True)
    parser.add_argument("--generation-metrics", required=True)
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--judge-model", default=CANONICAL_JUDGE_MODEL)
    parser.add_argument("--o4mini-model", default=CANONICAL_ACTION_MODEL)
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument("--max-evidence-per-criterion", type=int, default=5)
    # Keep Microsoft's native evidence-analysis behavior. A positive value
    # drops low-relevance top-K states before analysis and would make the DOM
    # verifier structurally different from the screenshot baseline.
    parser.add_argument("--min-relevance-threshold", type=int, default=0)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--dom-model-state-char-budget", type=int, default=350000)
    parser.add_argument("--success", choices=("outcome", "process", "both"), default="outcome")
    parser.add_argument("--redo-eval", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    print(json.dumps(run(parse_args(argv)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
