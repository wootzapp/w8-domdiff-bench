#!/usr/bin/env python3
"""Build DOM-diff-summary S1/S2/S3 payload metrics without any LLM calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent))
sys.path.insert(0, str(_THIS.parent.parent / "src"))
sys.path.insert(0, str(_THIS.parent.parent.parent / "src"))

import verify_trajectories_dom_diff_summary as runner
from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_summary_evidence import (
    load_dom_diff_summary_frames,
    render_summary_result,
    summary_compaction_metrics,
)
from webeval.rubric_agent.dom_diff_summary_prompts import (
    DOM_DIFF_SUMMARY_GROUNDING_RULES,
    SUMMARY_BATCHED_RELEVANCE_PROMPT,
    SUMMARY_PACKED_ANALYSIS_PROMPT,
)
from webeval.rubric_agent.dom_diff_summary_retrieval import (
    build_selection_receipts,
    local_relevance_scores,
    render_batched_relevance_evidence,
    render_packed_analysis_evidence,
)


def _rubric_text(rubric: dict[str, Any]) -> str:
    return "".join(
        f"{idx}. {item.get('criterion', '')}\n{item.get('description', '')}\n"
        for idx, item in enumerate(rubric.get("items") or [])
    )


def _criteria_text(rubric: dict[str, Any]) -> str:
    return "".join(
        f"Criterion {idx}: {item.get('criterion', '')}\n"
        f"Description: {item.get('description', '')}\n"
        f"Max points: {item.get('max_points', 0)}\n"
        for idx, item in enumerate(rubric.get("items") or [])
    )


def build_diagnostic(args: argparse.Namespace) -> dict[str, Any]:
    task_loader = runner.TASK_LOADERS[args.task_data_format]
    tasks = task_loader(Path(args.task_data).resolve())
    trajectory, task, input_dict = runner.preflight_trajectory(
        Path(args.trajectory).resolve(), tasks
    )
    del trajectory
    frames = load_dom_diff_summary_frames(
        input_dict["dom_actions"], max_record_chars=args.summary_max_record_chars
    )
    rubric = task.get("precomputed_rubric")
    if not isinstance(rubric, dict) or not isinstance(rubric.get("items"), list):
        raise ValueError("Diagnostic requires a frozen precomputed rubric")

    s1_rendered = [
        render_summary_result(
            frame,
            projection="compact",
            token_budget=args.summary_frame_token_budget,
            model=args.judge_model,
        )
        for frame in frames
    ]
    scores = local_relevance_scores(
        [frame.compact for frame in frames],
        rubric,
        task=str(task.get("question") or ""),
        predicted_output=str(input_dict.get("predicted_output") or ""),
    )
    grouped = {
        criterion_idx: sorted(
            range(len(frames)),
            key=lambda frame_idx: (
                scores[frame_idx][criterion_idx],
                frame_idx,
            ),
            reverse=True,
        )[: args.max_evidence_per_criterion]
        for criterion_idx in range(len(rubric["items"]))
    }
    receipts = build_selection_receipts(
        [frame.compact for frame in frames],
        grouped,
        scores,
        rubric,
        predicted_output=str(input_dict.get("predicted_output") or ""),
    )

    estimator = TokenEstimator(args.judge_model)
    relevance_empty = SUMMARY_BATCHED_RELEVANCE_PROMPT.substitute(
        task_definition=str(task.get("question") or ""),
        init_url_context=str(task.get("init_url") or ""),
        summary_frames="",
        rubric_criteria=_rubric_text(rubric),
        grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
    )
    relevance_evidence_budget = (
        args.summary_trajectory_token_budget
        - estimator.count(relevance_empty)
        - 64
    )
    if relevance_evidence_budget < 120:
        raise ValueError("Trajectory token budget is too small for fixed context")
    s2 = render_batched_relevance_evidence(
        [frame.compact for frame in frames],
        token_budget=relevance_evidence_budget,
        model=args.judge_model,
    )

    analysis_empty = SUMMARY_PACKED_ANALYSIS_PROMPT.substitute(
        task_definition=str(task.get("question") or ""),
        init_url_context=str(task.get("init_url") or ""),
        action_history=str(input_dict.get("action_history") or ""),
        agent_predicted_output=str(input_dict.get("predicted_output") or ""),
        packed_evidence="",
        criteria_info_block=_criteria_text(rubric),
        grounding_rules=DOM_DIFF_SUMMARY_GROUNDING_RULES,
    )
    analysis_evidence_budget = (
        args.summary_analysis_token_budget - estimator.count(analysis_empty) - 64
    )
    if analysis_evidence_budget < 160:
        raise ValueError("Analysis token budget is too small for fixed context")
    s3 = render_packed_analysis_evidence(
        [frame.compact for frame in frames],
        grouped,
        token_budget=analysis_evidence_budget,
        model=args.judge_model,
    )

    result = summary_compaction_metrics(frames)
    result.update(
        {
            "task_id": str(task.get("id") or Path(args.trajectory).name),
            "tokenizer": estimator.name,
            "s1": {
                "rendered_chars": sum(len(value.text) for value in s1_rendered),
                "estimated_evidence_tokens": sum(
                    value.estimated_tokens for value in s1_rendered
                ),
                "records_omitted_by_budget": sum(
                    value.records_omitted_by_budget for value in s1_rendered
                ),
            },
            "s2": {
                "fixed_prompt_tokens": estimator.count(relevance_empty),
                "evidence_tokens": s2.estimated_tokens,
                "total_prompt_tokens_estimate": (
                    estimator.count(relevance_empty) + s2.estimated_tokens
                ),
                "records_omitted_by_budget": s2.records_omitted_by_budget,
            },
            "s3": {
                "fixed_prompt_tokens": estimator.count(analysis_empty),
                "evidence_tokens": s3.estimated_tokens,
                "total_prompt_tokens_estimate": (
                    estimator.count(analysis_empty) + s3.estimated_tokens
                ),
                "selected_unique_frames": list(s3.frame_indices),
                "records_omitted_by_budget": s3.records_omitted_by_budget,
            },
            "selection_receipts": [receipt.to_dict() for receipt in receipts],
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory", required=True)
    parser.add_argument("--task-data", required=True)
    parser.add_argument(
        "--task-data-format", choices=sorted(runner.TASK_LOADERS), required=True
    )
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--max-evidence-per-criterion", type=int, default=5)
    parser.add_argument("--summary-frame-token-budget", type=int, default=1500)
    parser.add_argument("--summary-trajectory-token-budget", type=int, default=16000)
    parser.add_argument("--summary-analysis-token-budget", type=int, default=24000)
    parser.add_argument("--summary-max-record-chars", type=int, default=600)
    parser.add_argument("--output")
    args = parser.parse_args()
    for name in (
        "max_evidence_per_criterion",
        "summary_frame_token_budget",
        "summary_trajectory_token_budget",
        "summary_analysis_token_budget",
        "summary_max_record_chars",
    ):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    return args


def main() -> int:
    args = parse_args()
    result = build_diagnostic(args)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

