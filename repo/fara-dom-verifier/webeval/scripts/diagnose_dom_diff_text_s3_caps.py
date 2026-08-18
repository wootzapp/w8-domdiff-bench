#!/usr/bin/env python3
"""Offline 10k/15k/20k S3-cap diagnostics for refined DOM-diff text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional


_THIS = Path(__file__).resolve()
for _source_root in (_THIS.parent.parent / "src", _THIS.parent.parent.parent / "src"):
    _source = str(_source_root)
    if _source not in sys.path:
        sys.path.insert(0, _source)

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_adapter import preflight_dom_diff_text_bundle
from webeval.rubric_agent.dom_diff_text_compaction import compact_text_frames
from webeval.rubric_agent.dom_diff_text_prompts import (
    DOM_DIFF_TEXT_GROUNDING_RULES,
    TEXT_BATCHED_RELEVANCE_PROMPT,
    TEXT_PACKED_ANALYSIS_PROMPT,
)
from webeval.rubric_agent.dom_diff_text_retrieval import (
    local_relevance_scores,
    render_batched_relevance_evidence,
    render_packed_analysis_evidence,
)
from webeval.rubric_agent.dom_diff_text_s3_capping import apply_s3_prompt_cap
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgent


def _load_task_data(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"Expected one task in {path}")
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError(f"Expected one task object in {path}")
    return value


def _diagnostic_rubric(task_data: dict[str, Any]) -> dict[str, Any]:
    rubric = task_data.get("precomputed_rubric")
    if isinstance(rubric, list) and len(rubric) == 1:
        rubric = rubric[0]
    if not isinstance(rubric, dict) or not isinstance(rubric.get("items"), list):
        raise ValueError("Offline S3 diagnostics require the frozen precomputed_rubric")
    return rubric


def _rubric_text(rubric: dict[str, Any]) -> str:
    return "".join(
        f"\n{idx}. **{item['criterion']}**\n"
        f"   Description: {item['description']}\n"
        for idx, item in enumerate(rubric["items"])
    )


def _criteria_block(rubric: dict[str, Any]) -> str:
    block = ""
    for idx, item in enumerate(rubric["items"]):
        block += (
            f"\n**Criterion {idx}:** {item['criterion']}\n"
            f"**Description:** {item['description']}\n"
            f"**Max Points:** {item['max_points']}\n"
        )
        if "condition" in item:
            block += (
                f"**CONDITIONAL:** {item['condition']}; include "
                "condition_verification.\n"
            )
    return block


def _parse_caps(value: str) -> tuple[int, ...]:
    caps = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not caps or any(cap <= 0 for cap in caps):
        raise argparse.ArgumentTypeError("caps must be comma-separated positive integers")
    return caps


def build_diagnostics(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.input).resolve()
    output_root = Path(args.output_dir).resolve() / root.name
    output_root.mkdir(parents=True, exist_ok=True)
    task_data = _load_task_data(root / "task_data.json")
    rubric_task_data_path = (
        Path(args.rubric_task_data).resolve()
        if args.rubric_task_data
        else root / "task_data.json"
    )
    rubric_task_data = _load_task_data(rubric_task_data_path)
    trajectory, input_dict, parsed = preflight_dom_diff_text_bundle(
        root,
        task_data,
        require_frozen_rubric=False,
    )
    del trajectory
    frames = compact_text_frames(
        parsed,
        max_chunk_tokens=args.text_max_chunk_tokens,
        model=args.judge_model,
    )
    compact = [frame.compact for frame in frames]
    rubric = _diagnostic_rubric(rubric_task_data)
    task = str(input_dict["task"])
    predicted_output = str(input_dict.get("predicted_output") or "")
    init_url_context = MMRubricAgent._get_init_url_context(
        str(input_dict.get("init_url") or "")
    )
    action_history = str(input_dict.get("action_history") or "")
    estimator = TokenEstimator(args.judge_model)

    relevance_scores = local_relevance_scores(
        compact,
        rubric,
        task=task,
        predicted_output=predicted_output,
    )
    selected = {
        criterion_idx: sorted(
            range(len(compact)),
            key=lambda index: (-relevance_scores[index][criterion_idx], index),
        )[: args.max_evidence_per_criterion]
        for criterion_idx in range(len(rubric["items"]))
    }

    rubric_text = _rubric_text(rubric)
    def render_relevance_prompt(evidence: str) -> str:
        return TEXT_BATCHED_RELEVANCE_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            text_frames=evidence,
            rubric_criteria=rubric_text,
            grounding_rules=DOM_DIFF_TEXT_GROUNDING_RULES,
        )

    criteria_block = _criteria_block(rubric)
    def render_analysis_prompt(evidence: str) -> str:
        return TEXT_PACKED_ANALYSIS_PROMPT.substitute(
            task_definition=task,
            init_url_context=init_url_context,
            action_history=action_history,
            agent_predicted_output=predicted_output,
            packed_evidence=evidence,
            criteria_info_block=criteria_block,
            grounding_rules=DOM_DIFF_TEXT_GROUNDING_RULES,
        )

    relevance_empty_tokens = estimator.count(render_relevance_prompt(""))
    analysis_empty_tokens = estimator.count(render_analysis_prompt(""))
    relevance = render_batched_relevance_evidence(
        compact,
        rubric,
        task=task,
        predicted_output=predicted_output,
        starting_target_tokens=args.text_trajectory_starting_tokens,
        model_context_window_tokens=args.text_model_context_window_tokens,
        completion_reserve_tokens=args.text_relevance_completion_reserve_tokens,
        prompt_headroom_tokens=args.text_prompt_headroom_tokens,
        fixed_prompt_tokens=relevance_empty_tokens,
        model=args.judge_model,
    )
    analysis = render_packed_analysis_evidence(
        compact,
        selected,
        rubric,
        predicted_output=predicted_output,
        task=task,
        starting_target_tokens=args.text_analysis_starting_tokens,
        model_context_window_tokens=args.text_model_context_window_tokens,
        completion_reserve_tokens=args.text_analysis_completion_reserve_tokens,
        prompt_headroom_tokens=args.text_prompt_headroom_tokens,
        fixed_prompt_tokens=analysis_empty_tokens,
        model=args.judge_model,
    )

    results: dict[str, Any] = {}
    for cap in args.caps:
        cap_dir = output_root / f"{cap // 1000}k"
        cap_dir.mkdir(parents=True, exist_ok=True)
        capped_relevance = apply_s3_prompt_cap(
            relevance,
            compact,
            stage="relevance",
            total_prompt_cap_tokens=cap,
            empty_prompt_tokens=relevance_empty_tokens,
            render_prompt=render_relevance_prompt,
            model=args.judge_model,
        )
        capped_analysis = apply_s3_prompt_cap(
            analysis,
            compact,
            stage="analysis",
            total_prompt_cap_tokens=cap,
            empty_prompt_tokens=analysis_empty_tokens,
            render_prompt=render_analysis_prompt,
            model=args.judge_model,
        )
        (cap_dir / "relevance_evidence.txt").write_text(
            capped_relevance.text + "\n", encoding="utf-8"
        )
        (cap_dir / "analysis_evidence.txt").write_text(
            capped_analysis.text + "\n", encoding="utf-8"
        )
        receipts = {
            "relevance": capped_relevance.experimental_s3_cap_receipt,
            "analysis": capped_analysis.experimental_s3_cap_receipt,
            "criterion_frame_assignments": {
                str(key): list(value)
                for key, value in sorted(
                    (capped_analysis.criterion_frame_assignments or {}).items()
                )
            },
        }
        receipt_path = cap_dir / "receipts.json"
        receipt_path.write_text(
            json.dumps(receipts, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        results[str(cap)] = {
            **receipts,
            "artifacts": {
                "relevance_evidence": str(cap_dir / "relevance_evidence.txt"),
                "analysis_evidence": str(cap_dir / "analysis_evidence.txt"),
                "receipts": str(receipt_path),
            },
        }

    summary = {
        "task_folder": root.name,
        "rubric_task_data": str(rubric_task_data_path),
        "judge_calls": 0,
        "selection_source": (
            "deterministic local_relevance_scores for offline analysis packing; "
            "the production LLM relevance matrix/top-K path is unchanged"
        ),
        "caps": list(args.caps),
        "frame_count": len(frames),
        "criterion_count": len(rubric["items"]),
        "selected_frames": {str(key): value for key, value in selected.items()},
        "base": {
            "relevance_evidence_tokens": relevance.estimated_tokens,
            "relevance_full_prompt_tokens": estimator.count(
                render_relevance_prompt(relevance.text)
            ),
            "analysis_evidence_tokens": analysis.estimated_tokens,
            "analysis_full_prompt_tokens": estimator.count(
                render_analysis_prompt(analysis.text)
            ),
            "relevance_records": len(relevance.model_records),
            "analysis_records": len(analysis.model_records),
            "relevance_static_prompt_tokens": relevance_empty_tokens,
            "analysis_static_prompt_tokens": analysis_empty_tokens,
        },
        "configurations": results,
    }
    summary_path = output_root / "summary.json"
    summary["summary_path"] = str(summary_path)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--rubric-task-data", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--caps", type=_parse_caps, default=(10000, 15000, 20000))
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--max-evidence-per-criterion", type=int, default=5)
    parser.add_argument("--text-max-chunk-tokens", type=int, default=256)
    parser.add_argument("--text-trajectory-starting-tokens", type=int, default=16000)
    parser.add_argument("--text-analysis-starting-tokens", type=int, default=24000)
    parser.add_argument("--text-model-context-window-tokens", type=int, default=128000)
    parser.add_argument("--text-relevance-completion-reserve-tokens", type=int, default=4096)
    parser.add_argument("--text-analysis-completion-reserve-tokens", type=int, default=8192)
    parser.add_argument("--text-prompt-headroom-tokens", type=int, default=1024)
    args = parser.parse_args(argv)
    for key, value in vars(args).items():
        if (key.endswith("tokens") or key == "max_evidence_per_criterion") and value <= 0:
            parser.error(f"--{key.replace('_', '-')} must be positive")
    return args


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    summary = build_diagnostics(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

