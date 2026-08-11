#!/usr/bin/env python3
"""
Render ChromiumRL.captureStructuredSnapshot JSON as a full text inspection file.

Use this when you want to see the raw browser facts in a readable TXT form:
nodes, hierarchy, actions, attributes, states, bounds, visibility, hit testing,
tables/media-like nodes, and snapshot stats.

This is intentionally generic. It does not know about Slack, Google Docs,
Sheets, Amazon, or any task/environment-specific selectors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


TEXT_CONTAINER_TAGS = {
    "html",
    "body",
    "div",
    "main",
    "section",
    "article",
    "nav",
    "aside",
    "header",
    "footer",
    "form",
    "ul",
    "ol",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
}
TEXT_USEFUL_TAGS = {
    "a",
    "button",
    "caption",
    "dd",
    "dt",
    "figcaption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "img",
    "input",
    "label",
    "li",
    "option",
    "p",
    "pre",
    "select",
    "summary",
    "td",
    "textarea",
    "th",
}
COMMON_MOJIBAKE_REPLACEMENTS = {
    "â€¢": "•",
    "â€“": "–",
    "â€”": "—",
    "â€˜": "‘",
    "â€™": "’",
    "â€œ": "“",
    "â€\u009d": "”",
    "â€": "”",
    "Â ": " ",
    "Â": "",
}


def load_snapshot(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object")

    result = data.get("result")
    if isinstance(result, dict) and isinstance(result.get("snapshot"), dict):
        return result["snapshot"]
    if isinstance(data.get("snapshot"), dict):
        return data["snapshot"]
    if isinstance(data.get("nodes"), list):
        return data
    raise ValueError("Input does not contain result.snapshot, snapshot, or nodes[]")


def clean(value: Any, *, fix_mojibake: bool = True) -> str:
    text = "" if value is None else str(value)
    if fix_mojibake:
        for bad, good in COMMON_MOJIBAKE_REPLACEMENTS.items():
            text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text).strip()


def clip(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def norm_text_key(text: str) -> str:
    return re.sub(r"\W+", "", text.lower())


def attr_map(node: dict[str, Any]) -> dict[str, str]:
    attrs: dict[str, str] = {}
    raw = node.get("selectedAttributes", [])
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = clean(item.get("name"), fix_mojibake=False)
            value = clean(item.get("value"))
            if name:
                attrs[name] = value
    return attrs


def state_map(node: dict[str, Any]) -> dict[str, str]:
    states: dict[str, str] = {}
    raw = node.get("states", [])
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = clean(item.get("name"), fix_mojibake=False)
            value = clean(item.get("value"), fix_mojibake=False)
            if name:
                states[name] = value
    return states


def dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = clean(item, fix_mojibake=False)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def bounds_text(bounds: Any) -> str:
    if not isinstance(bounds, dict):
        return ""
    keys = ("x", "y", "width", "height")
    if not any(key in bounds for key in keys):
        return ""
    parts: list[str] = []
    for key in keys:
        value = bounds.get(key)
        if isinstance(value, (int, float)):
            parts.append(f"{key}={value:.1f}")
        elif value is not None:
            parts.append(f"{key}={value}")
    return "(" + " ".join(parts) + ")"


class FullSnapshotRenderer:
    def __init__(
        self,
        snapshot: dict[str, Any],
        *,
        max_text_chars: int,
        text_mode: str,
        include_suppressed_text_notes: bool,
        include_action_index: bool,
        include_child_refs: bool,
        include_text_nodes: bool,
        include_inert_wrappers: bool,
        include_diff: bool,
    ):
        self.snapshot = snapshot
        self.max_text_chars = max_text_chars
        self.text_mode = text_mode
        self.include_suppressed_text_notes = include_suppressed_text_notes
        self.include_action_index = include_action_index
        self.include_child_refs = include_child_refs
        self.include_text_nodes = include_text_nodes
        self.include_inert_wrappers = include_inert_wrappers
        self.include_diff = include_diff
        self.nodes = [node for node in snapshot.get("nodes", []) if isinstance(node, dict)]
        self.by_ref = {
            str(node.get("ref")): node
            for node in self.nodes
            if node.get("ref") is not None
        }
        self.children: dict[str, list[dict[str, Any]]] = {}
        for node in self.nodes:
            parent = node.get("parentRef")
            if parent is not None:
                self.children.setdefault(str(parent), []).append(node)
        for siblings in self.children.values():
            siblings.sort(key=self.source_order)

        self.action_map: dict[int, list[str]] = {}
        for action in snapshot.get("actions", []) or []:
            if not isinstance(action, dict):
                continue
            try:
                index = int(action.get("index"))
            except Exception:
                continue
            self.action_map[index] = dedupe(action.get("actionTypes", []))
        self.printed_subtree_keys: set[str] = set()

    def source_order(self, node: dict[str, Any]) -> int:
        try:
            return int(node.get("sourceOrder", 0) or 0)
        except Exception:
            return 0

    def node_index(self, node: dict[str, Any]) -> int | None:
        try:
            return int(node.get("index"))
        except Exception:
            return None

    def action_types(self, node: dict[str, Any]) -> list[str]:
        own = dedupe(node.get("actionTypes", []) if isinstance(node.get("actionTypes"), list) else [])
        index = self.node_index(node)
        mapped = self.action_map.get(index, []) if index is not None else []
        return dedupe([*own, *mapped])

    def roots(self) -> list[dict[str, Any]]:
        root_refs = [str(ref) for ref in self.snapshot.get("roots", []) or []]
        roots = [self.by_ref[ref] for ref in root_refs if ref in self.by_ref]
        if roots:
            return roots
        return [node for node in self.nodes if not node.get("parentRef")]

    def primary_text(self, node: dict[str, Any], *, allow_subtree: bool = False) -> str:
        for key in ("accessibleName", "directText", "description"):
            value = clean(node.get(key))
            if value:
                return value
        if allow_subtree:
            value = clean(node.get("subtreeText"))
            if value:
                return value
        attrs = attr_map(node)
        for key in ("aria-label", "title", "placeholder", "alt", "value", "name", "href", "src"):
            if attrs.get(key):
                return attrs[key]
        return ""

    def bool_flag(self, node: dict[str, Any], key: str) -> str:
        value = node.get(key)
        if isinstance(value, bool):
            return "true" if value else "false"
        return "?"

    def render_header(self) -> list[str]:
        stats = self.snapshot.get("stats", {}) if isinstance(self.snapshot.get("stats"), dict) else {}
        lines = [
            "=== SNAPSHOT ===",
            f"url: {clean(self.snapshot.get('url'))}",
            f"title: {clean(self.snapshot.get('title'))}",
        ]
        if self.snapshot.get("snapshotId"):
            lines.append(f"snapshot_id: {clean(self.snapshot.get('snapshotId'), fix_mojibake=False)}")
        if self.snapshot.get("documentRevision") is not None:
            lines.append(f"document_revision: {self.snapshot.get('documentRevision')}")
        lines.append(f"nodes_returned: {len(self.nodes)}")
        lines.append(f"actions_returned: {len(self.snapshot.get('actions', []) or [])}")
        if stats:
            ordered = [
                "rawNodes",
                "returnedNodes",
                "textChars",
                "groups",
                "droppedHidden",
                "droppedOffscreen",
                "droppedDuplicate",
                "truncated",
            ]
            stat_text = " ".join(f"{key}={stats.get(key)}" for key in ordered if key in stats)
            lines.append(f"stats: {stat_text}")
        if self.snapshot.get("roots"):
            lines.append("roots: " + ", ".join(str(ref) for ref in self.snapshot.get("roots", [])))
        return lines

    def render_actions_index(self) -> list[str]:
        if not self.include_action_index:
            return []
        lines = ["=== ACTION INDEX ==="]
        rows: list[tuple[int, dict[str, Any], list[str]]] = []
        for node in self.nodes:
            actions = self.action_types(node)
            index = self.node_index(node)
            if actions and index is not None:
                rows.append((index, node, actions))
        rows.sort(key=lambda row: (row[0], self.source_order(row[1])))
        if not rows:
            lines.append("(none)")
            return lines
        for index, node, actions in rows:
            label = clip(self.primary_text(node), self.max_text_chars)
            ref = clean(node.get("ref"), fix_mojibake=False)
            tag = clean(node.get("tag"), fix_mojibake=False)
            role = clean(node.get("role"), fix_mojibake=False)
            flags = (
                f"visible={self.bool_flag(node, 'visible')} "
                f"viewport={self.bool_flag(node, 'inViewport')} "
                f"hit={self.bool_flag(node, 'hitTestable')} "
                f"occluded={self.bool_flag(node, 'occluded')}"
            )
            role_text = f" role={role}" if role else ""
            label_text = f' "{label}"' if label else ""
            lines.append(f"[{index}] ref={ref} <{tag}>{role_text} actions={','.join(actions)} {flags}{label_text}")
        return lines

    def has_children(self, node: dict[str, Any]) -> bool:
        ref = str(node.get("ref"))
        return bool(self.children.get(ref) or node.get("childRefs"))

    def node_tag(self, node: dict[str, Any]) -> str:
        return clean(node.get("tag"), fix_mojibake=False).lower()

    def node_role(self, node: dict[str, Any]) -> str:
        return clean(node.get("role"), fix_mojibake=False).lower()

    def node_boundary(self, node: dict[str, Any]) -> str:
        return clean(node.get("semanticBoundary"), fix_mojibake=False).lower()

    def is_broad_container(self, node: dict[str, Any]) -> bool:
        tag = self.node_tag(node)
        role = self.node_role(node)
        return tag in TEXT_CONTAINER_TAGS and tag not in TEXT_USEFUL_TAGS and role not in {
            "button",
            "checkbox",
            "combobox",
            "heading",
            "link",
            "menuitem",
            "option",
            "radio",
            "searchbox",
            "textbox",
        }

    def should_print_text_fields(self, node: dict[str, Any]) -> bool:
        if self.text_mode == "none":
            return False
        tag = self.node_tag(node)
        if tag == "#text":
            return self.include_text_nodes
        if self.has_explicit_text_fact(node):
            return True
        if tag in TEXT_USEFUL_TAGS:
            return True
        if self.node_boundary(node):
            return True
        if self.action_types(node):
            return True
        if self.node_role(node) in {"heading", "link", "button", "textbox", "searchbox", "cell", "rowheader", "columnheader"}:
            return True
        if not self.has_children(node):
            return True
        return False

    def has_explicit_text_fact(self, node: dict[str, Any]) -> bool:
        return bool(
            clean(node.get("accessibleName"))
            or clean(node.get("description"))
            or clean(node.get("directText"))
        )

    def is_inert_wrapper(self, node: dict[str, Any]) -> bool:
        if self.include_inert_wrappers:
            return False
        tag = self.node_tag(node)
        if tag not in {"div", "span"}:
            return False
        if self.action_types(node):
            return False
        if state_map(node):
            return False
        if self.node_boundary(node):
            return False
        if self.node_role(node) not in {"", "generic", "none"}:
            return False
        if self.has_explicit_text_fact(node):
            return False
        attrs = attr_map(node)
        meaningful_attrs = {
            key: value
            for key, value in attrs.items()
            if key
            not in {
                "aria-describedby",
                "aria-hidden",
                "class",
                "data-qa",
                "data-testid",
                "id",
                "role",
                "style",
            }
        }
        if any(key in meaningful_attrs for key in ("href", "src", "alt", "title", "placeholder", "value", "name")):
            return False
        if "aria-label" in meaningful_attrs and not self.has_children(node):
            return False
        return True

    def should_print_subtree_text(self, node: dict[str, Any], subtree_text: str, already_printed: list[str]) -> tuple[bool, str]:
        if self.text_mode == "all":
            return True, ""
        if self.text_mode == "none":
            return False, "disabled_by_text_mode"

        tag = self.node_tag(node)
        role = self.node_role(node)
        boundary = self.node_boundary(node)
        actions = self.action_types(node)
        has_children = self.has_children(node)
        subtree_key = norm_text_key(subtree_text)

        if not subtree_key:
            return False, "empty"
        for existing in already_printed:
            if subtree_key == norm_text_key(existing):
                return False, "same_as_other_text_field"
        if subtree_key in self.printed_subtree_keys:
            return False, "duplicate_subtree_text"

        is_useful_text_node = tag in TEXT_USEFUL_TAGS or boundary in {"listitem"} or role in {"heading", "link", "button", "textbox", "searchbox"}
        is_broad_container = self.is_broad_container(node)

        if has_children and is_broad_container and not boundary and not actions:
            return False, "ancestor_container"
        if has_children and is_broad_container and actions == ["scroll"]:
            return False, "scroll_container"
        if has_children and len(subtree_text) > self.max_text_chars and not is_useful_text_node:
            return False, "large_parent_subtree"

        return True, ""

    def render_node_line(self, node: dict[str, Any], depth: int) -> list[str]:
        indent = "  " * depth
        ref = clean(node.get("ref"), fix_mojibake=False)
        index = self.node_index(node)
        tag = clean(node.get("tag"), fix_mojibake=False) or "?"
        role = clean(node.get("role"), fix_mojibake=False)
        actions = self.action_types(node)
        attrs = attr_map(node)
        states = state_map(node)
        bits = [f"ref={ref}"]
        if index is not None:
            bits.append(f"index={index}")
        bits.append(f"<{tag}>")
        if role:
            bits.append(f"role={role}")
        if node.get("semanticBoundary"):
            bits.append(f"boundary={clean(node.get('semanticBoundary'), fix_mojibake=False)}")
        if node.get("repeatedGroupId"):
            group = clean(node.get("repeatedGroupId"), fix_mojibake=False)
            if node.get("repeatedItemIndex") is not None:
                group += f"[{node.get('repeatedItemIndex')}]"
            bits.append(f"group={group}")
        if actions:
            bits.append(f"actions={','.join(actions)}")
        bits.append(f"visible={self.bool_flag(node, 'visible')}")
        bits.append(f"viewport={self.bool_flag(node, 'inViewport')}")
        bits.append(f"hit={self.bool_flag(node, 'hitTestable')}")
        bits.append(f"occluded={self.bool_flag(node, 'occluded')}")
        bits.append(f"scroll={self.bool_flag(node, 'scrollable')}")
        if node.get("confidence") is not None:
            bits.append(f"confidence={node.get('confidence')}")
        if node.get("truncated") is not None:
            bits.append(f"truncated={self.bool_flag(node, 'truncated')}")
        bounds = bounds_text(node.get("bounds"))
        if bounds:
            bits.append(f"bounds={bounds}")
        clipped = bounds_text(node.get("clippedBounds"))
        if clipped and clipped != bounds:
            bits.append(f"clipped={clipped}")

        lines = [indent + "- " + " ".join(bits)]
        printed_values: list[str] = []
        if self.should_print_text_fields(node):
            for key, label in (
                ("accessibleName", "name"),
                ("description", "description"),
                ("directText", "direct_text"),
            ):
                value = clean(node.get(key))
                if value and norm_text_key(value) not in {norm_text_key(existing) for existing in printed_values}:
                    lines.append(f"{indent}  {label}: {clip(value, self.max_text_chars)}")
                    printed_values.append(value)
            subtree_text = clean(node.get("subtreeText"))
            if subtree_text:
                should_print, suppressed_reason = self.should_print_subtree_text(node, subtree_text, printed_values)
                if should_print:
                    lines.append(f"{indent}  subtree_text: {clip(subtree_text, self.max_text_chars)}")
                    key = norm_text_key(subtree_text)
                    if key:
                        self.printed_subtree_keys.add(key)
                elif self.include_suppressed_text_notes:
                    lines.append(
                        f"{indent}  subtree_text: [suppressed reason={suppressed_reason} chars={len(subtree_text)}]"
                    )
        if attrs:
            attr_text = " ".join(f"{key}={json.dumps(value, ensure_ascii=False)}" for key, value in attrs.items())
            lines.append(f"{indent}  attrs: {attr_text}")
        if states:
            state_text = " ".join(f"{key}={value}" for key, value in states.items())
            lines.append(f"{indent}  states: {state_text}")
        children = [str(ref) for ref in node.get("childRefs", []) or []]
        if self.include_child_refs and children:
            lines.append(f"{indent}  child_refs: {', '.join(children)}")
        return lines

    def render_tree(self) -> list[str]:
        lines = ["=== NODE TREE ==="]
        seen: set[str] = set()

        def walk(node: dict[str, Any], depth: int) -> None:
            ref = str(node.get("ref"))
            if self.node_tag(node) == "#text" and not self.include_text_nodes:
                return
            if ref in seen:
                lines.append("  " * depth + f"- ref={ref} [already shown]")
                return
            seen.add(ref)
            if self.is_inert_wrapper(node):
                for child in self.children.get(ref, []):
                    walk(child, depth)
                return
            lines.extend(self.render_node_line(node, depth))
            for child in self.children.get(ref, []):
                walk(child, depth + 1)

        for root in self.roots():
            walk(root, 0)

        missing = [node for node in self.nodes if str(node.get("ref")) not in seen]
        if missing:
            lines.append("=== UNREACHED NODES ===")
            for node in sorted(missing, key=self.source_order):
                if self.node_tag(node) == "#text" and not self.include_text_nodes:
                    continue
                if self.is_inert_wrapper(node):
                    continue
                lines.extend(self.render_node_line(node, 0))
        return lines

    def render_diff(self) -> list[str]:
        if not self.include_diff or not isinstance(self.snapshot.get("diff"), dict):
            return []
        return ["=== DIFF ===", json.dumps(self.snapshot["diff"], ensure_ascii=False, indent=2)]

    def render(self) -> str:
        sections = [
            self.render_header(),
            self.render_actions_index(),
            self.render_tree(),
            self.render_diff(),
        ]
        return "\n\n".join("\n".join(section) for section in sections if section).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a ChromiumRL structured snapshot as full TXT")
    parser.add_argument("input", type=Path, help="Input structured snapshot JSON")
    parser.add_argument("-o", "--output", type=Path, help="Optional output TXT path")
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=1200,
        help="Maximum text chars per field; use 0 for no clipping",
    )
    parser.add_argument(
        "--text-mode",
        choices=("deduped", "all", "none"),
        default="deduped",
        help=(
            "How to render subtreeText. deduped keeps useful unique text and suppresses "
            "ancestor/container repeats; all prints raw subtreeText everywhere; none hides subtreeText."
        ),
    )
    parser.add_argument(
        "--include-suppressed-text-notes",
        action="store_true",
        help="Show one-line notes when subtreeText is suppressed in deduped mode",
    )
    parser.add_argument(
        "--include-action-index",
        action="store_true",
        help="Also print a separate action index. By default actions are shown only on their tree nodes.",
    )
    parser.add_argument(
        "--include-child-refs",
        action="store_true",
        help="Print raw childRefs arrays. By default hierarchy indentation already shows children.",
    )
    parser.add_argument(
        "--include-text-nodes",
        action="store_true",
        help="Print raw #text nodes. By default parent text fields carry readable text.",
    )
    parser.add_argument(
        "--include-inert-wrappers",
        action="store_true",
        help="Print inert div/span wrapper nodes. By default they are collapsed and their children are shown.",
    )
    parser.add_argument("--include-diff", action="store_true", help="Include snapshot.diff JSON if present")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rendered = FullSnapshotRenderer(
        load_snapshot(args.input),
        max_text_chars=args.max_text_chars,
        text_mode=args.text_mode,
        include_suppressed_text_notes=args.include_suppressed_text_notes,
        include_action_index=args.include_action_index,
        include_child_refs=args.include_child_refs,
        include_text_nodes=args.include_text_nodes,
        include_inert_wrappers=args.include_inert_wrappers,
        include_diff=args.include_diff,
    ).render()
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        try:
            sys.stdout.write(rendered)
        except BrokenPipeError:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
