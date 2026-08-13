#!/usr/bin/env python3
"""Offline parser/compaction/retrieval diagnostic for refined DOM-diff text."""

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

from webeval.rubric_agent.dom_diff_text_adapter import preflight_dom_diff_text_bundle
from webeval.rubric_agent.dom_diff_text_compaction import (
    aggregate_text_compaction_metrics,
    build_trajectory_ledger,
    compact_text_frames,
)
from webeval.rubric_agent.dom_diff_text_retrieval import (
    local_relevance_scores,
    render_batched_relevance_evidence,
    render_packed_analysis_evidence,
)


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
    if isinstance(rubric, dict) and isinstance(rubric.get("items"), list):
        return rubric
    # This is retrieval diagnostics only, not rubric generation or scoring.
    return {
        "items": [
            {
                "criterion": "Task-relevant explicit page-state evidence",
                "description": str(
                    task_data.get("question") or task_data.get("confirmed_task") or ""
                ),
                "max_points": 1,
            }
        ]
    }


def build_diagnostic(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.input).resolve()
    task_data = _load_task_data(root / "task_data.json")
    trajectory, input_dict, parsed = preflight_dom_diff_text_bundle(
        root,
        task_data,
        require_frozen_rubric=False,
    )
    frames = compact_text_frames(
        parsed,
        max_chunk_tokens=args.text_max_chunk_tokens,
        model=args.judge_model,
    )
    compact = [frame.compact for frame in frames]
    rubric = _diagnostic_rubric(task_data)
    task = str(task_data.get("question") or task_data.get("confirmed_task") or "")
    predicted_output = trajectory.final_answer
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
    relevance = render_batched_relevance_evidence(
        compact,
        rubric,
        task=task,
        predicted_output=predicted_output,
        starting_target_tokens=args.text_trajectory_starting_tokens,
        model_context_window_tokens=args.text_model_context_window_tokens,
        completion_reserve_tokens=args.text_relevance_completion_reserve_tokens,
        prompt_headroom_tokens=args.text_prompt_headroom_tokens,
        fixed_prompt_tokens=args.fixed_relevance_prompt_tokens,
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
        fixed_prompt_tokens=args.fixed_analysis_prompt_tokens,
        model=args.judge_model,
    )
    ledger = build_trajectory_ledger(compact)
    return {
        "requested_evidence_mode": "dom_diff_text",
        "task_folder": root.name,
        "actions": len(input_dict.get("dom_actions") or []),
        "frames": len(frames),
        "source_hashes": [frame.source_sha256 for frame in frames],
        "snapshot_chain_complete": all(
            frames[index].after_identity == frames[index + 1].before_identity
            for index in range(len(frames) - 1)
        ),
        "compaction": aggregate_text_compaction_metrics(compact),
        "ledger_records": len(ledger.records),
        "relevance_scores": relevance_scores,
        "selected_frames": {str(key): value for key, value in selected.items()},
        "relevance_pack": relevance.to_dict(),
        "analysis_pack": analysis.to_dict(),
        "source_audit_receipts": [frame.audit.to_dict() for frame in frames],
        "compaction_receipts": [frame.compact.receipt.to_dict() for frame in frames],
    }


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--max-evidence-per-criterion", type=int, default=5)
    parser.add_argument("--text-max-chunk-tokens", type=int, default=256)
    parser.add_argument("--text-trajectory-starting-tokens", type=int, default=16000)
    parser.add_argument("--text-analysis-starting-tokens", type=int, default=24000)
    parser.add_argument("--text-model-context-window-tokens", type=int, default=128000)
    parser.add_argument("--text-relevance-completion-reserve-tokens", type=int, default=4096)
    parser.add_argument("--text-analysis-completion-reserve-tokens", type=int, default=8192)
    parser.add_argument("--text-prompt-headroom-tokens", type=int, default=1024)
    parser.add_argument("--fixed-relevance-prompt-tokens", type=int, default=2000)
    parser.add_argument("--fixed-analysis-prompt-tokens", type=int, default=4000)
    args = parser.parse_args(argv)
    for key, value in vars(args).items():
        if (key.endswith("tokens") or key == "max_evidence_per_criterion") and value <= 0:
            parser.error(f"--{key.replace('_', '-')} must be positive")
    return args


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    diagnostic = build_diagnostic(args)
    text = json.dumps(diagnostic, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
