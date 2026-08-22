#!/usr/bin/env python3
"""Generate and freeze one canonical rubric for both benchmark modalities.

The command is offline by default. Pass ``--execute`` to authorize the paid
GPT-5.2/o4-mini rubric generation and dependency-check calls.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from microsoft_verifier.clients.graceful_client import GracefulRetryClient
from microsoft_verifier.rubric_agent import MMRubricAgent, MMRubricAgentConfig
from microsoft_verifier.utils.action_schema import FARA_ACTION_DEFINITIONS

from .common import (
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
    canonical_sha256,
    load_env_file,
    load_one_task,
    require_openai_key,
    task_id,
    task_init_url,
    task_instruction,
    validate_endpoint_configs,
    validate_rubric,
    write_json,
)
from .validate_inputs import (
    _compare_semantic_actions,
    _load_answer,
    _ordered_dom_diffs,
    _ordered_screenshots,
    _parse_actions,
    validate_pair,
)


ROOT = Path(__file__).resolve().parents[1]


def _usage(client: Any) -> dict[str, int]:
    prompt = completion = reasoning = 0
    for endpoint in getattr(client, "_clients", []):
        value = endpoint.total_usage()
        prompt += int(getattr(value, "prompt_tokens", 0) or 0)
        completion += int(getattr(value, "completion_tokens", 0) or 0)
        reasoning += int(getattr(value, "reasoning_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "total_tokens": prompt + completion,
    }


def _instrument(client: Any) -> dict[str, int]:
    metrics = {"logical_calls": 0, "api_attempts": 0}
    original_create = client.create

    async def logical(*args: Any, **kwargs: Any) -> Any:
        metrics["logical_calls"] += 1
        return await original_create(*args, **kwargs)

    client.create = logical
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def attempt(
            *args: Any,
            _original: Any = original_endpoint_create,
            **kwargs: Any,
        ) -> Any:
            metrics["api_attempts"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = attempt
    return metrics


def _dataset_only_preflight(screenshot_root: Path, dom_root: Path) -> dict[str, Any]:
    screenshot_data = load_one_task(screenshot_root / "task_data.json")
    dom_data = load_one_task(dom_root / "task_data.json")
    if screenshot_data != dom_data:
        raise ValueError("task_data.json differs between screenshot and DOM tasks")
    internal_id = task_id(screenshot_data)
    if not internal_id or not task_instruction(screenshot_data):
        raise ValueError("Task data must contain task ID and instruction")
    screenshot_actions = _parse_actions(screenshot_root / "web_surfer.log", mode="screenshot")
    dom_actions = _parse_actions(dom_root / "web_surfer.log", mode="dom")
    _compare_semantic_actions(screenshot_actions, dom_actions)
    screenshots = _ordered_screenshots(screenshot_root)
    diffs = _ordered_dom_diffs(dom_root, len(dom_actions))
    if len(screenshots) != len(screenshot_actions) + 1:
        raise ValueError("Screenshot task must contain intentional N+1 states")
    screenshot_answer = _load_answer(screenshot_root / "final_answer.json")
    dom_answer = _load_answer(dom_root / "final_answer.json")
    for field in ("final_answer", "is_aborted"):
        if screenshot_answer.get(field) != dom_answer.get(field):
            raise ValueError(f"Final-answer field differs: {field}")
    if "screenshots" in dom_answer or dom_answer.get("token_usage") != {}:
        raise ValueError("DOM final answer violates the DOM-only contract")
    return {
        "task_id": internal_id,
        "task_alias": screenshot_root.name,
        "actions": len(screenshot_actions),
        "screenshots": len(screenshots),
        "dom_text_frames": len(diffs),
    }


def _sidecar_payload(task_path: Path, rubric: dict[str, Any]) -> object:
    original = json.loads(task_path.read_text(encoding="utf-8"))
    task = load_one_task(task_path)
    task["precomputed_rubric"] = rubric
    return [task] if isinstance(original, list) else task


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot-task", required=True)
    parser.add_argument("--dom-task", required=True)
    parser.add_argument("--rubric-file")
    parser.add_argument("--metrics-file")
    parser.add_argument(
        "--eval-config",
        default=str(ROOT / "config/endpoints/openai/canonical"),
    )
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    screenshot_root = Path(args.screenshot_task).resolve(strict=True)
    dom_root = Path(args.dom_task).resolve(strict=True)
    if screenshot_root.name != dom_root.name:
        raise ValueError("Paired task folder aliases must match")
    dataset_receipt = _dataset_only_preflight(screenshot_root, dom_root)
    endpoint_receipt = validate_endpoint_configs(args.eval_config)
    rubric_path = Path(
        args.rubric_file or ROOT / "rubrics" / f"{screenshot_root.name}.json"
    ).resolve()
    metrics_path = Path(
        args.metrics_file or ROOT / "rubrics" / f"{screenshot_root.name}_generation_metrics.json"
    ).resolve()
    targets = [
        rubric_path,
        metrics_path,
        screenshot_root / "task_data_with_canonical_rubric.json",
        dom_root / "task_data_with_canonical_rubric.json",
    ]
    existing = [str(path) for path in targets if path.exists()]
    if existing and not args.overwrite:
        raise ValueError(
            "Refusing to overwrite existing frozen-rubric artifacts without "
            f"--overwrite: {existing}"
        )
    preflight = {
        "status": "ready",
        "paid_calls_authorized": bool(args.execute),
        "dataset": dataset_receipt,
        "endpoint_config": endpoint_receipt,
        "rubric_output": str(rubric_path),
        "metrics_output": str(metrics_path),
        "models": [CANONICAL_JUDGE_MODEL, CANONICAL_ACTION_MODEL],
    }
    if not args.execute:
        print(json.dumps(preflight, indent=2))
        return 0

    load_env_file(args.env_file)
    require_openai_key()
    logger = logging.getLogger("generate_frozen_rubric")
    gpt5_client = GracefulRetryClient.from_path(
        path=args.eval_config,
        logger=logger,
        eval_model=CANONICAL_JUDGE_MODEL,
    )
    o4mini_client = GracefulRetryClient.from_path(
        path=args.eval_config,
        logger=logger,
        eval_model=CANONICAL_ACTION_MODEL,
    )
    gpt_calls = _instrument(gpt5_client)
    o4_calls = _instrument(o4mini_client)
    agent = MMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=o4mini_client,
            gpt5_client=gpt5_client,
            action_definitions=FARA_ACTION_DEFINITIONS,
            majority_vote_instances=1,
            redo_eval=True,
        )
    )
    task = load_one_task(screenshot_root / "task_data.json")
    instruction = task_instruction(task)
    init_url = task_init_url(task)
    rubric = asyncio.run(
        agent._generate_rubric(
            instruction,
            MMRubricAgent._get_init_url_context(init_url),
        )
    )
    denominator = validate_rubric(rubric)
    rubric_sha256 = canonical_sha256(rubric)
    write_json(
        rubric_path,
        {"task_id": dataset_receipt["task_id"], "precomputed_rubric": rubric},
    )
    write_json(
        screenshot_root / "task_data_with_canonical_rubric.json",
        _sidecar_payload(screenshot_root / "task_data.json", rubric),
    )
    write_json(
        dom_root / "task_data_with_canonical_rubric.json",
        _sidecar_payload(dom_root / "task_data.json", rubric),
    )
    final_preflight = validate_pair(
        screenshot_root,
        dom_root,
        rubric_file=rubric_path,
        eval_config=args.eval_config,
    )
    usage = {
        CANONICAL_JUDGE_MODEL: _usage(gpt5_client),
        CANONICAL_ACTION_MODEL: _usage(o4mini_client),
    }
    usage["combined"] = {
        key: sum(usage[model][key] for model in (CANONICAL_JUDGE_MODEL, CANONICAL_ACTION_MODEL))
        for key in usage[CANONICAL_JUDGE_MODEL]
    }
    logical = gpt_calls["logical_calls"] + o4_calls["logical_calls"]
    attempts = gpt_calls["api_attempts"] + o4_calls["api_attempts"]
    metrics = {
        "task_id": dataset_receipt["task_id"],
        "frozen_rubric_sha256": rubric_sha256,
        "criterion_count": len(rubric["items"]),
        "criterion_denominator": denominator,
        "criteria": [item["criterion"] for item in rubric["items"]],
        "rubric_generation_calls": logical,
        "api_attempts": attempts,
        "retries": attempts - logical,
        "call_metrics": {
            CANONICAL_JUDGE_MODEL: gpt_calls,
            CANONICAL_ACTION_MODEL: o4_calls,
        },
        "token_usage": usage,
        "preflight": final_preflight,
        "note": "Reasoning tokens are a subset of completion tokens.",
    }
    write_json(metrics_path, metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
