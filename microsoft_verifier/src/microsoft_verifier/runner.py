"""Controlled standalone runner for the Microsoft screenshot verifier."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .adapter import create_datapoint
from .clients.graceful_client import GracefulRetryClient
from .rubric_agent import (
    MMRubricAgent,
    MMRubricAgentConfig,
    MMRubricOutcomeResult,
    MMRubricResult,
)
from .trajectory import Trajectory
from .utils.action_schema import FARA_ACTION_DEFINITIONS
from .utils.metrics import rubric_receipt
from .utils.preflight import preflight_screenshot_task
from .utils.rubric import load_frozen_rubric, require_matching_embedded_rubric


logger = logging.getLogger("microsoft_verifier")


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


def _usage_dict(client: GracefulRetryClient) -> dict[str, int]:
    prompt = completion = reasoning = 0
    for inner in getattr(client, "_clients", []):
        usage = inner.total_usage()
        prompt += int(getattr(usage, "prompt_tokens", 0))
        completion += int(getattr(usage, "completion_tokens", 0))
        reasoning += int(getattr(usage, "reasoning_tokens", 0))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "total_tokens": prompt + completion,
    }


def _instrument_client_calls(client: GracefulRetryClient) -> None:
    if hasattr(client, "_benchmark_call_metrics"):
        return
    metrics = {"logical_calls": 0, "api_attempts": 0}
    original_create = client.create

    async def counted_logical_create(*args: Any, **kwargs: Any):
        metrics["logical_calls"] += 1
        return await original_create(*args, **kwargs)

    client.create = counted_logical_create
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def counted_endpoint_create(
            *args: Any, _original=original_endpoint_create, **kwargs: Any
        ):
            metrics["api_attempts"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = counted_endpoint_create
    client._benchmark_call_metrics = metrics


def _call_metrics(client: GracefulRetryClient) -> dict[str, int]:
    metrics = getattr(client, "_benchmark_call_metrics", {})
    logical = int(metrics.get("logical_calls", 0))
    attempts = int(metrics.get("api_attempts", 0))
    return {
        "logical_calls": logical,
        "api_attempts": attempts,
        "retries": max(0, attempts - logical),
    }


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    task_dir = Path(args.input).resolve(strict=True)
    task_data = _read_task_data(task_dir)
    task_id = str(task_data.get("id") or task_dir.name)
    frozen = load_frozen_rubric(args.rubric_file, expected_task_id=task_id)
    task_data = require_matching_embedded_rubric(task_data, frozen)
    preflight = preflight_screenshot_task(task_dir)

    eval_config = Path(args.eval_config).resolve(strict=True)
    o4mini_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.o4mini_model
    )
    gpt5_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.judge_model
    )
    _instrument_client_calls(o4mini_client)
    _instrument_client_calls(gpt5_client)
    agent = MMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=o4mini_client,
            gpt5_client=gpt5_client,
            max_images_per_criterion=args.max_images_per_criterion,
            majority_vote_instances=args.majority_vote_instances,
            redo_eval=args.redo_eval,
            rubric_score_threshold=args.rubric_threshold,
            action_definitions=FARA_ACTION_DEFINITIONS,
        )
    )
    trajectory = Trajectory.from_folder(task_dir)
    if trajectory is None:
        raise ValueError(f"Unable to load trajectory: {task_dir}")
    datapoint = create_datapoint(task_data, trajectory)
    agent_input = MMRubricAgent._extract_input_from_datapoint(
        datapoint, screenshots_dir=str(task_dir), redo_eval=args.redo_eval
    )
    raw = asyncio.run(agent._generate_reply(agent_input))
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
    result = {
        "task_id": task_id,
        "verifier": "microsoft_verifier",
        "score": score,
        "success_criterion": args.success,
        "rubric_score": rubric_result.score,
        "rubric_total_max_points": rubric_result.total_max_points,
        "rubric_total_earned_points": rubric_result.total_earned_points,
        "rubric_is_success": process_pass,
        "outcome": _jsonable(outcome_result),
        "preflight": preflight,
        **rubric_receipt(
            path=str(frozen.path),
            sha256=frozen.sha256,
            rubric=frozen.precomputed_rubric,
        ),
        "token_usage": {
            "judge": _usage_dict(gpt5_client),
            "action_judge": _usage_dict(o4mini_client),
        },
        "call_metrics": {
            "judge": _call_metrics(gpt5_client),
            "action_judge": _call_metrics(o4mini_client),
        },
        "intermediate_mm_rubric_steps": raw.get("intermediate_mm_rubric_steps"),
        "duration_sec": round(time.time() - started, 3),
    }
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "result.json"
    output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    result["result_path"] = str(output_path)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--rubric-file", required=True)
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--judge-model", default="gpt-5")
    parser.add_argument("--o4mini-model", default="o4-mini")
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument("--max-images-per-criterion", type=int, default=5)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--success", choices=("outcome", "process", "both"), default="outcome")
    parser.add_argument("--redo-eval", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    print(json.dumps(run(parse_args(argv)), indent=2, default=str))


if __name__ == "__main__":
    main()
