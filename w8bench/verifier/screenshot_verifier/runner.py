"""Controlled standalone runner for the screenshot verifier."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from .adapter import create_datapoint, normalize_all_screenshot_evidence
from w8bench.verifier.clients.retry import GracefulRetryClient
from ..instrumentation import call_metrics, instrument_client_calls, usage_dict
from .rubric_agent import MMRubricAgent, MMRubricAgentConfig
from ..models import MMRubricOutcomeResult, MMRubricResult
from .models import Trajectory
from ..rubric_scoring import FARA_ACTION_DEFINITIONS, UngradedVerifierError, ungraded_result
from .prompts import SCORING_PROMPT_VERSION
from .preflight import preflight_screenshot_task
from ..common import native_judge_model, load_frozen_rubric, require_matching_embedded_rubric, rubric_receipt
from w8bench.settings import native_stage_settings, guard_result_settings


logger = logging.getLogger("screenshot_verifier")


def _read_task_data(task_dir: Path) -> dict[str, Any]:
    path = task_dir / "task_data.json"
    if not path.is_file():
        raise ValueError(f"Missing task_data.json: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError("task_data.json list must contain exactly one object")
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError("task_data.json must contain an object or one-item list")
    normalized = dict(value)
    normalized["id"] = str(value.get("id") or value.get("task_id") or task_dir.name)
    normalized["question"] = str(
        value.get("question") or value.get("confirmed_task") or ""
    )
    normalized["init_url"] = str(value.get("init_url") or value.get("website") or "")
    return normalized


def _bind_all_screenshot_evidence(
    agent_input: dict[str, Any], screenshots: list[str], action_count: int,
    evaluation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind all N+1 states to the unchanged screenshot evidence loader."""
    expected = action_count + 1
    if not evaluation_context and len(screenshots) != expected:
        raise ValueError(
            f"Expected {expected} screenshot evidence states, found {len(screenshots)}"
        )
    bound = dict(agent_input)
    if evaluation_context:
        import re
        expected_ids = evaluation_context["expected_state_ids"]
        gaps = evaluation_context.get("format_gaps", {}).get("screenshot", [])
        actual = [int(re.search(r"(\d+)\.png$", path).group(1)) for path in screenshots]
        if len(expected_ids) != expected or actual != [index for index in expected_ids if index not in gaps]:
            raise ValueError("Screenshot evidence differs from full recorded chronology")
        bound["actions_list"] = [{"id": index, "state_id": index, "screenshot": path} for index, path in zip(actual, screenshots)]
        return bound
    bound["actions_list"] = [
        {"id": index, "screenshot": screenshot}
        for index, screenshot in enumerate(screenshots, start=1)
    ]
    return bound


def _task_inputs(args):
    task_dir = Path(args.input).resolve(strict=True)
    task_data = _read_task_data(task_dir)
    task_id = str(task_data.get("id") or task_dir.name)
    frozen = load_frozen_rubric(args.rubric_file, expected_task_id=task_id)
    task_data = require_matching_embedded_rubric(task_data, frozen)
    preflight = preflight_screenshot_task(task_dir)
    return task_dir, task_data, task_id, frozen, preflight


def _evaluation_agent(args, task_data):
    eval_config = Path(args.eval_config).resolve(strict=True)
    action_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.action_model, evidence_mode='screenshot_verifier'
    )
    judge_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.judge_model, evidence_mode='screenshot_verifier'
    )
    instrument_client_calls(action_client)
    instrument_client_calls(judge_client)
    agent = MMRubricAgent(
        config=MMRubricAgentConfig(
            action_client=action_client,
            validity_date=(task_data.get("evaluation_context") or {}).get("validity_date") or datetime.now(timezone.utc).date().isoformat(),
            judge_client=judge_client,
            max_images_per_criterion=args.max_images_per_criterion,
            majority_vote_instances=args.majority_vote_instances,
            redo_eval=args.redo_eval,
            rubric_score_threshold=args.rubric_threshold,
            action_definitions=FARA_ACTION_DEFINITIONS,
        )
    )
    return agent, action_client, judge_client


def _evaluation_input(args, task_dir, task_data, preflight):
    trajectory = Trajectory.from_folder(task_dir)
    if trajectory is None:
        raise ValueError(f"Unable to load trajectory: {task_dir}")
    datapoint = create_datapoint(task_data, trajectory)
    agent_input = MMRubricAgent._extract_input_from_datapoint(
        datapoint, evidence_dir=str(task_dir), redo_eval=args.redo_eval
    )
    # Evidence selection receives every 0..N browser state. Action history and
    # step metadata above still contain only the N actions actually performed.
    agent_input = _bind_all_screenshot_evidence(
        agent_input, normalize_all_screenshot_evidence(trajectory), preflight["actions"],
        evaluation_context=task_data.get("evaluation_context")
    )
    return agent_input


def _evaluation_fields(args, task_id, agent, raw):
    if not isinstance(raw, dict) or raw.get("error"):
        raise RuntimeError(f"Rubric agent failed: {raw.get('error') if isinstance(raw, dict) else raw}")
    wrapped = agent._wrap_result(raw)
    rubric_result = next(item for item in wrapped if isinstance(item, MMRubricResult))
    outcome_result = next(
        item for item in wrapped if isinstance(item, MMRubricOutcomeResult)
    )
    outcome_pass = outcome_result.output_success is True
    process_pass = bool(rubric_result.rubric_is_success)
    if args.success == "process":
        score = int(process_pass)
    elif args.success == "both":
        score = int(process_pass and outcome_pass)
    else:
        score = int(outcome_pass)
    return {
        "status": "complete",
        "task_id": task_id,
        "verifier": "screenshot_verifier",
        "score": score,
        "success_criterion": args.success,
        "rubric_score": rubric_result.score,
        "rubric_total_max_points": rubric_result.total_max_points,
        "rubric_total_earned_points": rubric_result.total_earned_points,
        "rubric_is_success": process_pass,
        "outcome": outcome_result.model_dump(mode="json"),
    }


def _result_receipts(task_data, frozen, preflight, agent, action_client, judge_client, raw, started):
    return {
        "scoring_prompt_version": SCORING_PROMPT_VERSION,
        "preflight": preflight,
        **rubric_receipt(
            path=str(frozen.path),
            sha256=frozen.sha256,
            rubric=frozen.precomputed_rubric,
        ),
        "evaluation_context": task_data.get("evaluation_context"),
        "validity_date": agent.config.validity_date,
        "token_usage": {
            "judge": usage_dict(judge_client),
            "action_judge": usage_dict(action_client),
        },
        "call_metrics": {
            "judge": call_metrics(judge_client),
            "action_judge": call_metrics(action_client),
        },
        "intermediate_mm_rubric_steps": raw.get("intermediate_mm_rubric_steps"),
        "duration_sec": round(time.time() - started, 3),
    }


def _write_result(result, output):
    output_dir = Path(output).resolve()
    output_path = output_dir / "result.json"
    from ..batch import publication
    with publication():
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    result["result_path"] = os.path.relpath(output_path, Path(__file__).resolve().parents[3])
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    task_dir, task_data, task_id, frozen, preflight = _task_inputs(args)
    effective = native_stage_settings(args, "screenshot_verifier", rubric_hash=frozen.sha256)
    guard_result_settings(Path(args.output) / "result.json", effective, label="screenshot verifier resume")
    agent, action_client, judge_client = _evaluation_agent(args, task_data)
    agent_input = _evaluation_input(args, task_dir, task_data, preflight)
    try:
        raw = asyncio.run(agent._generate_reply(agent_input))
        result = _evaluation_fields(args, task_id, agent, raw)
    except UngradedVerifierError as error:
        raw = {}
        result = {"task_id": task_id, "verifier": "screenshot_verifier",
            "success_criterion": args.success, **ungraded_result(error)}
    result.update(_result_receipts(
        task_data, frozen, preflight, agent, action_client, judge_client, raw, started
    ))
    result["effective_settings"] = effective
    return _write_result(result, args.output)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, epilog="Invalid earned points exhaust validation as ungraded; returned model IDs are diagnostic records. Existing outputs require matching effective settings.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--rubric-file", required=True)
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--judge-model", default=native_judge_model())
    parser.add_argument("--action-model", default=native_judge_model(),
                        help="Action/validity judge model")
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument("--max-images-per-criterion", type=int, default=5)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--success", choices=("outcome", "process", "both"), default="outcome")
    parser.add_argument("--redo-eval", action="store_true")
    args = parser.parse_args(argv)
    if args.judge_model != native_judge_model() or args.action_model != native_judge_model():
        parser.error(f"verifier models are pinned to {native_judge_model()} for the selected native judge profile")
    return args


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    from ..batch import BatchPending, BatchCancelled
    try:
        print(json.dumps(run(parse_args(argv)), indent=2, default=str))
    except BatchPending:
        raise SystemExit(75)
    except BatchCancelled:
        raise SystemExit(130)



if __name__ == "__main__":
    main()
