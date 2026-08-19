#!/usr/bin/env python3
"""Run the isolated summary-S3 verifier over refined ``dom_diffN.txt`` files.

All trajectories are preflighted before judge clients are initialized. This
runner never imports the current DOM-text compactor, retrieval, prompts, cap,
or agent modules.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any, List, Optional


_THIS = Path(__file__).resolve()
for _source_root in (_THIS.parent.parent / "src", _THIS.parent.parent.parent / "src"):
    _source = str(_source_root)
    if _source not in sys.path:
        sys.path.insert(0, _source)

from webeval.oai_clients.graceful_client import GracefulRetryClient
from webeval.rubric_agent import (
    MMRubricAgentConfig,
    MMRubricOutcomeResult,
    MMRubricResult,
)
from webeval.rubric_agent.dom_diff_adapter import ordered_action_events
from webeval.rubric_agent.dom_diff_text_adapter import (
    preflight_dom_diff_text_bundle,
    semantic_action_definitions,
)
from webeval.rubric_agent.dom_diff_text_evidence import DOM_DIFF_TEXT_SCHEMA
from webeval.rubric_agent.dom_diff_text_summary_agent import (
    DOMDiffTextSummaryMMRubricAgent,
)
from webeval.rubric_agent.dom_diff_text_summary_projection import (
    COMPACT_DOM_DIFF_TEXT_SUMMARY_SCHEMA,
)


logger = logging.getLogger("verify_trajectories_dom_diff_text_summary")
VERIFIER_SCHEMA_VERSION = "mmrubric-dom-diff-text-summary-result/v1"
PROMPT_VERSION = "mmrubric-dom-diff-text-summary-prompts/v1"
EVIDENCE_FORMAT = "runner-dom-diff-text-summary"
REQUESTED_EVIDENCE_MODE = "dom_diff_text_summary"


def _load_task_data(trajectory_dir: Path) -> dict[str, Any]:
    path = trajectory_dir / "task_data.json"
    if not path.is_file():
        raise ValueError(f"Missing task_data.json: {trajectory_dir}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"task_data.json must contain exactly one task: {path}")
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError(f"task_data.json must be one object or one-item list: {path}")
    return value


def find_trajectory_dirs(input_dir: Path) -> List[Path]:
    def valid(path: Path) -> bool:
        return all(
            (path / name).is_file()
            for name in ("task_data.json", "web_surfer.log", "final_answer.json")
        )

    if valid(input_dir):
        return [input_dir]
    return [
        child
        for child in sorted(input_dir.iterdir())
        if child.is_dir() and valid(child)
    ]


def preflight_trajectory(trajectory_dir: Path, *, redo_eval: bool = False):
    task_data = _load_task_data(trajectory_dir)
    trajectory, input_dict, frames = preflight_dom_diff_text_bundle(
        trajectory_dir,
        task_data,
        redo_eval=redo_eval,
        require_frozen_rubric=True,
    )
    input_dict["requested_evidence_mode"] = REQUESTED_EVIDENCE_MODE
    return trajectory, task_data, input_dict, frames


def _usage_dict(client: Any) -> dict[str, int]:
    prompt = completion = reasoning = 0
    for endpoint in getattr(client, "_clients", [client]):
        getter = getattr(endpoint, "total_usage", None)
        if not callable(getter):
            continue
        usage = getter()
        prompt += int(getattr(usage, "prompt_tokens", 0) or 0)
        completion += int(getattr(usage, "completion_tokens", 0) or 0)
        reasoning += int(getattr(usage, "reasoning_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "total_tokens": prompt + completion,
    }


def _delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {key: after.get(key, 0) - before.get(key, 0) for key in after}


def _instrument_client_calls(client: Any) -> None:
    if hasattr(client, "_dom_text_summary_call_metrics"):
        return
    metrics = {"logical_calls": 0, "api_attempts": 0}
    original_create = client.create

    async def counted_create(*args: Any, **kwargs: Any):
        metrics["logical_calls"] += 1
        return await original_create(*args, **kwargs)

    client.create = counted_create
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def counted_endpoint_create(
            *args: Any, _original=original_endpoint_create, **kwargs: Any
        ):
            metrics["api_attempts"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = counted_endpoint_create
    client._dom_text_summary_call_metrics = metrics


def _call_metrics(client: Any) -> dict[str, int]:
    metrics = getattr(client, "_dom_text_summary_call_metrics", {})
    logical = int(metrics.get("logical_calls", 0))
    attempts = int(metrics.get("api_attempts", 0))
    return {
        "logical_calls": logical,
        "api_attempts": attempts,
        "retries": max(0, attempts - logical),
    }


def _source_digest(trajectory_dir: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        trajectory_dir.glob("dom_diff*.txt"),
        key=lambda path: int(path.stem.removeprefix("dom_diff")),
    )
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _rubric_digest(task_data: dict[str, Any]) -> str:
    rubric = task_data.get("precomputed_rubric")
    if isinstance(rubric, list) and len(rubric) == 1:
        rubric = rubric[0]
    return hashlib.sha256(
        json.dumps(
            rubric, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _identity(
    args: argparse.Namespace, trajectory_dir: Path
) -> tuple[str, dict[str, Any]]:
    task_data = _load_task_data(trajectory_dir)
    config = {
        "requested_evidence_mode": REQUESTED_EVIDENCE_MODE,
        "evidence_format": EVIDENCE_FORMAT,
        "evidence_schema_version": DOM_DIFF_TEXT_SCHEMA,
        "compact_schema_version": COMPACT_DOM_DIFF_TEXT_SUMMARY_SCHEMA,
        "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "judge_model": args.judge_model,
        "o4mini_model": args.o4mini_model,
        "rubric_threshold": args.rubric_threshold,
        "max_evidence_per_criterion": args.max_evidence_per_criterion,
        "mm_keypoint_score_threshold": args.mm_keypoint_score_threshold,
        "majority_vote_instances": args.majority_vote_instances,
        "success_criterion": args.success,
        "frame_token_budget": 1500,
        "relevance_prompt_cap_tokens": 16000,
        "analysis_prompt_cap_tokens": 24000,
        "max_record_chars": 600,
        "prompt_reserve_tokens": 64,
        "frozen_rubric_sha256": _rubric_digest(task_data),
        "source_text_sha256": _source_digest(trajectory_dir),
    }
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16], config


def _build_agent(args: argparse.Namespace) -> DOMDiffTextSummaryMMRubricAgent:
    worker_logger = logging.getLogger(
        "verify_trajectories_dom_diff_text_summary.worker"
    )
    o4mini_client = GracefulRetryClient.from_path(
        path=str(Path(args.eval_config).resolve()),
        logger=worker_logger,
        eval_model=args.o4mini_model,
    )
    gpt5_client = GracefulRetryClient.from_path(
        path=str(Path(args.eval_config).resolve()),
        logger=worker_logger,
        eval_model=args.judge_model,
    )
    for client in (o4mini_client, gpt5_client):
        client.timeout = args.request_timeout_seconds
        client.max_retries = args.max_api_retries
        _instrument_client_calls(client)
    return DOMDiffTextSummaryMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=o4mini_client,
            gpt5_client=gpt5_client,
            max_images_per_criterion=args.max_evidence_per_criterion,
            majority_vote_instances=args.majority_vote_instances,
            redo_eval=args.redo_eval,
            rubric_score_threshold=args.rubric_threshold,
            evidence_mode="dom",
            evidence_schema_version=DOM_DIFF_TEXT_SCHEMA,
            prompt_version=PROMPT_VERSION,
            verifier_schema_version=VERIFIER_SCHEMA_VERSION,
            dom_frame_char_budget=16000,
            dom_context_char_budget=48000,
            dom_top_k=None,
            action_definitions=semantic_action_definitions(),
            summary_mode="s3",
            summary_projection="compact",
            summary_relevance_mode="batched_llm",
            summary_analysis_mode="packed",
            summary_frame_token_budget=1500,
            summary_trajectory_token_budget=16000,
            summary_analysis_token_budget=24000,
            summary_max_record_chars=600,
            summary_judge_model=args.judge_model,
        )
    )


def _run_one(
    agent: DOMDiffTextSummaryMMRubricAgent,
    args: argparse.Namespace,
    trajectory_dir: Path,
) -> dict[str, Any]:
    started = time.time()
    output: dict[str, Any] = {
        "task_id": trajectory_dir.name,
        "traj_dir": str(trajectory_dir),
    }
    try:
        trajectory, _, input_dict, frames = preflight_trajectory(
            trajectory_dir, redo_eval=args.redo_eval
        )
        before_usage = {
            "judge": _usage_dict(agent._gpt5_client),
            "action_rubric": _usage_dict(agent._o4mini_client),
        }
        before_calls = {
            "judge": _call_metrics(agent._gpt5_client),
            "action_rubric": _call_metrics(agent._o4mini_client),
        }
        result = asyncio.run(agent._generate_reply(input_dict))
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError(f"Rubric agent failed: {result}")
        after_usage = {
            "judge": _usage_dict(agent._gpt5_client),
            "action_rubric": _usage_dict(agent._o4mini_client),
        }
        after_calls = {
            "judge": _call_metrics(agent._gpt5_client),
            "action_rubric": _call_metrics(agent._o4mini_client),
        }
        token_usage = {
            role: _delta(after_usage[role], before_usage[role]) for role in after_usage
        }
        call_metrics = {
            role: _delta(after_calls[role], before_calls[role]) for role in after_calls
        }
        token_usage["total"] = {
            key: sum(token_usage[role][key] for role in ("judge", "action_rubric"))
            for key in token_usage["judge"]
        }
        call_metrics["total"] = {
            key: sum(call_metrics[role][key] for role in ("judge", "action_rubric"))
            for key in call_metrics["judge"]
        }
        token_usage["solver_recorded"] = trajectory.token_usage
        wrapped = agent._wrap_result(result)
        rubric_result = next(
            item for item in wrapped if isinstance(item, MMRubricResult)
        )
        outcome_result = next(
            item for item in wrapped if isinstance(item, MMRubricOutcomeResult)
        )
        process_pass = bool(rubric_result.rubric_is_success)
        outcome_pass = outcome_result.output_success is True
        top_score = int(
            process_pass
            if args.success == "process"
            else process_pass and outcome_pass
            if args.success == "both"
            else outcome_pass
        )
        identity, verifier_config = _identity(args, trajectory_dir)
        payload = {
            "score": top_score,
            "requested_evidence_mode": REQUESTED_EVIDENCE_MODE,
            "evidence_format": EVIDENCE_FORMAT,
            "evidence_schema_version": DOM_DIFF_TEXT_SCHEMA,
            "compact_schema_version": COMPACT_DOM_DIFF_TEXT_SUMMARY_SCHEMA,
            "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "actions": len(ordered_action_events(trajectory)),
            "text_frames": len(frames),
            "frozen_rubric_sha256": input_dict["frozen_rubric_sha256"],
            "frozen_input_denominator": input_dict["frozen_input_denominator"],
            "final_denominator": rubric_result.total_max_points,
            "token_usage": token_usage,
            "call_metrics": call_metrics,
            "summary_runtime_metrics": agent.text_summary_runtime_metrics(),
            "verifier_config": verifier_config,
            "cache_identity": identity,
            "result": {
                "top_score": top_score,
                "rubric": {
                    "score": rubric_result.score,
                    "is_success": process_pass,
                    "total_max_points": rubric_result.total_max_points,
                    "total_earned_points": rubric_result.total_earned_points,
                    "items": result.get("items", []),
                },
                "outcome": {
                    "success": outcome_result.output_success,
                    "reasoning": outcome_result.reasoning,
                    "primary_intent": outcome_result.primary_intent,
                },
            },
        }
        score_path = (
            trajectory_dir
            / "scores"
            / f"mmrubric-dom-diff-text-summary-{identity}.json"
        )
        score_path.parent.mkdir(parents=True, exist_ok=True)
        score_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        output.update(
            status="ok",
            score_path=str(score_path),
            result=payload["result"],
            token_usage=token_usage,
        )
    except Exception as exc:
        output.update(
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
        logger.error("[%s] %s", trajectory_dir.name, output["error"])
    output["duration_sec"] = round(time.time() - started, 2)
    return output


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--o4mini-model", default="o4-mini")
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument(
        "--success", choices=("outcome", "process", "both"), default="outcome"
    )
    parser.add_argument("--max-evidence-per-criterion", type=int, default=5)
    parser.add_argument("--mm-keypoint-score-threshold", type=int, default=3)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-api-retries", type=int, default=2)
    parser.add_argument("--redo-eval", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args(argv)
    for name in (
        "max_evidence_per_criterion",
        "majority_vote_instances",
        "request_timeout_seconds",
        "max_api_retries",
    ):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    return args


def _write_report(path: Path, rows: List[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    input_dir = Path(args.input).resolve()
    eval_config = Path(args.eval_config).resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"--input is not a directory: {input_dir}")
    if not eval_config.exists():
        raise SystemExit(f"--eval-config does not exist: {eval_config}")
    trajectories = find_trajectory_dirs(input_dir)
    if args.limit is not None:
        trajectories = trajectories[: args.limit]
    if not trajectories:
        raise SystemExit(
            f"No refined DOM-diff text trajectories found under {input_dir}"
        )
    report = (
        Path(args.report).resolve()
        if args.report
        else input_dir / "verify_report_dom_diff_text_summary.jsonl"
    )
    preflight_errors = []
    for trajectory_dir in trajectories:
        try:
            preflight_trajectory(trajectory_dir, redo_eval=args.redo_eval)
        except Exception as exc:
            preflight_errors.append(
                {
                    "task_id": trajectory_dir.name,
                    "status": "input_validation_error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    if preflight_errors:
        _write_report(report, preflight_errors)
        raise SystemExit(
            f"Text-summary preflight failed for {len(preflight_errors)} trajectory(s); "
            f"no judge clients were initialized. See {report}"
        )
    agent = _build_agent(args)
    results = [_run_one(agent, args, path) for path in trajectories]
    _write_report(report, results)
    ok = sum(row.get("status") == "ok" for row in results)
    logger.info("Text-summary verification complete: %s/%s succeeded", ok, len(results))
    logger.info("Report: %s", report)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
