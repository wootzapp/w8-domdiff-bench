#!/usr/bin/env python3
"""Run Universal Verifier using action-aligned DOM-diff summaries only.

The runner loads task data, ``web_surfer.log``, one final-answer JSON, and one
``step_XXX/dom_diff_summary.json`` per action.  It rejects screenshots, raw DOM
diffs, DOM snapshots, page-state files, and verifier-action files as evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import multiprocessing as mp
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent / "src"))
sys.path.insert(0, str(_THIS.parent.parent.parent / "src"))

from webeval.oai_clients.graceful_client import GracefulRetryClient
from webeval.rubric_agent import MMRubricAgentConfig, MMRubricOutcomeResult, MMRubricResult
from webeval.rubric_agent.dom_diff_adapter import (
    DOMDiffTrajectory,
    load_dom_diff_trajectory,
    ordered_action_events,
)
from webeval.rubric_agent.dom_diff_summary_adapter import (
    build_dom_diff_summary_input,
    validate_summary_input_paths,
)
from webeval.rubric_agent.dom_diff_summary_agent import DOMDiffSummaryMMRubricAgent
from webeval.rubric_agent.dom_diff_summary_compaction import COMPACT_SUMMARY_SCHEMA


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(processName)s - %(message)s",
)
logger = logging.getLogger("verify_trajectories_dom_diff_summary")

VERIFIER_SCHEMA_VERSION = "mmrubric-dom-diff-summary-result/v2"
PROMPT_VERSION = "mmrubric-dom-diff-summary-prompts/v2"
EVIDENCE_FORMAT = "dom-diff-summary"
EVIDENCE_SCHEMA_VERSION = "dom-diff-summary/v1"


def load_om2w_tasks(path: Path) -> Dict[str, Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        rows = json.load(handle)
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise ValueError(f"OM2W task data must be a JSON list or object: {path}")
    output: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"OM2W task entry must be an object: {path}")
        task_id = str(row.get("task_id") or row.get("id") or "")
        if not task_id:
            raise ValueError(f"OM2W task entry has no task_id: {row}")
        item = {
            "id": task_id,
            "question": row.get("confirmed_task") or row.get("question") or "",
            "init_url": row.get("website") or row.get("init_url") or "",
            "level": row.get("level"),
        }
        if row.get("precomputed_rubric") is not None:
            item["precomputed_rubric"] = row["precomputed_rubric"]
        output[task_id] = item
    return output


def load_webtailbench_tasks(path: Path) -> Dict[str, Dict[str, Any]]:
    output: Dict[str, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            task_id = (row.get("id") or "").strip()
            if not task_id:
                continue
            item: Dict[str, Any] = {
                "id": task_id,
                "question": (row.get("task_summary") or "").strip(),
                "init_url": (row.get("init_url") or "").strip(),
            }
            raw_rubric = (row.get("precomputed_rubric") or "").strip()
            if raw_rubric:
                item["precomputed_rubric"] = json.loads(raw_rubric)
            output[task_id] = item
    return output


TASK_LOADERS = {"om2w": load_om2w_tasks, "webtailbench": load_webtailbench_tasks}


def _match_task(
    tasks: Dict[str, Dict[str, Any]], trajectory_dir: Path
) -> Optional[Dict[str, Any]]:
    if trajectory_dir.name in tasks:
        return tasks[trajectory_dir.name]
    if len(tasks) == 1:
        return next(iter(tasks.values()))
    return None


def find_trajectory_dirs(input_dir: Path) -> List[Path]:
    def is_trajectory(path: Path) -> bool:
        has_log = (path / "web_surfer.log").is_file() or (path / "websurfer.log").is_file()
        return has_log and len(list(path.glob("*_answer.json"))) == 1

    if is_trajectory(input_dir):
        return [input_dir]
    return [
        child
        for child in sorted(input_dir.iterdir())
        if child.is_dir() and is_trajectory(child)
    ]


def preflight_trajectory(
    trajectory_dir: Path,
    tasks: Dict[str, Dict[str, Any]],
    *,
    redo_eval: bool = False,
) -> Tuple[DOMDiffTrajectory, Dict[str, Any], dict[str, Any]]:
    """Validate every required summary input before judge initialization."""
    task_data = _match_task(tasks, trajectory_dir)
    if task_data is None:
        raise ValueError(f"No task definition found for {trajectory_dir.name}")
    trajectory = load_dom_diff_trajectory(trajectory_dir)
    input_dict = build_dom_diff_summary_input(
        task_data, trajectory, redo_eval=redo_eval
    )
    action_count = len(ordered_action_events(trajectory))
    validate_summary_input_paths(input_dict, action_count)
    return trajectory, task_data, input_dict


def _rubric_hash(task_data: dict[str, Any]) -> Optional[str]:
    rubric = task_data.get("precomputed_rubric")
    if rubric is None:
        return None
    encoded = json.dumps(rubric, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _summary_source_digest(trajectory_dir: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(trajectory_dir.glob("step_*/dom_diff_summary.json"))
    if not paths:
        raise ValueError(f"No dom_diff_summary.json files found under {trajectory_dir}")
    for path in paths:
        digest.update(path.parent.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _verifier_identity(
    args_dict: Dict[str, Any], trajectory_dir: Path | None = None
) -> Tuple[str, Dict[str, Any]]:
    config = {
        "requested_evidence_mode": "dom_diff_summary",
        "evidence_format": EVIDENCE_FORMAT,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "compact_schema_version": COMPACT_SUMMARY_SCHEMA,
        "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model_roles": {
            "judge": args_dict["judge_model"],
            "action_rubric": args_dict["o4mini_model"],
        },
        "rubric_threshold": args_dict["rubric_threshold"],
        "max_evidence_per_criterion": args_dict["max_evidence_per_criterion"],
        "mm_keypoint_score_threshold": args_dict["mm_keypoint_score_threshold"],
        "majority_vote_instances": args_dict["majority_vote_instances"],
        "success_criterion": args_dict["success_criterion"],
        "dom_frame_char_budget": args_dict["dom_frame_char_budget"],
        "dom_context_char_budget": args_dict["dom_context_char_budget"],
        "dom_top_k": args_dict["dom_top_k"],
        "summary_mode": args_dict["summary_mode"],
        "summary_projection": args_dict["summary_projection"],
        "summary_relevance_mode": args_dict["summary_relevance_mode"],
        "summary_analysis_mode": args_dict["summary_analysis_mode"],
        "summary_frame_token_budget": args_dict["summary_frame_token_budget"],
        "summary_trajectory_token_budget": args_dict[
            "summary_trajectory_token_budget"
        ],
        "summary_analysis_token_budget": args_dict["summary_analysis_token_budget"],
        "summary_max_record_chars": args_dict["summary_max_record_chars"],
        "request_timeout_seconds": args_dict["request_timeout_seconds"],
        "max_api_retries": args_dict["max_api_retries"],
        "source_summary_sha256": (
            _summary_source_digest(trajectory_dir) if trajectory_dir is not None else None
        ),
    }
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16], config


def _score_path(trajectory_dir: Path, args_dict: Dict[str, Any]) -> Path:
    identity, _ = _verifier_identity(args_dict, trajectory_dir)
    return trajectory_dir / "scores" / (
        f"mmrubric_{args_dict['rubric_threshold']}-"
        f"{args_dict['max_evidence_per_criterion']}-"
        f"{args_dict['mm_keypoint_score_threshold']}-dom_diff_summary-"
        f"{args_dict['summary_mode']}-{identity}.json"
    )


def _read_cache(
    path: Path,
    args_dict: Dict[str, Any],
    trajectory_dir: Path,
) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    identity, _ = _verifier_identity(args_dict, trajectory_dir)
    return payload if payload.get("cache_identity") == identity else None


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


def _usage_delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {key: after.get(key, 0) - before.get(key, 0) for key in after}


def _instrument_client_calls(client: Any) -> None:
    """Count graceful logical calls and underlying endpoint attempts."""
    if hasattr(client, "_summary_call_metrics"):
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
            *args: Any,
            _original=original_endpoint_create,
            **kwargs: Any,
        ):
            metrics["api_attempts"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = counted_endpoint_create
    client._summary_call_metrics = metrics


def _call_metrics(client: Any) -> dict[str, int]:
    raw = getattr(client, "_summary_call_metrics", {})
    logical = int(raw.get("logical_calls", 0))
    attempts = int(raw.get("api_attempts", 0))
    return {
        "logical_calls": logical,
        "api_attempts": attempts,
        "retries": max(0, attempts - logical),
    }


def _call_metrics_delta(
    after: dict[str, int], before: dict[str, int]
) -> dict[str, int]:
    return {key: after.get(key, 0) - before.get(key, 0) for key in after}


_GLOBAL_AGENT: Optional[DOMDiffSummaryMMRubricAgent] = None
_GLOBAL_TASKS: Optional[Dict[str, Dict[str, Any]]] = None
_GLOBAL_ARGS: Dict[str, Any] = {}


def _pool_init(args_dict: Dict[str, Any], tasks: Dict[str, Dict[str, Any]]) -> None:
    from fara import FARA_ACTION_DEFINITIONS

    global _GLOBAL_AGENT, _GLOBAL_TASKS, _GLOBAL_ARGS
    _GLOBAL_TASKS = tasks
    _GLOBAL_ARGS = args_dict
    worker_logger = logging.getLogger("verify_trajectories_dom_diff_summary.worker")
    o4mini_client = GracefulRetryClient.from_path(
        path=args_dict["eval_config"],
        logger=worker_logger,
        eval_model=args_dict["o4mini_model"],
    )
    gpt5_client = GracefulRetryClient.from_path(
        path=args_dict["eval_config"],
        logger=worker_logger,
        eval_model=args_dict["judge_model"],
    )
    for role, client in (("action_rubric", o4mini_client), ("judge", gpt5_client)):
        client.timeout = args_dict["request_timeout_seconds"]
        client.max_retries = args_dict["max_api_retries"]
        worker_logger.info(
            "Configured %s client timeout=%ss max_retries=%s",
            role,
            client.timeout,
            client.max_retries,
        )
    _instrument_client_calls(o4mini_client)
    _instrument_client_calls(gpt5_client)
    _GLOBAL_AGENT = DOMDiffSummaryMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=o4mini_client,
            gpt5_client=gpt5_client,
            max_images_per_criterion=args_dict["max_evidence_per_criterion"],
            majority_vote_instances=args_dict["majority_vote_instances"],
            redo_eval=args_dict["redo_eval"],
            rubric_score_threshold=args_dict["rubric_threshold"],
            evidence_mode="dom",
            evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
            prompt_version=PROMPT_VERSION,
            verifier_schema_version=VERIFIER_SCHEMA_VERSION,
            dom_frame_char_budget=args_dict["dom_frame_char_budget"],
            dom_context_char_budget=args_dict["dom_context_char_budget"],
            dom_top_k=args_dict["dom_top_k"],
            action_definitions=FARA_ACTION_DEFINITIONS,
            summary_mode=args_dict["summary_mode"],
            summary_projection=args_dict["summary_projection"],
            summary_relevance_mode=args_dict["summary_relevance_mode"],
            summary_analysis_mode=args_dict["summary_analysis_mode"],
            summary_frame_token_budget=args_dict["summary_frame_token_budget"],
            summary_trajectory_token_budget=args_dict[
                "summary_trajectory_token_budget"
            ],
            summary_analysis_token_budget=args_dict["summary_analysis_token_budget"],
            summary_max_record_chars=args_dict["summary_max_record_chars"],
            summary_judge_model=args_dict["judge_model"],
        )
    )


def _capture_coverage(input_dict: dict[str, Any], action_count: int) -> dict[str, Any]:
    summary_actions = input_dict.get("dom_actions") or []
    summary_frames = sum(
        bool(action.get("dom_diff_summary_path")) for action in summary_actions
    )
    return {
        "actions": action_count,
        "diff_frames": 0,
        "summary_frames": summary_frames,
        "alignment_complete": summary_frames == action_count,
        "capture_status_counts": {
            status: sum(
                1
                for action in summary_actions
                if (action.get("dom_capture_status") or "unspecified") == status
            )
            for status in sorted(
                {
                    action.get("dom_capture_status") or "unspecified"
                    for action in summary_actions
                }
            )
        },
        "declared_paths": [
            action["dom_diff_summary_path"] for action in summary_actions
        ],
        "declared_omissions": [
            "screenshots",
            "raw_dom_diff",
            "before_dom",
            "after_dom",
            "before_page_state",
            "after_page_state",
            "verifier_action",
        ],
        "requested_evidence_mode": "dom_diff_summary",
    }


def _run_one(trajectory_dir_string: str) -> Dict[str, Any]:
    assert _GLOBAL_AGENT is not None and _GLOBAL_TASKS is not None
    trajectory_dir = Path(trajectory_dir_string)
    started = time.time()
    output: Dict[str, Any] = {
        "task_id": trajectory_dir.name,
        "traj_dir": str(trajectory_dir),
    }
    score_path = _score_path(trajectory_dir, _GLOBAL_ARGS)

    cached = _read_cache(score_path, _GLOBAL_ARGS, trajectory_dir)
    if cached is not None and not _GLOBAL_ARGS["redo_eval"]:
        output.update(
            status="cached",
            score_path=str(score_path),
            requested_evidence_mode="dom_diff_summary",
            capture_coverage=cached.get("capture_coverage"),
            result=cached.get("result"),
            token_usage=cached.get("token_usage"),
            summary_runtime_metrics=cached.get("summary_runtime_metrics"),
        )
        return output

    try:
        trajectory, task_data, input_dict = preflight_trajectory(
            trajectory_dir, _GLOBAL_TASKS, redo_eval=_GLOBAL_ARGS["redo_eval"]
        )
        action_count = len(ordered_action_events(trajectory))
        before_usage = {
            "judge": _usage_dict(_GLOBAL_AGENT._gpt5_client),
            "action_rubric": _usage_dict(_GLOBAL_AGENT._o4mini_client),
        }
        before_calls = {
            "judge": _call_metrics(_GLOBAL_AGENT._gpt5_client),
            "action_rubric": _call_metrics(_GLOBAL_AGENT._o4mini_client),
        }
        result = asyncio.run(_GLOBAL_AGENT._generate_reply(input_dict))
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError(f"Rubric agent failed: {result}")
        after_usage = {
            "judge": _usage_dict(_GLOBAL_AGENT._gpt5_client),
            "action_rubric": _usage_dict(_GLOBAL_AGENT._o4mini_client),
        }
        after_calls = {
            "judge": _call_metrics(_GLOBAL_AGENT._gpt5_client),
            "action_rubric": _call_metrics(_GLOBAL_AGENT._o4mini_client),
        }
        call_metrics = {
            role: _call_metrics_delta(after_calls[role], before_calls[role])
            for role in after_calls
        }
        call_metrics["total"] = {
            key: sum(call_metrics[role][key] for role in ("judge", "action_rubric"))
            for key in call_metrics["judge"]
        }
        token_usage = {
            role: _usage_delta(after_usage[role], before_usage[role])
            for role in after_usage
        }
        token_usage["total"] = {
            key: sum(token_usage[role][key] for role in ("judge", "action_rubric"))
            for key in token_usage["judge"]
        }
        token_usage["solver_recorded"] = trajectory.token_usage

        verification_results = _GLOBAL_AGENT._wrap_result(result)
        rubric_result = next(
            value for value in verification_results if isinstance(value, MMRubricResult)
        )
        outcome_result = next(
            value
            for value in verification_results
            if isinstance(value, MMRubricOutcomeResult)
        )
        intermediate = result.get("intermediate_mm_rubric_steps") or {}
        error_taxonomy = {
            "first_point_of_failure": intermediate.get("step9_first_point_of_failure"),
            "task_verification_with_trajectory": intermediate.get(
                "step9b_task_verification_with_trajectory"
            ),
            "task_verification": intermediate.get("step10_task_verification"),
        }
        process_pass = bool(rubric_result.rubric_is_success)
        outcome_pass = outcome_result.output_success is True
        criterion = _GLOBAL_ARGS["success_criterion"]
        top_score = int(
            process_pass
            if criterion == "process"
            else process_pass and outcome_pass
            if criterion == "both"
            else outcome_pass
        )
        capture = _capture_coverage(input_dict, action_count)
        if not capture["alignment_complete"]:
            raise RuntimeError(f"Incomplete summary capture coverage: {capture}")
        identity, verifier_config = _verifier_identity(_GLOBAL_ARGS, trajectory_dir)
        summary_metrics = _GLOBAL_AGENT.summary_runtime_metrics()
        structured_result = {
            "top_score": top_score,
            "success_criterion": criterion,
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
            "error_taxonomy": error_taxonomy,
        }
        score_payload = {
            "score": top_score,
            "evidence_format": EVIDENCE_FORMAT,
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "compact_schema_version": COMPACT_SUMMARY_SCHEMA,
            "requested_evidence_mode": "dom_diff_summary",
            "diff_frames": 0,
            "summary_frames": capture["summary_frames"],
            "actions": action_count,
            "alignment_complete": capture["alignment_complete"],
            "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "model_roles": verifier_config["model_roles"],
            "capture_coverage": capture,
            "frozen_rubric_sha256": _rubric_hash(task_data),
            "token_usage": token_usage,
            "call_metrics": call_metrics,
            "summary_runtime_metrics": summary_metrics,
            "verifier_config": verifier_config,
            "cache_identity": identity,
            "result": structured_result,
        }
        score_path.parent.mkdir(parents=True, exist_ok=True)
        with score_path.open("w", encoding="utf-8") as handle:
            json.dump(score_payload, handle, indent=2)
        output.update(
            status="ok",
            score_path=str(score_path),
            rubric_score=rubric_result.score,
            rubric_total_max_points=rubric_result.total_max_points,
            rubric_total_earned_points=rubric_result.total_earned_points,
            rubric_is_success=process_pass,
            outcome_success=outcome_result.output_success,
            requested_evidence_mode="dom_diff_summary",
            capture_coverage=capture,
            token_usage=token_usage,
            call_metrics=call_metrics,
            summary_runtime_metrics=summary_metrics,
            cache_identity=identity,
        )
    except Exception as exc:
        output.update(
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
        logger.error("[%s] %s", trajectory_dir.name, output["error"])
    finally:
        output["duration_sec"] = round(time.time() - started, 2)
    return output


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--task-data", required=True)
    parser.add_argument("--task-data-format", choices=sorted(TASK_LOADERS), required=True)
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--o4mini-model", default="o4-mini")
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument("--success", choices=("outcome", "process", "both"), default="outcome")
    parser.add_argument(
        "--max-evidence-per-criterion",
        "--max-images-per-criterion",
        dest="max_evidence_per_criterion",
        type=int,
        default=5,
    )
    parser.add_argument("--mm-keypoint-score-threshold", type=int, default=3)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--dom-frame-char-budget", type=int, default=16000)
    parser.add_argument("--dom-context-char-budget", type=int, default=48000)
    parser.add_argument("--dom-top-k", type=int, default=None)
    parser.add_argument("--summary-mode", choices=("s0", "s1", "s2", "s3"), default="s1")
    parser.add_argument("--summary-projection", choices=("auto", "raw", "compact"), default="auto")
    parser.add_argument(
        "--summary-relevance-mode",
        choices=("auto", "per_frame_llm", "batched_llm", "local"),
        default="auto",
    )
    parser.add_argument(
        "--summary-analysis-mode",
        choices=("auto", "selected_frames", "packed"),
        default="auto",
    )
    parser.add_argument("--summary-frame-token-budget", type=int, default=1500)
    parser.add_argument("--summary-trajectory-token-budget", type=int, default=16000)
    parser.add_argument("--summary-analysis-token-budget", type=int, default=24000)
    parser.add_argument("--summary-max-record-chars", type=int, default=600)
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-api-retries", type=int, default=2)
    parser.add_argument("--redo-eval", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args(argv)
    if args.max_evidence_per_criterion <= 0:
        parser.error("--max-evidence-per-criterion must be positive")
    if args.dom_frame_char_budget <= 0 or args.dom_context_char_budget <= 0:
        parser.error("DOM character budgets must be positive")
    if args.dom_top_k is not None and args.dom_top_k <= 0:
        parser.error("--dom-top-k must be positive")
    for name in (
        "summary_frame_token_budget",
        "summary_trajectory_token_budget",
        "summary_analysis_token_budget",
        "summary_max_record_chars",
    ):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.processes <= 0:
        parser.error("--processes must be positive")
    if args.request_timeout_seconds <= 0:
        parser.error("--request-timeout-seconds must be positive")
    if args.max_api_retries <= 0:
        parser.error("--max-api-retries must be positive")

    if args.summary_projection == "auto":
        args.summary_projection = "raw" if args.summary_mode == "s0" else "compact"
    if args.summary_relevance_mode == "auto":
        args.summary_relevance_mode = (
            "batched_llm" if args.summary_mode in {"s2", "s3"} else "per_frame_llm"
        )
    if args.summary_analysis_mode == "auto":
        args.summary_analysis_mode = (
            "packed" if args.summary_mode == "s3" else "selected_frames"
        )
    if args.summary_mode == "s0" and args.summary_projection != "raw":
        parser.error("S0 requires --summary-projection raw")
    return args


def _write_report(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    input_dir = Path(args.input).resolve()
    task_data_path = Path(args.task_data).resolve()
    eval_config = Path(args.eval_config).resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"--input is not a directory: {input_dir}")
    if not task_data_path.is_file():
        raise SystemExit(f"--task-data is not a file: {task_data_path}")
    if not eval_config.exists():
        raise SystemExit(f"--eval-config does not exist: {eval_config}")

    tasks = TASK_LOADERS[args.task_data_format](task_data_path)
    trajectory_dirs = find_trajectory_dirs(input_dir)
    if args.limit is not None:
        trajectory_dirs = trajectory_dirs[: args.limit]
    if not trajectory_dirs:
        raise SystemExit(f"No DOM-diff-summary trajectories found under {input_dir}")

    preflight_errors: List[Dict[str, Any]] = []
    for trajectory_dir in trajectory_dirs:
        try:
            preflight_trajectory(trajectory_dir, tasks, redo_eval=args.redo_eval)
        except Exception as exc:
            preflight_errors.append(
                {
                    "task_id": trajectory_dir.name,
                    "traj_dir": str(trajectory_dir),
                    "status": "input_validation_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "requested_evidence_mode": "dom_diff_summary",
                }
            )
    report_path = (
        Path(args.report).resolve()
        if args.report
        else input_dir / "verify_report_dom_diff_summary.jsonl"
    )
    if preflight_errors:
        _write_report(report_path, preflight_errors)
        raise SystemExit(
            f"DOM-diff-summary preflight failed for {len(preflight_errors)} trajectory(s); "
            f"no judge clients were initialized. See {report_path}"
        )

    args_dict = {
        "eval_config": str(eval_config),
        "judge_model": args.judge_model,
        "o4mini_model": args.o4mini_model,
        "rubric_threshold": args.rubric_threshold,
        "max_evidence_per_criterion": args.max_evidence_per_criterion,
        "mm_keypoint_score_threshold": args.mm_keypoint_score_threshold,
        "majority_vote_instances": args.majority_vote_instances,
        "redo_eval": args.redo_eval,
        "success_criterion": args.success,
        "dom_frame_char_budget": args.dom_frame_char_budget,
        "dom_context_char_budget": args.dom_context_char_budget,
        "dom_top_k": args.dom_top_k,
        "summary_mode": args.summary_mode,
        "summary_projection": args.summary_projection,
        "summary_relevance_mode": args.summary_relevance_mode,
        "summary_analysis_mode": args.summary_analysis_mode,
        "summary_frame_token_budget": args.summary_frame_token_budget,
        "summary_trajectory_token_budget": args.summary_trajectory_token_budget,
        "summary_analysis_token_budget": args.summary_analysis_token_budget,
        "summary_max_record_chars": args.summary_max_record_chars,
        "request_timeout_seconds": args.request_timeout_seconds,
        "max_api_retries": args.max_api_retries,
    }
    results: List[Dict[str, Any]]
    if args.processes == 1:
        _pool_init(args_dict, tasks)
        results = [_run_one(str(path)) for path in trajectory_dirs]
    else:
        context = mp.get_context("spawn")
        with context.Pool(
            processes=args.processes,
            initializer=_pool_init,
            initargs=(args_dict, tasks),
        ) as pool:
            results = list(pool.imap_unordered(_run_one, map(str, trajectory_dirs)))
    _write_report(report_path, results)
    ok = sum(row.get("status") in {"ok", "cached"} for row in results)
    logger.info("DOM-diff-summary verification complete: %s/%s succeeded", ok, len(results))
    logger.info("Report: %s", report_path)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

