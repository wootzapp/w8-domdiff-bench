#!/usr/bin/env python3
"""Offline diagnostics for the raw DOM-diff grep/read evidence path."""

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

from webeval.oai_clients.wrapper import ChatCompletionClient
from webeval.rubric_agent.dom_diff_text_grep_agent import (
    DOMDiffTextGrepMMRubricAgent,
)
from webeval.rubric_agent.dom_diff_text_grep_tools import (
    TOOL_SCHEMAS,
    GrepEvidenceExecutor,
    assert_no_raw_evidence_in_initial_payload,
)
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgentConfig

from verify_trajectories_dom_diff_text_grep import (
    _load_task_data,
    preflight_trajectory,
)


def _rubric(task_data: dict[str, Any]) -> dict[str, Any]:
    value = task_data["precomputed_rubric"]
    if isinstance(value, list):
        value = value[0]
    return value


def _sentinel(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    candidates = [line for line in lines if len(line) >= 24]
    return max(candidates, key=len) if candidates else (lines[0] if lines else "")


def diagnose(path: Path) -> dict[str, Any]:
    trajectory, task_data, input_dict = preflight_trajectory(path)
    counter = ChatCompletionClient()
    agent = DOMDiffTextGrepMMRubricAgent(
        config=MMRubricAgentConfig(
            o4mini_client=object(),
            gpt5_client=counter,
            evidence_mode="dom",
            dom_frame_char_budget=1,
            dom_context_char_budget=1,
            dom_global_transition_char_budget=1,
            action_definitions=input_dict["action_definitions"],
        )
    )
    frames = agent._load_dom_evidence(input_dict["dom_actions"])
    relevance_messages = agent.build_relevance_initial_messages(
        _rubric(task_data),
        input_dict["task"],
        agent._get_init_url_context(input_dict.get("init_url")),
    )
    sentinel = _sentinel(agent.raw_bundle.files[0].path)
    payload = {"messages": relevance_messages, "tools": TOOL_SCHEMAS}
    assert_no_raw_evidence_in_initial_payload(
        payload, agent.raw_bundle, sentinels=[sentinel]
    )
    executor = GrepEvidenceExecutor(agent.raw_bundle)
    grep_result = executor.grep_evidence(
        query="status",
        file_ids=[],
        mode="literal",
        case_sensitive=False,
        context_before=1,
        context_after=1,
        match_offset=0,
        max_matches=10,
    )
    read_result = executor.read_file(
        file_id=agent.raw_bundle.files[0].file_id,
        start_line=1,
        end_line=min(5, agent.raw_bundle.files[0].line_count),
        start_column=0,
    )
    return {
        "status": "ok",
        "task_id": path.name,
        "actions": len(trajectory.events),
        "frames": len(frames),
        "source_files": agent.raw_bundle.audit_metadata(),
        "initial_prompt_estimated_tokens": counter.count_tokens(
            messages=relevance_messages, tools=TOOL_SCHEMAS
        ),
        "zero_dom_in_initial_prompt": True,
        "grep_smoke": {
            "ok": grep_result["ok"],
            "matches_total": grep_result["matches_total"],
            "matches_returned": grep_result["matches_returned"],
        },
        "read_smoke": {
            "ok": read_result["ok"],
            "segments": len(read_result["segments"]),
            "complete": read_result["complete"],
        },
        "coverage": executor.coverage_receipt(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = diagnose(Path(args.input).resolve())
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
