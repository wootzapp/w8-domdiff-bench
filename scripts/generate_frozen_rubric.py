#!/usr/bin/env python3
"""Phase A: generate/import and freeze one rubric for both staged modalities.

Offline by default. ``--execute`` is required for all writes and, unless
``--import-rubric`` is supplied, explicitly authorizes paid Microsoft rubric calls.
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
    ensure_under,
    load_canonical_rubric,
    load_env_file,
    load_one_task,
    require_openai_key,
    task_init_url,
    task_instruction,
    validate_endpoint_configs,
    validate_rubric,
    write_json,
)
from .package_manifests import require_local_packages
from .validate_inputs import dataset_only_preflight, validate_pair


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config"


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

        async def attempt(*args: Any, _original=original_endpoint_create, **kwargs: Any) -> Any:
            metrics["api_attempts"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = attempt
    return metrics


def _sidecar_payload(task_path: Path, rubric: dict[str, Any]) -> object:
    original = json.loads(task_path.read_text(encoding="utf-8"))
    task = load_one_task(task_path)
    task["precomputed_rubric"] = rubric
    return [task] if isinstance(original, list) else task


def _require_isolated_staging_root(path: str | Path) -> Path:
    staged = Path(path).resolve(strict=True)
    for protected in (ROOT.parent / "benchmarks", ROOT.parent / "ms-paper-execution"):
        protected = protected.resolve(strict=True)
        if staged == protected or protected in staged.parents:
            raise ValueError(
                f"Phase A staging root may not be inside protected source tree: {staged}"
            )
    return staged


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot-task", required=True)
    parser.add_argument("--dom-task", required=True)
    parser.add_argument("--rubric-file")
    parser.add_argument("--metrics-file")
    parser.add_argument("--import-rubric", help="Read-only existing canonical rubric to validate/import")
    parser.add_argument("--staged-root", default=str(ROOT / "data"))
    parser.add_argument("--eval-config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packages = require_local_packages()
    staged_root = _require_isolated_staging_root(args.staged_root)
    screenshot_root = ensure_under(Path(args.screenshot_task).resolve(strict=True), staged_root, label="screenshot task")
    dom_root = ensure_under(Path(args.dom_task).resolve(strict=True), staged_root, label="DOM-model task")
    if screenshot_root.name != dom_root.name:
        raise ValueError("Paired task folder aliases must match")
    dataset_receipt = dataset_only_preflight(screenshot_root, dom_root)
    endpoint_receipt = validate_endpoint_configs(args.eval_config)
    rubric_path = ensure_under(
        Path(args.rubric_file or ROOT / "rubrics" / f"{screenshot_root.name}.json"),
        ROOT,
        label="rubric output",
    )
    metrics_path = ensure_under(
        Path(args.metrics_file or ROOT / "rubrics" / f"{screenshot_root.name}_generation_metrics.json"),
        ROOT,
        label="generation metrics output",
    )
    targets = [
        rubric_path,
        metrics_path,
        screenshot_root / "task_data_with_canonical_rubric.json",
        dom_root / "task_data_with_canonical_rubric.json",
    ]
    existing = [str(path) for path in targets if path.exists()]
    if existing and not args.overwrite:
        raise ValueError(f"Refusing to overwrite Phase A artifacts without --overwrite: {existing}")
    preflight = {
        "status": "ready",
        "phase": "A",
        "paid_calls_authorized": bool(args.execute and not args.import_rubric),
        "writes_authorized": bool(args.execute),
        "dataset": dataset_receipt,
        "endpoint_config": endpoint_receipt,
        "rubric_output": str(rubric_path),
        "metrics_output": str(metrics_path),
        "sidecar_outputs": [str(targets[2]), str(targets[3])],
        "models": [CANONICAL_JUDGE_MODEL, CANONICAL_ACTION_MODEL],
        "verifier_packages": packages,
        "import_source": str(Path(args.import_rubric).resolve(strict=True)) if args.import_rubric else None,
    }
    if not args.execute:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return 0

    gpt_calls = {"logical_calls": 0, "api_attempts": 0}
    o4_calls = {"logical_calls": 0, "api_attempts": 0}
    gpt_usage = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    o4_usage = dict(gpt_usage)
    origin = "microsoft_generate_rubric"
    if args.import_rubric:
        imported = load_canonical_rubric(
            args.import_rubric, expected_task_id=dataset_receipt["task_id"]
        )
        rubric = imported.rubric
        origin = "validated_import"
    else:
        load_env_file(args.env_file)
        require_openai_key()
        logger = logging.getLogger("generate_frozen_rubric")
        gpt5_client = GracefulRetryClient.from_path(
            path=args.eval_config, logger=logger, eval_model=CANONICAL_JUDGE_MODEL
        )
        o4mini_client = GracefulRetryClient.from_path(
            path=args.eval_config, logger=logger, eval_model=CANONICAL_ACTION_MODEL
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
        rubric = asyncio.run(
            agent._generate_rubric(
                task_instruction(task),
                MMRubricAgent._get_init_url_context(task_init_url(task)),
            )
        )
        gpt_usage = _usage(gpt5_client)
        o4_usage = _usage(o4mini_client)

    denominator = validate_rubric(rubric)
    rubric_sha = canonical_sha256(rubric)
    canonical_payload = {"task_id": dataset_receipt["task_id"], "precomputed_rubric": rubric}
    write_json(rubric_path, canonical_payload)
    write_json(
        screenshot_root / "task_data_with_canonical_rubric.json",
        _sidecar_payload(screenshot_root / "task_data.json", rubric),
    )
    write_json(
        dom_root / "task_data_with_canonical_rubric.json",
        _sidecar_payload(dom_root / "task_data.json", rubric),
    )
    logical = gpt_calls["logical_calls"] + o4_calls["logical_calls"]
    attempts = gpt_calls["api_attempts"] + o4_calls["api_attempts"]
    usage = {
        CANONICAL_JUDGE_MODEL: gpt_usage,
        CANONICAL_ACTION_MODEL: o4_usage,
        "combined": {
            key: gpt_usage[key] + o4_usage[key]
            for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens")
        },
    }
    metrics = {
        "phase": "A",
        "origin": origin,
        "task_id": dataset_receipt["task_id"],
        "frozen_rubric_sha256": rubric_sha,
        "criterion_count": len(rubric["items"]),
        "criterion_denominator": denominator,
        "criteria": [item["criterion"] for item in rubric["items"]],
        "maximum_points": [float(item["max_points"]) for item in rubric["items"]],
        "rubric_generation_calls": logical,
        "api_attempts": attempts,
        "retries": max(0, attempts - logical),
        "call_metrics": {
            CANONICAL_JUDGE_MODEL: {**gpt_calls, "retries": max(0, gpt_calls["api_attempts"] - gpt_calls["logical_calls"])},
            CANONICAL_ACTION_MODEL: {**o4_calls, "retries": max(0, o4_calls["api_attempts"] - o4_calls["logical_calls"])},
        },
        "token_usage": usage,
        "preflight": preflight,
        "note": "Phase A usage is separate; reasoning tokens are a subset of completion tokens.",
    }
    write_json(metrics_path, metrics)
    final_preflight = validate_pair(
        screenshot_root,
        dom_root,
        rubric_file=rubric_path,
        generation_metrics=metrics_path,
        eval_config=args.eval_config,
        require_sidecars=True,
    )
    metrics["final_preflight"] = final_preflight
    write_json(metrics_path, metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
