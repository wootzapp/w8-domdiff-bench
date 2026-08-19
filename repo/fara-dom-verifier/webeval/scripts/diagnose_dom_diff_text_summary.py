#!/usr/bin/env python3
"""Offline diagnostics for the isolated DOM-text summary-S3 projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


_THIS = Path(__file__).resolve()
for _source_root in (_THIS.parent.parent / "src", _THIS.parent.parent.parent / "src"):
    _source = str(_source_root)
    if _source not in sys.path:
        sys.path.insert(0, _source)

from webeval.rubric_agent.dom_diff_summary_compaction import TokenEstimator
from webeval.rubric_agent.dom_diff_text_adapter import preflight_dom_diff_text_bundle
from webeval.rubric_agent.dom_diff_text_summary_projection import (
    aggregate_text_summary_projection_metrics,
    project_text_summary_frames,
)
from webeval.rubric_agent.dom_diff_text_summary_prompts import (
    DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
    TEXT_SUMMARY_BATCHED_RELEVANCE_PROMPT,
    TEXT_SUMMARY_PACKED_ANALYSIS_PROMPT,
)
from webeval.rubric_agent.dom_diff_text_summary_rendering import (
    render_batched_text_summary_relevance_evidence,
    render_packed_text_summary_analysis_evidence,
)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"Expected one object in {path}")
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _rubric(root: Path, task_data: dict[str, Any]) -> dict[str, Any]:
    value = task_data.get("precomputed_rubric")
    if value is None:
        sidecar = root / "task_data_with_canonical_rubric.json"
        if sidecar.is_file():
            value = _object(sidecar).get("precomputed_rubric")
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ValueError(
            "Offline diagnostics require a frozen rubric or canonical sidecar"
        )
    return value


def _rubric_text(rubric: dict[str, Any]) -> str:
    return "".join(
        f"\n{idx}. **{item['criterion']}**\n" f"   Description: {item['description']}\n"
        for idx, item in enumerate(rubric["items"])
    )


def _criteria_block(rubric: dict[str, Any]) -> str:
    output = ""
    for idx, item in enumerate(rubric["items"]):
        output += (
            f"\n**Criterion {idx}:** {item['criterion']}\n"
            f"**Description:** {item['description']}\n"
            f"**Max Points:** {item['max_points']}\n"
        )
        if "condition" in item:
            output += f"**CONDITIONAL:** {item['condition']}\n"
    return output


def diagnose(root: Path, *, sample_chars: int) -> dict[str, Any]:
    task_data = _object(root / "task_data.json")
    _, input_dict, parsed = preflight_dom_diff_text_bundle(
        root,
        task_data,
        require_frozen_rubric=False,
    )
    rubric = _rubric(root, task_data)
    frames = project_text_summary_frames(parsed, max_record_chars=600)
    compact = [frame.compact for frame in frames]
    estimator = TokenEstimator("gpt-5.2")
    rubric_text = _rubric_text(rubric)
    relevance_empty = TEXT_SUMMARY_BATCHED_RELEVANCE_PROMPT.substitute(
        task_definition=input_dict["task"],
        init_url_context=input_dict["init_url"],
        text_summary_frames="",
        rubric_criteria=rubric_text,
        grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
    )
    relevance_budget = 16000 - estimator.count(relevance_empty) - 64
    relevance = render_batched_text_summary_relevance_evidence(
        compact,
        token_budget=relevance_budget,
    )
    relevance_prompt = TEXT_SUMMARY_BATCHED_RELEVANCE_PROMPT.substitute(
        task_definition=input_dict["task"],
        init_url_context=input_dict["init_url"],
        text_summary_frames=relevance.text,
        rubric_criteria=rubric_text,
        grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
    )
    # Offline analysis uses the all-frame union. Runtime uses the actual shared
    # top-K output, which can only make the selected union equal or smaller.
    grouped = {index: list(range(len(frames))) for index in range(len(rubric["items"]))}
    criteria = _criteria_block(rubric)
    analysis_empty = TEXT_SUMMARY_PACKED_ANALYSIS_PROMPT.substitute(
        task_definition=input_dict["task"],
        init_url_context=input_dict["init_url"],
        action_history=input_dict["action_history"],
        agent_predicted_output=input_dict["predicted_output"],
        packed_evidence="",
        criteria_info_block=criteria,
        grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
    )
    analysis_budget = 24000 - estimator.count(analysis_empty) - 64
    analysis = render_packed_text_summary_analysis_evidence(
        compact,
        grouped,
        token_budget=analysis_budget,
    )
    analysis_prompt = TEXT_SUMMARY_PACKED_ANALYSIS_PROMPT.substitute(
        task_definition=input_dict["task"],
        init_url_context=input_dict["init_url"],
        action_history=input_dict["action_history"],
        agent_predicted_output=input_dict["predicted_output"],
        packed_evidence=analysis.text,
        criteria_info_block=criteria,
        grounding_rules=DOM_DIFF_TEXT_SUMMARY_GROUNDING_RULES,
    )
    return {
        "task": root.name,
        "projection": aggregate_text_summary_projection_metrics(compact),
        "relevance": {
            "full_prompt_cap_tokens": 16000,
            "empty_prompt_tokens": estimator.count(relevance_empty),
            "reserve_tokens": 64,
            "evidence_budget_tokens": relevance_budget,
            "starting_per_frame_allowance_tokens": (
                relevance.starting_per_frame_allowance_tokens
            ),
            "per_frame_allowance_tokens": relevance.per_frame_allowance_tokens,
            "evidence_tokens": relevance.estimated_tokens,
            "full_prompt_tokens": estimator.count(relevance_prompt),
            "records_omitted_by_budget": relevance.records_omitted_by_budget,
            "sample": relevance.text[:sample_chars],
        },
        "analysis_all_frame_proxy": {
            "full_prompt_cap_tokens": 24000,
            "empty_prompt_tokens": estimator.count(analysis_empty),
            "reserve_tokens": 64,
            "evidence_budget_tokens": analysis_budget,
            "starting_per_frame_allowance_tokens": (
                analysis.starting_per_frame_allowance_tokens
            ),
            "per_frame_allowance_tokens": analysis.per_frame_allowance_tokens,
            "evidence_tokens": analysis.estimated_tokens,
            "full_prompt_tokens": estimator.count(analysis_prompt),
            "records_omitted_by_budget": analysis.records_omitted_by_budget,
            "sample": analysis.text[:sample_chars],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--sample-chars", type=int, default=2400)
    args = parser.parse_args()
    if args.sample_chars <= 0:
        parser.error("--sample-chars must be positive")
    print(
        json.dumps(
            diagnose(Path(args.input).resolve(), sample_chars=args.sample_chars),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
