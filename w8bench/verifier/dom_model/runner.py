"""Controlled standalone runner over the package-local DOM-model pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from w8bench.settings import native_stage_settings, guard_result_settings
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from w8bench.verifier.clients.retry import GracefulRetryClient
from .rubric_agent import MMRubricAgent, MMRubricAgentConfig
from ..models import MMRubricOutcomeResult, MMRubricResult
from ..rubric_scoring import FARA_ACTION_DEFINITIONS, UngradedVerifierError, ungraded_result
from .prompts import SCORING_PROMPT_VERSION

from ..common import (
    native_judge_model,
    CanonicalRubric,
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
    canonical_json_bytes,
    load_one_task,
    load_frozen_rubric,
    require_matching_embedded_rubric,
    rubric_receipt,
    validate_generation_metrics,
    write_json,
)

from .adapter import create_datapoint
from .evidence import DomModelRubricAgent
from .alignment import validate_alignment
from ..instrumentation import call_metrics, instrument_client_calls, usage_dict
from ..package_manifests import dom_source_receipt
from .states import load_dom_model_states
from ..trajectory import action_events, load_trajectory
from .models import Trajectory


logger = logging.getLogger("dom_model")


def _read_task_data(task_dir: Path) -> dict[str, Any]:
    task = load_one_task(task_dir / "task_data.json")
    normalized = dict(task)
    normalized["id"] = str(task.get("id") or task.get("task_id") or task_dir.name)
    normalized["question"] = str(task.get("question") or task.get("confirmed_task") or "")
    normalized["init_url"] = str(task.get("init_url") or task.get("website") or "")
    if not normalized["question"] or not normalized["init_url"]:
        raise ValueError("Task data must contain instruction and initial URL")
    return normalized


def _dom_task_binding(task_dir: Path, rubric_file: str | Path):
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
    return task, task_id, frozen


def _dom_generation_metrics(generation_metrics: str | Path, task_id: str, frozen: Any):
    metrics_rubric = CanonicalRubric(
        task_id=task_id,
        rubric=frozen.precomputed_rubric,
        sha256=frozen.sha256,
        denominator=sum(float(item["max_points"]) for item in frozen.precomputed_rubric["items"]),
        path=frozen.path,
    )
    metrics = validate_generation_metrics(generation_metrics, metrics_rubric, native=True)
    return metrics


def _dom_trajectory(task_dir: Path, task_id: str, task: dict[str, Any]):
    trajectory = load_trajectory(task_dir, Trajectory)
    actions = action_events(trajectory)
    states = load_dom_model_states(task_dir, action_count=len(actions))
    alignment = validate_alignment(
        task_id=task_id,
        initial_url=task["init_url"],
        actions=actions,
        states=states,
        evaluation_context=task.get("evaluation_context"),
    )
    return trajectory, actions, states, alignment


def _validate_dom_answer(task_dir: Path) -> None:
    answer = json.loads((task_dir / "final_answer.json").read_text(encoding="utf-8"))
    if not isinstance(answer, dict) or not isinstance(answer.get("final_answer"), str):
        raise ValueError("final_answer.json must contain final_answer text")
    allowed_answer_fields = {
        "env_state_json", "env_state_raw", "final_answer", "is_aborted",
        "is_rel_paths", "token_usage",
    }
    unexpected_answer_fields = sorted(set(answer) - allowed_answer_fields)
    if unexpected_answer_fields or answer.get("token_usage") != {}:
        raise ValueError(
            "DOM-model final answer must contain only canonical fields and token_usage: {}; "
            f"unexpected fields: {unexpected_answer_fields}"
        )


def _validate_dom_task_files(task_dir: Path, states: list) -> None:
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


def _dom_preflight_receipt(
    task_id, actions, states, alignment, frozen, generation_metrics, metrics, package,
):
    return {
        "task_id": task_id,
        "actions": len(actions),
        "dom_model_states": len(states),
        "initial_state": alignment.initial_state,
        "final_state": alignment.final_state,
        "alignment": alignment.as_dict(),
        "frozen_rubric_sha256": frozen.sha256,
        "criterion_order": [item["criterion"] for item in frozen.precomputed_rubric["items"]],
        "maximum_points": [float(item["max_points"]) for item in frozen.precomputed_rubric["items"]],
        "criterion_denominator": sum(float(item["max_points"]) for item in frozen.precomputed_rubric["items"]),
        "sidecar_validated": True,
        "phase_a_metrics": os.path.relpath(Path(generation_metrics).resolve(strict=True), Path(__file__).resolve().parents[3]),
        "phase_a_rubric_generation_calls": metrics["rubric_generation_calls"],
        "rubric_generation_calls": 0,
        "package_manifest": package,
    }


def _dom_agent(args: argparse.Namespace, task_data: dict[str, Any], eval_config: Path):
    action_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.action_model, evidence_mode='dom_model'
    )
    judge_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.judge_model, evidence_mode='dom_model'
    )
    instrument_client_calls(action_client)
    instrument_client_calls(judge_client)
    agent = DomModelRubricAgent(
        config=MMRubricAgentConfig(
            action_client=action_client,
            validity_date=(task_data.get("evaluation_context") or {}).get("validity_date") or datetime.now(timezone.utc).date().isoformat(),
            judge_client=judge_client,
            max_states_per_criterion=args.max_evidence_per_criterion,
            min_relevance_threshold=args.min_relevance_threshold,
            majority_vote_instances=args.majority_vote_instances,
            dom_model_state_char_budget=args.dom_model_state_char_budget,
            redo_eval=args.redo_eval,
            rubric_score_threshold=args.rubric_threshold,
            action_definitions=FARA_ACTION_DEFINITIONS,
        )
    )
    return action_client, judge_client, agent


def _dom_scored_results(agent: Any, raw: Any, args: argparse.Namespace):
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
    return rubric_result, outcome_result, process_pass, score


def _dom_result(
    args, task_data, preflight, rubric_result, outcome_result, process_pass, score,
    agent, frozen, action_client, judge_client, started, raw,
) -> dict[str, Any]:
    fields = ungraded_result(raw["ungraded_error"]) if "ungraded_error" in raw else {
        "status": "complete",
        "score": score,
        "rubric_score": rubric_result.score,
        "rubric_total_max_points": rubric_result.total_max_points,
        "rubric_total_earned_points": rubric_result.total_earned_points,
        "rubric_is_success": process_pass,
        "outcome": outcome_result.model_dump(mode="json"),
    }
    return {
        "task_id": task_data["id"],
        "verifier": "dom_model",
        "evidence_mode": "dom_model",
        **fields,
        "scoring_prompt_version": SCORING_PROMPT_VERSION,
        "success_criterion": args.success,
        "preflight": preflight,
        **rubric_receipt(path=str(frozen.path), sha256=frozen.sha256, rubric=frozen.precomputed_rubric),
        "rubric_generation_calls": 0,
        "dom_model_evidence_audit": getattr(agent, "evidence_audit", {}),
        "citation_checks": getattr(agent, "evidence_audit", {}).get("citation_checks"),
        "evaluation_context": task_data.get("evaluation_context"),
        "validity_date": agent.config.validity_date,
        "token_usage": {
            "judge": usage_dict(judge_client),
            "action_judge": usage_dict(action_client),
        },
        "call_metrics": {
            "judge": call_metrics(judge_client),
            "action_judge": call_metrics(action_client),
            "rubric_generation_calls": 0,
        },
        "intermediate_mm_rubric_steps": raw.get("intermediate_mm_rubric_steps"),
        "duration_sec": round(time.time() - started, 3),
    }


def preflight_dom_model_task(
    task_dir: Path, *, rubric_file: str | Path, generation_metrics: str | Path
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    package = dom_source_receipt()
    task, task_id, frozen = _dom_task_binding(task_dir, rubric_file)
    metrics = _dom_generation_metrics(generation_metrics, task_id, frozen)
    trajectory, actions, states, alignment = _dom_trajectory(task_dir, task_id, task)
    _validate_dom_answer(task_dir)
    _validate_dom_task_files(task_dir, states)
    receipt = _dom_preflight_receipt(
        task_id, actions, states, alignment, frozen, generation_metrics, metrics, package,
    )
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
    frozen = load_frozen_rubric(args.rubric_file, expected_task_id=task_data["id"])
    effective = native_stage_settings(args, "dom_model", rubric_hash=frozen.sha256)
    guard_result_settings(Path(args.output) / "result.json", effective, label="DOM verifier resume")
    action_client, judge_client, agent = _dom_agent(args, task_data, eval_config)
    datapoint = create_datapoint(task_data, trajectory)
    agent_input = MMRubricAgent._extract_input_from_datapoint(
        datapoint, evidence_dir=str(task_dir), redo_eval=args.redo_eval
    )
    try:
        raw = asyncio.run(agent._generate_reply(agent_input))
        rubric_result, outcome_result, process_pass, score = _dom_scored_results(agent, raw, args)
    except UngradedVerifierError as error:
        raw = {"ungraded_error": error}
        rubric_result = outcome_result = process_pass = score = None
    frozen = load_frozen_rubric(args.rubric_file, expected_task_id=task_data["id"])
    result = _dom_result(
        args, task_data, preflight, rubric_result, outcome_result, process_pass, score,
        agent, frozen, action_client, judge_client, started, raw,
    )
    result["effective_settings"] = effective
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = write_json(output_dir / "result.json", result)
    result["result_path"] = os.path.relpath(output_path, Path(__file__).resolve().parents[3])
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, epilog="Invalid earned points exhaust validation as ungraded; model IDs and DOM citations are diagnostic records. Existing outputs require matching effective settings.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--rubric-file", required=True)
    parser.add_argument("--generation-metrics", required=True)
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--judge-model", default=native_judge_model())
    parser.add_argument("--action-model", default=native_judge_model())
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument("--max-evidence-per-criterion", type=int, default=5)
    # Keep the baseline evidence-analysis behavior. A positive value
    # drops low-relevance top-K states before analysis and would make the DOM
    # verifier structurally different from the fixed baseline.
    parser.add_argument("--min-relevance-threshold", type=int, default=0)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--dom-model-state-char-budget", type=int, default=350000)
    parser.add_argument("--success", choices=("outcome", "process", "both"), default="outcome")
    parser.add_argument("--redo-eval", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.judge_model != native_judge_model() or args.action_model != native_judge_model():
        parser.error(f"verifier models are pinned to {native_judge_model()} for the selected native judge profile")
    return args


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    print(json.dumps(run(parse_args(argv)), ensure_ascii=False, indent=2, default=str))



if __name__ == "__main__":
    main()
