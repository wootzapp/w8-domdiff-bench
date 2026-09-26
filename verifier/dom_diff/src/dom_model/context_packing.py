"""Deterministic record-boundary packing for oversized DOM-model states."""

from __future__ import annotations

import json
import re
from typing import Any

from .schemas import DomModelState


MANDATORY = re.compile(
    r"^(?:URL|Title|Snapshot):|\b(?:dialog|alert|error|validation|truncat(?:ed|ion))\b",
    re.I | re.M,
)


def pack_state(
    state: DomModelState, *, action_count: int, max_chars: int
) -> tuple[str, list[dict[str, Any]]]:
    """Pack source-ordered records, never silently dropping a partial record."""
    complete = state.model_text(action_count=action_count)
    if max_chars <= 0 or len(complete) <= max_chars:
        return complete, []
    prefix, _ = complete.split("\n\n", 1)
    prefix += "\n\n"
    lines = state.raw_text.splitlines(keepends=True)
    blocks: list[tuple[int, int, str]] = []
    current_start = 1
    current: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        begins_record = bool(line.strip()) and (
            not line[:1].isspace() or line.lstrip().startswith(("- ", "* ", "|"))
        )
        if begins_record and current:
            blocks.append((current_start, line_number - 1, "".join(current)))
            current = []
            current_start = line_number
        current.append(line)
    if current:
        blocks.append((current_start, len(lines), "".join(current)))

    selected = {
        index for index, (_, _, block) in enumerate(blocks) if MANDATORY.search(block)
    }
    used = len(prefix) + sum(len(blocks[index][2]) for index in selected)
    for index, (_, _, block) in enumerate(blocks):
        if index not in selected and used + len(block) <= max_chars:
            selected.add(index)
            used += len(block)
    omissions = [
        {
            "state_index": state.index,
            "start_line": start,
            "end_line": end,
            "provenance": f"m{state.index}:L{start}-L{end}",
            "char_count": len(block),
            "estimated_tokens": (len(block) + 3) // 4,
            "reason": "state_exceeds_context_budget",
        }
        for index, (start, end, block) in enumerate(blocks)
        if index not in selected
    ]
    rendered = prefix + "".join(
        block for index, (_, _, block) in enumerate(blocks) if index in selected
    )
    rendered += (
        "\nDOM_MODEL_CONTEXT_OMISSIONS: "
        + json.dumps(omissions, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )
    return rendered, omissions
