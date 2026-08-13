#!/usr/bin/env python3
"""Run Universal Verifier using root-level refined ``dom_diffN.txt`` only.

Every trajectory is fully preflighted before judge clients are initialized.
The Microsoft and DOM-diff-summary runners are neither imported nor modified.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import multiprocessing as mp
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional


_THIS = Path(__file__).resolve()
for _source_root in (_THIS.parent.parent / "src", _THIS.parent.parent.parent / "src"):
    _source = str(_source_root)
    if _source not in sys.path:
        sys.path.insert(0, _source)

from webeval.rubric_agent import MMRubricAgentConfig, MMRubricOutcomeResult, MMRubricResult
from webeval.rubric_agent.dom_diff_adapter import DOMDiffTrajectory, ordered_action_events
from webeval.rubric_agent.dom_diff_text_adapter import (
    preflight_dom_diff_text_bundle,
    semantic_action_definitions,
)
from webeval.rubric_agent.dom_diff_text_agent import DOMDiffTextMMRubricAgent
from webeval.rubric_agent.dom_diff_text_compaction import COMPACT_DOM_DIFF_TEXT_SCHEMA
from webeval.rubric_agent.dom_diff_text_evidence import DOM_DIFF_TEXT_SCHEMA


logger = logging.getLogger("verify_trajectories_dom_diff_text")

VERIFIER_SCHEMA_VERSION = "mmrubric-dom-diff-text-result/v1"
PROMPT_VERSION = "mmrubric-dom-diff-text-prompts/v1"
EVIDENCE_FORMAT = "runner-dom-diff-text"
REQUESTED_EVIDENCE_MODE = "dom_diff_text"


def _load_local_task_data(trajectory_dir: Path) -> dict[str, Any]:
    path = trajectory_dir / "task_data.json"
    if not path.is_file():
        raise ValueError(f"Missing task_data.json: {trajectory_dir}")
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"task_data.json must contain exactly one task: {path}")
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError(f"task_data.json must be one object or one-item list: {path}")
    task_id = str(value.get("task_id") or value.get("id") or "")
    if not task_id:
        raise ValueError(f"Task data has no internal task ID: {path}")
    return value


def find_trajectory_dirs(input_dir: Path) -> List[Path]:
    def is_trajectory(path: Path) -> bool:
        return (
            (path / "task_data.json").is_file()
            and (path / "web_surfer.log").is_file()
            and (path / "final_answer.json").is_file()
        )

    if is_trajectory(input_dir):
        return [input_dir]
    return [
        child
        for child in sorted(input_dir.iterdir())
        if child.is_dir() and is_trajectory(child)
    ]


def preflight_trajectory(
    trajectory_dir: Path, *, redo_eval: bool = False
) -> tuple[DOMDiffTrajectory, dict[str, Any], dict[str, Any], list[Any]]:
    task_data = _load_local_task_data(trajectory_dir)
    trajectory, input_dict, frames = preflight_dom_diff_text_bundle(
        trajectory_dir,
        task_data,
        redo_eval=redo_eval,
        require_frozen_rubric=True,
    )
    return trajectory, task_data, input_dict, frames


def _text_source_digest(trajectory_dir: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        trajectory_dir.glob("dom_diff*.txt"),
        key=lambda path: int(path.stem.removeprefix("dom_diff")),
    )
    if not paths:
        raise ValueError(f"No refined text diffs found in {trajectory_dir}")
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _frozen_rubric_digest(trajectory_dir: Path) -> str | None:
    task_data = _load_local_task_data(trajectory_dir)
    rubric = task_data.get("precomputed_rubric")
    if rubric is None:
        return None
    if isinstance(rubric, list) and len(rubric) == 1:
        rubric = rubric[0]
    encoded = json.dumps(
        rubric, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_digest(path_value: str | Path) -> str | None:
    path = Path(path_value)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _verifier_identity(
    args_dict: Dict[str, Any], trajectory_dir: Path | None = None
) -> tuple[str, dict[str, Any]]:
    config = {
        "requested_evidence_mode": REQUESTED_EVIDENCE_MODE,
        "evidence_format": EVIDENCE_FORMAT,
        "evidence_schema_version": DOM_DIFF_TEXT_SCHEMA,
        "compact_schema_version": COMPACT_DOM_DIFF_TEXT_SCHEMA,
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
        "text_relevance_mode": args_dict["text_relevance_mode"],
        "text_frame_starting_tokens": args_dict["text_frame_starting_tokens"],
        "text_trajectory_starting_tokens": args_dict["text_trajectory_starting_tokens"],
        "text_analysis_starting_tokens": args_dict["text_analysis_starting_tokens"],
        "text_max_chunk_tokens": args_dict["text_max_chunk_tokens"],
        "text_allow_budget_expansion": args_dict["text_allow_budget_expansion"],
        "text_model_context_window_tokens": args_dict[
            "text_model_context_window_tokens"
        ],
        "text_relevance_completion_reserve_tokens": args_dict[
            "text_relevance_completion_reserve_tokens"
        ],
        "text_analysis_completion_reserve_tokens": args_dict[
            "text_analysis_completion_reserve_tokens"
        ],
        "text_prompt_headroom_tokens": args_dict["text_prompt_headroom_tokens"],
        "request_timeout_seconds": args_dict["request_timeout_seconds"],
        "max_api_retries": args_dict["max_api_retries"],
        "eval_config_sha256": _file_digest(args_dict["eval_config"]),
        "frozen_rubric_sha256": (
            _frozen_rubric_digest(trajectory_dir)
            if trajectory_dir is not None
            else None
        ),
        "source_text_sha256": (
            _text_source_digest(trajectory_dir) if trajectory_dir is not None else None
        ),
    }
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16], config


def _score_path(trajectory_dir: Path, args_dict: Dict[str, Any]) -> Path:
    identity, _ = _verifier_identity(args_dict, trajectory_dir)
    return trajectory_dir / "scores" / (
        f"mmrubric_{args_dict['rubric_threshold']}-"
        f"{args_dict['max_evidence_per_criterion']}-"
        f"{args_dict['mm_keypoint_score_threshold']}-dom_diff_text-{identity}.json"
    )


def _read_cache(
    path: Path, args_dict: Dict[str, Any], trajectory_dir: Path
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


# These small runner-plumbing functions intentionally mirror the reference
# summary runner locally. Importing that script would initialize logging and
# mutate module state, so the approved design requires local parity tests.
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
    if hasattr(client, "_dom_text_call_metrics"):
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
    client._dom_text_call_metrics = metrics


def _call_metrics(client: Any) -> dict[str, int]:
    raw = getattr(client, "_dom_text_call_metrics", {})
    logical = int(raw.get("logical_calls", 0))
    attempts = int(raw.get("api_attempts", 0))
    return {
        "logical_calls": logical,
        "api_attempts": attempts,
        "retries": max(0, attempts - logical),
    }


_GLOBAL_AGENT: Optional[DOMDiffTextMMRubricAgent] = None
_GLOBAL_ARGS: Dict[str, Any] = {}


def _pool_init(args_dict: Dict[str, Any]) -> None:
    from webeval.oai_clients.graceful_client import GracefulRetryClient

    global _GLOBAL_AGENT, _GLOBAL_ARGS
    _GLOBAL_ARGS = args_dict
    worker_logger = logging.getLogger("verify_trajectories_dom_diff_text.worker")
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
    for client in (o4mini_client, gpt5_client):
        client.timeout = args_dict["request_timeout_seconds"]
        client.max_retries = args_dict["max_api_retries"]
        _instrument_client_calls(client)
    _GLOBAL_AGENT = DOMDiffTextMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=o4mini_client,
            gpt5_client=gpt5_client,
            max_images_per_criterion=args_dict["max_evidence_per_criterion"],
            majority_vote_instances=args_dict["majority_vote_instances"],
            redo_eval=args_dict["redo_eval"],
            rubric_score_threshold=args_dict["rubric_threshold"],
            evidence_mode="dom",
            evidence_schema_version=DOM_DIFF_TEXT_SCHEMA,
            prompt_version=PROMPT_VERSION,
            verifier_schema_version=VERIFIER_SCHEMA_VERSION,
            dom_frame_char_budget=args_dict["dom_frame_char_budget"],
            dom_context_char_budget=args_dict["dom_context_char_budget"],
            dom_top_k=args_dict["dom_top_k"],
            action_definitions=semantic_action_definitions(),
            text_relevance_mode=args_dict["text_relevance_mode"],
            text_frame_starting_tokens=args_dict["text_frame_starting_tokens"],
            text_trajectory_starting_tokens=args_dict[
                "text_trajectory_starting_tokens"
            ],
            text_analysis_starting_tokens=args_dict["text_analysis_starting_tokens"],
            text_max_chunk_tokens=args_dict["text_max_chunk_tokens"],
            text_allow_budget_expansion=args_dict["text_allow_budget_expansion"],
            text_model_context_window_tokens=args_dict[
                "text_model_context_window_tokens"
            ],
            text_relevance_completion_reserve_tokens=args_dict[
                "text_relevance_completion_reserve_tokens"
            ],
            text_analysis_completion_reserve_tokens=args_dict[
                "text_analysis_completion_reserve_tokens"
            ],
            text_prompt_headroom_tokens=args_dict["text_prompt_headroom_tokens"],
            text_judge_model=args_dict["judge_model"],
        )
    )


def _capture_coverage(input_dict: dict[str, Any], action_count: int) -> dict[str, Any]:
    actions = input_dict.get("dom_actions") or []
    text_frames = sum(bool(action.get("dom_diff_text_path")) for action in actions)
    return {
        "actions": action_count,
        "text_frames": text_frames,
        "alignment_complete": text_frames == action_count,
        "declared_paths": [action["dom_diff_text_path"] for action in actions],
        "declared_omissions": [
            "screenshots",
            "raw_dom_diff",
            "dom_diff_summary",
            "before_dom",
            "after_dom",
            "before_page_state",
            "after_page_state",
            "verifier_action",
            "agent_browser_observations",
        ],
        "requested_evidence_mode": REQUESTED_EVIDENCE_MODE,
    }


def _run_one(trajectory_dir_string: str) -> Dict[str, Any]:
    assert _GLOBAL_AGENT is not None
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
            requested_evidence_mode=REQUESTED_EVIDENCE_MODE,
            capture_coverage=cached.get("capture_coverage"),
            result=cached.get("result"),
            token_usage=cached.get("token_usage"),
            call_metrics=cached.get("call_metrics"),
            text_runtime_metrics=cached.get("text_runtime_metrics"),
        )
        return output
    try:
        trajectory, task_data, input_dict, frames = preflight_trajectory(
            trajectory_dir, redo_eval=_GLOBAL_ARGS["redo_eval"]
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
        token_usage = {
            role: _delta(after_usage[role], before_usage[role]) for role in after_usage
        }
        call_metrics = {
            role: _delta(after_calls[role], before_calls[role]) for role in after_calls
        }
        for values in (token_usage, call_metrics):
            values["total"] = {
                key: sum(values[role][key] for role in ("judge", "action_rubric"))
                for key in values["judge"]
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
            raise RuntimeError(f"Incomplete refined-text capture coverage: {capture}")
        identity, verifier_config = _verifier_identity(_GLOBAL_ARGS, trajectory_dir)
        text_metrics = _GLOBAL_AGENT.text_runtime_metrics()
        structured_result = {
            "top_score": top_score,
            "success_criterion": criterion,
            "rubric": {
                "score": rubric_result.score,
                "is_success": process_pass,
                "frozen_input_denominator": input_dict["frozen_input_denominator"],
                "total_max_points": rubric_result.total_max_points,
                "total_earned_points": rubric_result.total_earned_points,
                "items": result.get("items", []),
            },
            "outcome": {
                "success": outcome_result.output_success,
                "reasoning": outcome_result.reasoning,
                "primary_intent": outcome_result.primary_intent,
            },
            "penalty": intermediate.get("step7_unsolicited_side_effects"),
            "error_taxonomy": {
                "first_point_of_failure": intermediate.get(
                    "step9_first_point_of_failure"
                ),
                "task_verification_with_trajectory": intermediate.get(
                    "step9b_task_verification_with_trajectory"
                ),
                "task_verification": intermediate.get("step10_task_verification"),
            },
        }
        score_payload = {
            "score": top_score,
            "evidence_format": EVIDENCE_FORMAT,
            "evidence_schema_version": DOM_DIFF_TEXT_SCHEMA,
            "compact_schema_version": COMPACT_DOM_DIFF_TEXT_SCHEMA,
            "requested_evidence_mode": REQUESTED_EVIDENCE_MODE,
            "text_frames": len(frames),
            "actions": action_count,
            "alignment_complete": capture["alignment_complete"],
            "verifier_schema_version": VERIFIER_SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "model_roles": verifier_config["model_roles"],
            "capture_coverage": capture,
            "frozen_rubric_sha256": input_dict["frozen_rubric_sha256"],
            "frozen_input_denominator": input_dict["frozen_input_denominator"],
            "final_denominator": rubric_result.total_max_points,
            "token_usage": token_usage,
            "call_metrics": call_metrics,
            "text_runtime_metrics": text_metrics,
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
            requested_evidence_mode=REQUESTED_EVIDENCE_MODE,
            capture_coverage=capture,
            token_usage=token_usage,
            call_metrics=call_metrics,
            text_runtime_metrics=text_metrics,
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
    parser.add_argument("--eval-config", required=True)
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--o4mini-model", default="o4-mini")
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument(
        "--success", choices=("outcome", "process", "both"), default="outcome"
    )
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
    parser.add_argument("--text-frame-starting-tokens", type=int, default=1500)
    parser.add_argument("--text-trajectory-starting-tokens", type=int, default=16000)
    parser.add_argument("--text-analysis-starting-tokens", type=int, default=24000)
    parser.add_argument("--text-max-chunk-tokens", type=int, default=256)
    parser.add_argument(
        "--text-model-context-window-tokens", type=int, default=128000
    )
    parser.add_argument(
        "--text-relevance-completion-reserve-tokens", type=int, default=4096
    )
    parser.add_argument(
        "--text-analysis-completion-reserve-tokens", type=int, default=8192
    )
    parser.add_argument("--text-prompt-headroom-tokens", type=int, default=1024)
    parser.add_argument(
        "--no-text-budget-expansion",
        action="store_false",
        dest="text_allow_budget_expansion",
        help="Fail rather than omit evidence at a soft starting target.",
    )
    parser.set_defaults(text_allow_budget_expansion=True)
    parser.add_argument("--request-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-api-retries", type=int, default=2)
    parser.add_argument("--redo-eval", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args(argv)
    positive = (
        "max_evidence_per_criterion",
        "majority_vote_instances",
        "processes",
        "dom_frame_char_budget",
        "dom_context_char_budget",
        "text_frame_starting_tokens",
        "text_trajectory_starting_tokens",
        "text_analysis_starting_tokens",
        "text_max_chunk_tokens",
        "text_model_context_window_tokens",
        "text_relevance_completion_reserve_tokens",
        "text_analysis_completion_reserve_tokens",
        "text_prompt_headroom_tokens",
        "request_timeout_seconds",
        "max_api_retries",
    )
    for name in positive:
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.dom_top_k is not None:
        parser.error(
            "--dom-top-k is unsupported for refined text because it would drop "
            "chronological action steps; use --max-evidence-per-criterion"
        )
    if (
        args.text_relevance_completion_reserve_tokens
        + args.text_prompt_headroom_tokens
        >= args.text_model_context_window_tokens
        or args.text_analysis_completion_reserve_tokens
        + args.text_prompt_headroom_tokens
        >= args.text_model_context_window_tokens
    ):
        parser.error("Completion reserve plus headroom must be below model context")
    return args


def _write_report(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(processName)s - %(message)s",
    )
    input_dir = Path(args.input).resolve()
    eval_config = Path(args.eval_config).resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"--input is not a directory: {input_dir}")
    if not eval_config.exists():
        raise SystemExit(f"--eval-config does not exist: {eval_config}")
    trajectory_dirs = find_trajectory_dirs(input_dir)
    if args.limit is not None:
        trajectory_dirs = trajectory_dirs[: args.limit]
    if not trajectory_dirs:
        raise SystemExit(f"No refined DOM-diff text trajectories found under {input_dir}")

    report_path = (
        Path(args.report).resolve()
        if args.report
        else input_dir / "verify_report_dom_diff_text.jsonl"
    )
    preflight_errors: List[Dict[str, Any]] = []
    for trajectory_dir in trajectory_dirs:
        try:
            preflight_trajectory(trajectory_dir, redo_eval=args.redo_eval)
        except Exception as exc:
            preflight_errors.append(
                {
                    "task_id": trajectory_dir.name,
                    "traj_dir": str(trajectory_dir),
                    "status": "input_validation_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "requested_evidence_mode": REQUESTED_EVIDENCE_MODE,
                }
            )
    if preflight_errors:
        _write_report(report_path, preflight_errors)
        raise SystemExit(
            f"Refined DOM-diff text preflight failed for {len(preflight_errors)} "
            f"trajectory(s); no judge clients were initialized. See {report_path}"
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
        "text_relevance_mode": "batched_llm",
        "text_frame_starting_tokens": args.text_frame_starting_tokens,
        "text_trajectory_starting_tokens": args.text_trajectory_starting_tokens,
        "text_analysis_starting_tokens": args.text_analysis_starting_tokens,
        "text_max_chunk_tokens": args.text_max_chunk_tokens,
        "text_allow_budget_expansion": args.text_allow_budget_expansion,
        "text_model_context_window_tokens": args.text_model_context_window_tokens,
        "text_relevance_completion_reserve_tokens": (
            args.text_relevance_completion_reserve_tokens
        ),
        "text_analysis_completion_reserve_tokens": (
            args.text_analysis_completion_reserve_tokens
        ),
        "text_prompt_headroom_tokens": args.text_prompt_headroom_tokens,
        "request_timeout_seconds": args.request_timeout_seconds,
        "max_api_retries": args.max_api_retries,
    }
    if args.processes == 1:
        _pool_init(args_dict)
        results = [_run_one(str(path)) for path in trajectory_dirs]
    else:
        context = mp.get_context("spawn")
        with context.Pool(
            processes=args.processes,
            initializer=_pool_init,
            initargs=(args_dict,),
        ) as pool:
            results = list(pool.imap_unordered(_run_one, map(str, trajectory_dirs)))
    _write_report(report_path, results)
    ok = sum(row.get("status") in {"ok", "cached"} for row in results)
    logger.info("Refined DOM-diff text verification complete: %s/%s succeeded", ok, len(results))
    logger.info("Report: %s", report_path)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
