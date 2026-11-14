"""Controlled standalone runner for the screenshot verifier."""

from __future__ import annotations

import inspect

import argparse
import asyncio
import json
import logging
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from .adapter import create_datapoint, normalize_all_screenshot_evidence
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


def _instrument_client_calls(client: Any) -> None:
    if hasattr(client, "_benchmark_call_metrics"):
        return
    metrics = {"logical_calls": 0, "endpoint_calls": 0}
    original_create = client.create

    async def counted_logical_create(*args: Any, **kwargs: Any):
        metrics["logical_calls"] += 1
        stage_path = []
        frame = inspect.currentframe()
        try:
            while frame is not None:
                module = frame.f_globals.get("__name__", "")
                if (module.endswith(".rubric_agent") or module.endswith(".dom_model_agent")) and frame.f_code.co_name != "_call_llm":
                    stage_path.append(f"{module}.{frame.f_code.co_name}")
                frame = frame.f_back
        finally:
            del frame
        stage_tokens = [(endpoint, endpoint._logical_stage.set(tuple(stage_path)))
            for endpoint in getattr(client, "_clients", []) if hasattr(endpoint, "_logical_stage")]
        try:
            return await original_create(*args, **kwargs)
        finally:
            for endpoint, token in stage_tokens:
                endpoint._logical_stage.reset(token)

    client.create = counted_logical_create
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def counted_endpoint_create(
            *args: Any, _original=original_endpoint_create, **kwargs: Any
        ):
            metrics["endpoint_calls"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = counted_endpoint_create
    client._benchmark_call_metrics = metrics


def _call_metrics(client: Any) -> dict[str, Any]:
    metrics = getattr(client, "_benchmark_call_metrics", {})
    logical = int(metrics.get("logical_calls", 0))
    endpoint_calls = int(metrics.get("endpoint_calls", 0))
    endpoints = list(getattr(client, "_clients", []))
    attempts = sum(int(getattr(endpoint, "_http_attempts", 0)) for endpoint in endpoints)
    complete = bool(endpoints) and all(getattr(endpoint, "_http_attempts_observed", False) for endpoint in endpoints)
    records = [dict(record) for endpoint in endpoints for record in getattr(endpoint, "_call_records", [])]
    return {
        "logical_calls": logical, "endpoint_calls": endpoint_calls,
        "api_attempts": attempts, "http_attempts": attempts,
        "http_attempts_complete": complete,
        "retries": max(0, attempts - logical) if complete else None,
        "endpoint_retries": max(0, endpoint_calls - logical),
        "sdk_http_retries": max(0, attempts - endpoint_calls) if complete else None,
        "configured_models": sorted({record["configured_model"] for record in records}),
        "returned_models": sorted({record["returned_model"] for record in records if record.get("returned_model")}),
        "calls": records,
    }


def _usage_dict(client: Any) -> dict[str, Any]:
    prompt = completion = 0
    records = []
    for inner in getattr(client, "_clients", []):
        usage = inner.total_usage()
        prompt += int(getattr(usage, "prompt_tokens", 0))
        completion += int(getattr(usage, "completion_tokens", 0))
        records.extend(getattr(inner, "_call_records", []))
    if records:
        inputs = [record["input_tokens"] for record in records if record.get("input_tokens") is not None]
        outputs = [record["output_tokens"] for record in records if record.get("output_tokens") is not None]
        prompt = sum(inputs) if inputs else None
        completion = sum(outputs) if outputs else None
    writes = [record["cache_write_input_tokens"] for record in records if record.get("cache_write_input_tokens") is not None]
    reads = [record["cached_input_tokens"] for record in records if record.get("cached_input_tokens") is not None]
    thinking = [record["reasoning_tokens"] for record in records if record.get("reasoning_tokens") is not None]
    return {
        "prompt_tokens": prompt, "input_tokens": prompt,
        "completion_tokens": completion, "output_tokens": completion,
        "cached_input_tokens": sum(reads) if reads else None,
        "cache_write_input_tokens": sum(writes) if writes else None,
        "reasoning_tokens": sum(thinking) if thinking else None,
        "total_tokens": (prompt or 0) + (completion or 0) if prompt is not None or completion is not None else None,
        "usage_known_calls": {key: sum(record.get("usage_fields_reported", {}).get(key, False) for record in records)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens")},
        "cached_input_usage_reported_calls": len(reads), "reasoning_usage_reported_calls": len(thinking),
        "calls_without_reported_usage": sum(not record.get("usage_reported", False) for record in records),
        "cache_write_usage_reported_calls": len(writes),
    }



def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


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


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    task_dir = Path(args.input).resolve(strict=True)
    task_data = _read_task_data(task_dir)
    task_id = str(task_data.get("id") or task_dir.name)
    frozen = load_frozen_rubric(args.rubric_file, expected_task_id=task_id)
    task_data = require_matching_embedded_rubric(task_data, frozen)
    preflight = preflight_screenshot_task(task_dir)

    eval_config = Path(args.eval_config).resolve(strict=True)
    action_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.action_model
    )
    gpt5_client = GracefulRetryClient.from_path(
        path=str(eval_config), logger=logger, eval_model=args.judge_model
    )
    _instrument_client_calls(action_client)
    _instrument_client_calls(gpt5_client)
    agent = MMRubricAgent(
        config=MMRubricAgentConfig(
            action_client=action_client,
            validity_date=(task_data.get("evaluation_context") or {}).get("validity_date") or datetime.now(timezone.utc).date().isoformat(),
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
    # Evidence selection receives every 0..N browser state. Action history and
    # step metadata above still contain only the N actions actually performed.
    agent_input = _bind_all_screenshot_evidence(
        agent_input, normalize_all_screenshot_evidence(trajectory), preflight["actions"],
        evaluation_context=task_data.get("evaluation_context")
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
        "verifier": "screenshot_verifier",
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
        "evaluation_context": task_data.get("evaluation_context"),
        "validity_date": agent.config.validity_date,
        "token_usage": {
            "judge": _usage_dict(gpt5_client),
            "action_judge": _usage_dict(action_client),
        },
        "call_metrics": {
            "judge": _call_metrics(gpt5_client),
            "action_judge": _call_metrics(action_client),
        },
        "intermediate_mm_rubric_steps": raw.get("intermediate_mm_rubric_steps"),
        "duration_sec": round(time.time() - started, 3),
    }
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "result.json"
    output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    result["result_path"] = os.path.relpath(output_path, Path(__file__).resolve().parents[3])
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--rubric-file", required=True)
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--action-model", default="gpt-5.6-terra",
                        help="Action/validity judge model")
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument("--max-images-per-criterion", type=int, default=5)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--success", choices=("outcome", "process", "both"), default="outcome")
    parser.add_argument("--redo-eval", action="store_true")
    args = parser.parse_args(argv)
    if args.judge_model != "gpt-5.2" or args.action_model != "gpt-5.6-terra":
        parser.error("verifier models are pinned to judge gpt-5.2 and action/validity gpt-5.6-terra")
    return args


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    print(json.dumps(run(parse_args(argv)), indent=2, default=str))


if __name__ == "__main__":
    main()
