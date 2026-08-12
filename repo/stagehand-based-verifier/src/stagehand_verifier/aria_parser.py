from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from .schemas import AriaNode


ARIA_LINE = re.compile(
    r"^(?P<indent>\s*)\[(?P<reference>[^\]]+)\]\s+"
    r"(?P<role>[^:]+?)(?::\s*(?P<name>.*))?$"
)
STATE_WORDS = (
    "checked",
    "selected",
    "expanded",
    "collapsed",
    "disabled",
    "pressed",
    "required",
    "readonly",
    "focused",
    "invalid",
)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _semantic_key(
    role: str,
    name: str,
    parents: tuple[str, ...],
    occurrence: int,
) -> str:
    payload = "|".join((*parents, _normalize(role), _normalize(name), str(occurrence)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def parse_aria_tree(text: str) -> tuple[tuple[AriaNode, ...], tuple[str, ...]]:
    """Parse Stagehand's indentation-based ARIA text without discarding unknown lines."""
    nodes: list[AriaNode] = []
    unparsed: list[str] = []
    stack: list[tuple[int, str]] = []
    occurrences: defaultdict[tuple[tuple[str, ...], str, str], int] = defaultdict(int)

    for raw in text.splitlines():
        if not raw.strip():
            continue
        match = ARIA_LINE.match(raw)
        if match is None:
            unparsed.append(raw)
            continue
        indent = len(match.group("indent").expandtabs(2))
        depth = indent // 2
        role = match.group("role").strip()
        name = (match.group("name") or "").strip()

        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent_context = tuple(label for _, label in stack[-4:])
        identity = (parent_context, _normalize(role), _normalize(name))
        occurrence = occurrences[identity]
        occurrences[identity] += 1
        states = tuple(word for word in STATE_WORDS if re.search(rf"\b{word}\b", name, re.I))
        key = _semantic_key(role, name, parent_context, occurrence)
        node = AriaNode(
            raw_reference=match.group("reference").strip(),
            semantic_key=key,
            depth=depth,
            role=role,
            accessible_name=name,
            text=name,
            states=states,
            parent_context=parent_context,
            source_line=raw.strip(),
        )
        nodes.append(node)
        stack.append((depth, f"{role}:{name}" if name else role))
    return tuple(nodes), tuple(unparsed)

