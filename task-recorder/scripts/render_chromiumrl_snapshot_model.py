#!/usr/bin/env python3
"""
Render ChromiumRL.captureStructuredSnapshot JSON as model-facing context.

This is the merged/clean renderer for task environments:
  - keeps tables and readable content;
  - groups useful nested controls under the content item they belong to;
  - separates primary actions from secondary/debug actions using generic facts;
  - preserves href/src/alt/title/aria labels as labels, without app-specific code.

This renderer uses only generic facts present in the structured snapshot.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


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

CONTENT_TAGS = {
    "article",
    "blockquote",
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
    "li",
    "p",
    "pre",
    "summary",
}
TABLE_TAGS = {"table", "thead", "tbody", "tfoot", "tr", "td", "th"}
MEDIA_TAGS = {"img", "picture", "video", "audio", "canvas"}
BROAD_CONTAINER_TAGS = {"html", "body", "main", "section", "article", "div"}
# A role-less text node at or below this length that repeats an interactive
# element's label is treated as chrome rather than page content.
CHROME_LABEL_MAX_CHARS = 40
# Renderer limits below bound model-facing context only. The raw dom.json and
# full renderer remain available, and every hidden section reports its count.
LOW_VALUE_LABELS = {
    "",
    "toggle",
    "more",
    "menu",
}
LOW_VALUE_CONTEXT_LABELS = {
    "",
    "document",
    "generic",
    "group",
    "home",
    "jump to date",
    "list",
    "listitem",
    "main",
    "none",
    "tabpanel",
    "toolbar",
}
LOW_VALUE_CONTENT_RE = re.compile(
    r"^(folder|new|loading|loading[ .…]*|loading history[ .…]*|shift \+ return|"
    r"last updated\b.*|press ctrl\b.*)$",
    re.I,
)
CONTROL_WORDS = re.compile(
    r"\b(open|view|show|expand|details|more|download|submit|send|search|load|"
    r"toggle|next|previous|change|dismiss|close|sign in|reply|replies|"
    r"thread|comment|comments|file|attachment)\b",
    re.I,
)
ESSENTIAL_ACTION_WORDS = re.compile(
    r"\b(search|load|submit|send|save|dismiss|close|change|continue|next|previous|"
    r"open|download|upload)\b",
    re.I,
)
LOW_VALUE_NESTED_LABEL_PATTERNS = (
    # Labels with no alphanumeric content carry no information for the model.
    re.compile(r"^[^A-Za-z0-9]+$"),
    # Inline metadata links are usually context, not the main thing to act on.
    # They still remain in raw snapshots/full debug output.
    re.compile(r"^@\S+$"),
    re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s*(AM|PM)?$", re.I),
    re.compile(r"^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}(?:\s+at\b.*)?$", re.I),
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_LABEL_ATTR_RE = re.compile(r"""\b(?:aria-label|alt|title)=["']([^"']+)["']""", re.I)
MEDIA_FILE_RE = re.compile(r"\.(?:pdf|docx?|xlsx?|pptx?|csv|txt|png|jpe?g|gif|webp|svg)\b", re.I)
ATTACHMENT_FILE_TOKEN_RE = re.compile(
    r"(?<![\w.-])[\w@()+.-]+\.(?:pdf|docx?|xlsx?|pptx?|csv|txt|png|jpe?g|gif|webp|svg)\b",
    re.I,
)
ATTACHMENT_SPACED_FILE_RE = re.compile(
    r"(?<![\w.-])[\w@()+.-]+(?:\s+-\s+[\w@()+.-]+)+"
    r"\.(?:pdf|docx?|xlsx?|pptx?|csv|txt|png|jpe?g|gif|webp|svg)\b",
    re.I,
)
MESSAGE_PREFIX_RE = re.compile(
    r"^(?P<author>[A-Z][A-Za-z0-9 ._'-]{1,80}?)\s+"
    r"(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM))\s+"
    r"(?P<body>.+)$",
    re.I,
)
THREAD_SUMMARY_RE = re.compile(
    r"\b(?P<count>\d+\s+repl(?:y|ies))"
    r"(?:\s+(?P<last>(?:Last reply\s+)?[^|]{1,50}?))?"
    r"\s+View thread\b",
    re.I,
)
REACTION_TOKEN_RE = re.compile(r"(?:\+1|👍|👀|🙏|🎉|🔥|✅|❌)$")


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load wrapped or bare structured-snapshot JSON and reject other shapes."""
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
    """Normalize captured text, HTML labels, entities, whitespace, and mojibake."""
    text = "" if value is None else str(value)
    if fix_mojibake:
        for bad, good in COMMON_MOJIBAKE_REPLACEMENTS.items():
            text = text.replace(bad, good)
    if "&" in text:
        text = html.unescape(text)
    if "<" in text and ">" in text:
        attr_labels = [html.unescape(match) for match in HTML_LABEL_ATTR_RE.findall(text)]
        stripped = HTML_TAG_RE.sub(" ", text)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if stripped:
            text = stripped
        elif attr_labels:
            text = " ".join(attr_labels)
    return re.sub(r"\s+", " ", text).strip()


def clip(text: str, limit: int) -> str:
    """Clip model-facing text with an ellipsis; non-positive limits are unlimited."""
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def norm_key(text: str) -> str:
    """Create a case-insensitive punctuation-free key for semantic deduplication."""
    return re.sub(r"\W+", "", text.lower())


def dedupe(items: Iterable[str]) -> list[str]:
    """Remove empty and repeated strings while preserving their first occurrence."""
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = clean(item, fix_mojibake=False)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def attr_map(node: dict[str, Any]) -> dict[str, str]:
    """Convert selectedAttributes records into a normalized lookup mapping."""
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


def bounds_text(bounds: Any) -> str:
    """Render available geometry fields for optional debug action context."""
    if not isinstance(bounds, dict):
        return ""
    x = bounds.get("x")
    y = bounds.get("y")
    w = bounds.get("width")
    h = bounds.get("height")
    if not any(value is not None for value in (x, y, w, h)):
        return ""
    return f"x={x} y={y} w={w} h={h}"


class ModelSnapshotRenderer:
    def __init__(
        self,
        snapshot: dict[str, Any],
        *,
        max_actions: int,
        max_secondary_actions: int,
        max_nested_actions: int,
        max_content_blocks: int,
        max_table_rows: int,
        max_media: int,
        max_scroll_regions: int = 16,
        max_cell_chars: int,
        max_text_chars: int,
        include_refs: bool,
        include_secondary: bool,
        include_offscreen_content: bool,
        suppress_authoring: bool = False,
        chrome_label_max_chars: int = CHROME_LABEL_MAX_CHARS,
    ):
        """Index the snapshot and configure explicit model-context budgets."""
        self.snapshot = snapshot
        self.max_actions = max_actions
        self.max_secondary_actions = max_secondary_actions
        self.max_nested_actions = max_nested_actions
        self.max_content_blocks = max_content_blocks
        self.max_table_rows = max_table_rows
        self.max_media = max_media
        self.max_scroll_regions = max_scroll_regions
        self.max_cell_chars = max_cell_chars
        self.max_text_chars = max_text_chars
        self.include_refs = include_refs
        self.include_secondary = include_secondary
        self.include_offscreen_content = include_offscreen_content
        self.suppress_authoring = suppress_authoring
        self.chrome_label_max_chars = int(chrome_label_max_chars)

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

        # Mark structurally repeated sibling branches. Many applications build
        # logical rows from role-less div/span trees instead of listitems. Text
        # deduplication must be scoped to one such branch so equal metadata in
        # separate rows is not mistaken for a duplicate.
        self.repeated_item_refs: set[str] = set()
        for siblings in self.children.values():
            by_signature: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
            for child in siblings:
                signature = (
                    clean(child.get("tag"), fix_mojibake=False).lower(),
                    clean(child.get("role"), fix_mojibake=False).lower(),
                    clean(child.get("semanticBoundary"), fix_mojibake=False).lower(),
                )
                by_signature.setdefault(signature, []).append(child)
            for repeated in by_signature.values():
                if len(repeated) < 2:
                    continue
                self.repeated_item_refs.update(
                    str(child.get("ref"))
                    for child in repeated
                    if child.get("ref") is not None
                )

        # Read-only tasks must not expose content-authoring widgets. Identify them
        # by ARIA role and DOM containment rather than by application-specific
        # names: an authoring field is a plain `textbox`, and its toolbar and send
        # controls sit under a shared ancestor. Walk up only while the subtree
        # stays free of content items, so the surrounding list is never swallowed.
        self.suppressed_refs: set[str] = set()
        if self.suppress_authoring:
            for node in self.nodes:
                role = clean(node.get("role"), fix_mojibake=False).lower()
                tag = clean(node.get("tag"), fix_mojibake=False).lower()
                if role != "textbox" or tag in {"input", "textarea"}:
                    continue
                container = node
                for _ in range(4):
                    parent_ref = container.get("parentRef")
                    parent = self.by_ref.get(str(parent_ref)) if parent_ref is not None else None
                    if not parent:
                        break
                    subtree = self.descendants(str(parent.get("ref")))
                    if any(
                        clean(self.by_ref[ref].get("role"), fix_mojibake=False).lower() == "listitem"
                        for ref in subtree
                        if ref in self.by_ref
                    ):
                        break
                    container = parent
                self.suppressed_refs.add(str(container.get("ref")))
                self.suppressed_refs.update(self.descendants(str(container.get("ref"))))

        self.action_map: dict[int, list[str]] = {}
        for action in snapshot.get("actions", []) or []:
            if not isinstance(action, dict):
                continue
            try:
                index = int(action.get("index"))
            except Exception:
                continue
            self.action_map[index] = dedupe(action.get("actionTypes", []))

        self.action_nodes = self.collect_action_nodes()
        self.action_labels: set[str] = {
            norm_key(self.text(node))
            for node, actions in self.action_nodes
            if actions != ["scroll"]
            and not self.is_broad_action(node, actions)
            and norm_key(self.text(node))
        }
        self.generated_action_ids: dict[str, str] = {}
        next_id = 1
        for node, _actions in self.action_nodes:
            ref = str(node.get("ref", ""))
            if self.node_index(node) is None and ref:
                self.generated_action_ids[ref] = f"A{next_id}"
                next_id += 1
        self.nested_actions_by_content_ref = self.group_nested_actions()
        self.rendered_content_refs: set[str] = set()
        self.rendered_content_text_keys: set[str] = set()

    def source_order(self, node: dict[str, Any]) -> int:
        """Return numeric document order, using zero for malformed input."""
        try:
            return int(node.get("sourceOrder", 0) or 0)
        except Exception:
            return 0

    def node_index(self, node: dict[str, Any]) -> int | None:
        """Return the capture index used for actions when it is numeric."""
        try:
            return int(node.get("index"))
        except Exception:
            return None

    def action_types(self, node: dict[str, Any]) -> list[str]:
        """Merge node-local and snapshot-level action declarations."""
        own = dedupe(node.get("actionTypes", []) if isinstance(node.get("actionTypes"), list) else [])
        index = self.node_index(node)
        mapped = self.action_map.get(index, []) if index is not None else []
        return dedupe([*own, *mapped])

    def action_id(self, node: dict[str, Any]) -> str:
        """Prefer stable backendNodeId, then capture index, then a synthetic id."""
        # Prefer the browser's stable per-node identifier. `index`/`ref` are the
        # node's position in the capture list, so inserting or removing any earlier
        # node renumbers everything after it: an agent reusing an id from the
        # previous observation lands one or two elements off. backendNodeId is
        # constant for the lifetime of the DOM node, so an id stays valid across
        # turns unless the element is genuinely destroyed.
        backend_node_id = node.get("backendNodeId")
        if backend_node_id not in (None, ""):
            try:
                return str(int(backend_node_id))
            except (TypeError, ValueError):
                pass
        index = self.node_index(node)
        if index is not None:
            return str(index)
        return self.generated_action_ids.get(str(node.get("ref", "")), "A?")

    def ancestors(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        """Walk parentRef links outward until the root or a missing parent."""
        out: list[dict[str, Any]] = []
        parent_ref = node.get("parentRef")
        while parent_ref is not None:
            parent = self.by_ref.get(str(parent_ref))
            if not parent:
                break
            out.append(parent)
            parent_ref = parent.get("parentRef")
        return out

    def descendants(self, ref: str) -> set[str]:
        """Collect descendant refs iteratively with cycle protection."""
        found: set[str] = set()
        stack = list(self.children.get(ref, []))
        while stack:
            node = stack.pop()
            node_ref = str(node.get("ref"))
            if node_ref in found:
                continue
            found.add(node_ref)
            stack.extend(self.children.get(node_ref, []))
        return found

    def text(self, node: dict[str, Any]) -> str:
        """Choose the richest own semantic text without exposing raw URLs."""
        # A node's own rendered text wins over an inherited accessible name.
        # Accessible names propagate up the AX tree, so a content row can end up
        # labelled by a descendant control (e.g. an avatar's hover label) and its
        # real text becomes invisible. Order: own text, then subtree text when it
        # carries more than the label does, then the label.
        direct = clean(node.get("directText"))
        accessible = clean(node.get("accessibleName"))
        subtree = clean(node.get("subtreeText"))
        # A captured directText value can itself be clipped or be only the
        # beginning of a richer subtree fact. Prefer the subtree only when it
        # demonstrably contains the direct fact; this preserves the protection
        # against unrelated inherited accessible names.
        if direct and subtree and len(subtree) > len(direct):
            direct_key = norm_key(direct)
            subtree_key = norm_key(subtree)
            if node.get("truncated") is True or (direct_key and direct_key in subtree_key):
                return subtree
        if direct:
            return direct
        if subtree and len(subtree) > len(accessible):
            return subtree
        for value in (accessible, subtree, clean(node.get("description"))):
            if value:
                return value
        attrs = attr_map(node)
        # `href`/`src` are deliberately absent: a URL is not a usable label, and
        # emitting one leaks permalinks and file/resource ids into the observation.
        for key in ("aria-label", "title", "placeholder", "alt", "value", "name"):
            value = clean(attrs.get(key))
            if value:
                return value
        return ""

    def node_tag(self, node: dict[str, Any]) -> str:
        """Return a normalized lowercase tag."""
        return clean(node.get("tag"), fix_mojibake=False).lower()

    def node_role(self, node: dict[str, Any]) -> str:
        """Return a normalized lowercase accessibility role."""
        return clean(node.get("role"), fix_mojibake=False).lower()

    def node_ref(self, node: dict[str, Any]) -> str:
        """Return the snapshot-local ref as text, or an empty string."""
        return str(node.get("ref", "") or "")

    def action_kind(self, node: dict[str, Any], actions: list[str]) -> str:
        """Classify raw action facts into a concise model-facing control kind."""
        tag = self.node_tag(node)
        role = self.node_role(node)
        attrs = attr_map(node)
        label = self.text(node).lower()
        if "type" in actions or role in {"textbox", "searchbox"} or tag in {"input", "textarea"}:
            return "text-input" if role != "searchbox" and "search" not in label else "search-input"
        if role in {"checkbox", "radio", "switch"} or "toggle" in actions:
            return "toggle"
        if role in {"combobox", "listbox"} or tag == "select" or "select" in actions:
            return "select"
        if "upload" in actions:
            return "file-upload"
        if tag == "a" or role == "link" or attrs.get("href"):
            return "link"
        if tag == "button" or role == "button":
            return "button"
        if "scroll" in actions and len(actions) == 1:
            return "scroll-region"
        if "click" in actions:
            return "clickable"
        return "action"

    def visibility_notes(self, node: dict[str, Any]) -> list[str]:
        """List captured visibility blockers without inferring absent flags."""
        notes: list[str] = []
        if node.get("visible") is False:
            notes.append("hidden")
        if node.get("inViewport") is False:
            notes.append("offscreen")
        if node.get("occluded") is True:
            notes.append("occluded")
        if node.get("hitTestable") is False:
            notes.append("not-hit-testable")
        return notes

    def compact_node_label(self, node: dict[str, Any], *, limit: int = 80) -> str:
        """Build a short semantic label for context headings and debug actions."""
        label = clean(node.get("accessibleName")) or clean(node.get("directText")) or clean(node.get("description"))
        if not label:
            attrs = attr_map(node)
            for key in ("aria-label", "title", "placeholder", "alt", "value", "name"):
                if attrs.get(key):
                    label = attrs[key]
                    break
        return clip(label, limit)

    def region_context(self, node: dict[str, Any], *, limit: int = 160) -> str:
        """Summarize up to three useful ancestors while skipping inert wrappers."""
        parts: list[str] = []
        seen: set[str] = set()
        for ancestor in self.ancestors(node):
            tag = self.node_tag(ancestor)
            role = self.node_role(ancestor)
            semantic = clean(ancestor.get("semanticBoundary"), fix_mojibake=False).lower()
            if tag in {"html", "body"}:
                continue
            if role in {"generic", "none", ""} and tag in {"div", "span"} and not semantic:
                continue
            label = self.compact_node_label(ancestor, limit=70)
            if not label and role:
                label = role
            if not label and tag:
                label = tag
            key = norm_key(f"{role}:{tag}:{label}")
            if not key or key in seen:
                continue
            seen.add(key)
            prefix = role or semantic or tag
            parts.append(f"{prefix}: {label}" if label else prefix)
            if len(parts) >= 3:
                break
        return clip(" / ".join(reversed(parts)), limit)

    def display_context(self, node: dict[str, Any], *, limit: int = 80) -> str:
        """Short context label for grouping, not a full ancestor trace."""
        for ancestor in self.ancestors(node):
            tag = self.node_tag(ancestor)
            role = self.node_role(ancestor)
            semantic = clean(ancestor.get("semanticBoundary"), fix_mojibake=False).lower()
            label = self.compact_node_label(ancestor, limit=limit)
            label_key = label.lower().strip()
            if label_key in LOW_VALUE_CONTEXT_LABELS:
                label = ""
            if label and role in {
                "alertdialog",
                "dialog",
                "group",
                "list",
                "main",
                "navigation",
                "search",
                "tabpanel",
                "toolbar",
                "tree",
            }:
                return clip(label, limit)
            if label and semantic in {"list", "section", "region"}:
                return clip(label, limit)
            if label and tag in {"article", "aside", "footer", "header", "main", "nav", "section"}:
                return clip(label, limit)
        return ""

    def has_ancestor_role_or_tag(self, node: dict[str, Any], values: set[str]) -> bool:
        """Check whether any ancestor tag or role belongs to a supplied set."""
        for ancestor in self.ancestors(node):
            if self.node_tag(ancestor) in values or self.node_role(ancestor) in values:
                return True
        return False

    def is_low_value_content_text(self, text: str) -> bool:
        """Recognize generic loading, authoring, and status chrome text."""
        return bool(LOW_VALUE_CONTENT_RE.match(clean(text)))

    def is_date_like_text(self, text: str) -> bool:
        """Recognize standalone day-month-year separators used in timelines."""
        return bool(re.match(r"^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}$", clean(text)))

    def parse_message_like_text(self, text: str) -> dict[str, str] | None:
        """Parse common chat/timeline rows into model-readable fields.

        This intentionally uses only rendered text patterns. It does not depend on
        implementation-specific classes, authored selectors, or external labels. If the
        text does not look like a message row, the renderer leaves it as normal
        content.
        """
        raw = clean(text)
        match = MESSAGE_PREFIX_RE.match(raw)
        if not match:
            return None

        author = clean(match.group("author"))
        time = clean(match.group("time"))
        body = clean(match.group("body"))
        thread = ""
        reactions: list[str] = []

        thread_match = THREAD_SUMMARY_RE.search(body)
        if thread_match:
            count = clean(thread_match.group("count"))
            last = clean(thread_match.group("last") or "")
            thread = f"{count}, {last}" if last else count
            body = clean((body[: thread_match.start()] + " " + body[thread_match.end() :]).strip())

            # A trailing "+1" / emoji / small count immediately before a thread
            # summary is reaction metadata, not body text. Extract only when a
            # thread summary exists so ordinary sentences ending with a number are
            # not changed.
            parts = body.rsplit(" ", 1)
            if len(parts) == 2 and REACTION_TOKEN_RE.fullmatch(parts[1].strip()):
                reactions.append(parts[1].strip())
                body = clean(parts[0])

        return {
            "author": author,
            "time": time,
            "text": body,
            "thread": thread,
            "reactions": ", ".join(reactions),
        }

    def normalize_attachment_label(self, label: str) -> str:
        """Normalize generic attachment labels using visible text patterns."""
        value = clean(label)
        # Some apps render card labels with no space before a media type:
        # "ReleaseBriefCanvas" -> "ReleaseBrief Canvas". Keep this generic; it
        # only affects labels ending in the common browser/media term "Canvas".
        value = re.sub(r"(?<=[A-Za-z0-9)])Canvas\b", " Canvas", value)
        return clean(value)

    def attachment_labels_for_item(
        self,
        text: str,
        controls: list[tuple[dict[str, Any], list[str]]],
    ) -> list[str]:
        """Extract file/media labels while preserving meaningful duplicate filenames."""
        labels: list[str] = []

        # Preserve duplicates found in the rendered text. Two identical
        # filenames in the row usually means two attached files with the same
        # visible name, and collapsing them hides information.
        occupied_spans: list[tuple[int, int]] = []
        cleaned_text = clean(text)
        for pattern in (ATTACHMENT_SPACED_FILE_RE, ATTACHMENT_FILE_TOKEN_RE):
            for match in pattern.finditer(cleaned_text):
                span = match.span()
                if any(not (span[1] <= old[0] or span[0] >= old[1]) for old in occupied_spans):
                    continue
                occupied_spans.append(span)
                labels.append(match.group(0))

        seen_control_labels = {norm_key(label) for label in labels}
        for control, _actions in controls:
            label = self.normalize_attachment_label(self.text(control))
            lower = label.lower().strip()
            if not label or lower == "toggle file":
                continue
            tag = self.node_tag(control)
            is_attachment = bool(MEDIA_FILE_RE.search(label))
            is_attachment = is_attachment or tag in MEDIA_TAGS
            is_canvas_attachment = bool(re.search(r"\bcanvas\b", lower)) and lower.endswith("canvas")
            is_short_add_create_control = lower.startswith(("add ", "create ")) and len(lower.split()) <= 4
            is_attachment = is_attachment or (is_canvas_attachment and lower != "canvas" and not is_short_add_create_control)
            if not is_attachment:
                continue
            key = norm_key(label)
            if key and key in seen_control_labels:
                continue
            seen_control_labels.add(key)
            labels.append(label)
        return labels

    def text_without_attachment_labels(self, text: str, attachments: list[str]) -> str:
        """Remove plain file-token duplication without deleting rich attachment text."""
        stripped = clean(text)
        for label in attachments:
            # Only remove simple file tokens from body text. Rich attachment
            # labels such as Canvas titles may be meaningful sentence text, so
            # leave them unless they are plain file tokens.
            if not (
                ATTACHMENT_FILE_TOKEN_RE.fullmatch(label)
                or ATTACHMENT_SPACED_FILE_RE.fullmatch(label)
            ):
                continue
            stripped = re.sub(rf"(?<![\w.-]){re.escape(label)}(?![\w.-])", " ", stripped, count=1)
        stripped = re.sub(r"\b\d+\s+files?\s+Download all\b", " ", stripped, flags=re.I)
        stripped = clean(stripped)
        return stripped or clean(text)

    def format_content_item_lines(
        self,
        text: str,
        *,
        prefix: str = "-",
        attachments: list[str] | None = None,
    ) -> list[str]:
        """Format ordinary content or parsed message rows with attachment metadata."""
        attachment_labels = attachments or []
        parsed = self.parse_message_like_text(text)
        if not parsed:
            lines = [f"{prefix} {clip(text, min(self.max_text_chars, 360))}"]
            if attachment_labels:
                lines.append(f"  attachments: {', '.join(attachment_labels)}")
            return lines

        lines = [f"{prefix} {parsed['author']} {parsed['time']}"]
        if parsed.get("text"):
            body = self.text_without_attachment_labels(parsed["text"], attachment_labels)
            lines.append(f"  text: {clip(body, min(self.max_text_chars, 320))}")
        if attachment_labels:
            lines.append(f"  attachments: {', '.join(attachment_labels)}")
        if parsed.get("reactions"):
            reaction_text = parsed["reactions"].replace("+1", "+1 emoji")
            lines.append(f"  reactions: {reaction_text}")
        if parsed.get("thread"):
            lines.append(f"  thread: {parsed['thread']}")
        return lines

    def low_value_nested_control(self, node: dict[str, Any], actions: list[str], parent_text: str) -> bool:
        """Suppress nested metadata controls while retaining genuine activation inputs."""
        label = self.text(node)
        if any(action in actions for action in ("type", "focus", "select", "toggle", "upload")):
            return False
        if not label:
            return True
        if label.lower().strip() == "toggle file":
            return True
        if MEDIA_FILE_RE.search(label):
            return True
        if CONTROL_WORDS.search(label):
            return False
        if any(pattern.search(label) for pattern in LOW_VALUE_NESTED_LABEL_PATTERNS):
            return True
        context = self.region_context(node, limit=160).lower()
        if "profile" in context and not CONTROL_WORDS.search(label):
            return True
        tag = self.node_tag(node)
        role = self.node_role(node)
        if tag == "button" or role == "button":
            return False
        label_key = norm_key(label)
        parent_key = norm_key(parent_text)
        return bool(label_key and label_key in parent_key and len(label) <= self.chrome_label_max_chars)

    def is_readable_item(self, node: dict[str, Any]) -> bool:
        """Recognize list-item boundaries from tag, role, or semantic boundary."""
        tag = clean(node.get("tag"), fix_mojibake=False).lower()
        role = clean(node.get("role"), fix_mojibake=False).lower()
        semantic = clean(node.get("semanticBoundary"), fix_mojibake=False).lower()
        return tag == "li" or role == "listitem" or semantic == "listitem"

    def nearest_readable_item(self, node: dict[str, Any]) -> dict[str, Any] | None:
        """Return the closest ancestor that represents a readable repeated item."""
        for ancestor in self.ancestors(node):
            if self.is_readable_item(ancestor):
                return ancestor
        return None

    def semantic_owner_ref(self, node: dict[str, Any]) -> str:
        """Scope repeated text to its nearest readable item when one exists."""
        if self.is_readable_item(node):
            return self.node_ref(node)
        owner = self.nearest_readable_item(node)
        if owner is None:
            owner = next(
                (
                    ancestor
                    for ancestor in self.ancestors(node)
                    if self.node_ref(ancestor) in self.repeated_item_refs
                ),
                None,
            )
        return self.node_ref(owner) if owner is not None else ""

    def additional_content_evidence(
        self,
        node: dict[str, Any],
        emitted_lines: list[str],
    ) -> list[str]:
        """Preserve captured descendant-control facts omitted from parent text.

        Interactive descendants can carry accessibility metadata (for example,
        precise timestamps or control state) that is not present in their
        parent's subtree text. Such facts remain read-only evidence here; no
        executable action id is introduced.
        """
        ref = self.node_ref(node)
        if not ref:
            return []
        emitted_key = norm_key(" ".join(emitted_lines))
        owner_ref = self.semantic_owner_ref(node)
        evidence: list[str] = []
        seen: set[str] = set()
        descendant_nodes = [
            self.by_ref[child_ref]
            for child_ref in self.descendants(ref)
            if child_ref in self.by_ref
        ]
        descendant_nodes.sort(key=self.source_order)
        for child in descendant_nodes:
            if not self.action_types(child):
                continue
            child_owner_ref = self.semantic_owner_ref(child)
            if owner_ref and child_owner_ref and child_owner_ref != owner_ref:
                continue
            attrs = attr_map(child)
            candidates = [
                clean(child.get("accessibleName")),
                attrs.get("aria-label", ""),
                attrs.get("value", ""),
                attrs.get("title", ""),
                self.text(child),
            ]
            raw_states = child.get("states", [])
            has_state = isinstance(raw_states, list) and any(
                isinstance(state, dict) and clean(state.get("value")) for state in raw_states
            )
            for value in candidates:
                value = clean(value)
                if not has_state and not any(character.isdigit() for character in value):
                    continue
                key = norm_key(value)
                if not key or key in seen or key in emitted_key:
                    continue
                seen.add(key)
                evidence.append(value)
                break
        return evidence

    def is_broad_action(self, node: dict[str, Any], actions: list[str]) -> bool:
        """Identify container-wide actions that are unusable or excessively noisy."""
        tag = clean(node.get("tag"), fix_mojibake=False).lower()
        role = clean(node.get("role"), fix_mojibake=False).lower()
        text = self.text(node)
        direct = clean(node.get("directText"))
        if tag in {"html", "body"}:
            return True
        if role in {"dialog", "alertdialog"} and tag in BROAD_CONTAINER_TAGS:
            return True
        if tag in TABLE_TAGS and actions == ["scroll"]:
            return True
        if tag in BROAD_CONTAINER_TAGS and role in {"", "generic", "none", "application"}:
            if not direct and len(text) > 220:
                return True
            if actions == ["click"] and len(text) > 180:
                return True
        return False

    def is_primary_action(self, node: dict[str, Any], actions: list[str]) -> bool:
        """Require visible, hit-testable, labeled controls for the primary list."""
        if str(node.get("ref", "")) in self.suppressed_refs:
            return False
        if self.is_broad_action(node, actions):
            return False
        tag = clean(node.get("tag"), fix_mojibake=False).lower()
        label = self.text(node)
        attrs = attr_map(node)
        # Scroll is not an activation affordance: it is only present because the
        # element has overflow. The scroll tool addresses regions, not element
        # ids, so a scroll-only entry here is unusable. Regions are listed
        # separately by the caller.
        if actions == ["scroll"]:
            return False
        # The default click path is CDP mouse input only. If ChromiumRL says a
        # node is not hit-testable/currently in viewport, showing it as a normal
        # action leads the model to click an id that cannot work.
        if node.get("visible") is False or node.get("inViewport") is False or node.get("hitTestable") is False:
            return False
        if tag in {"input", "textarea", "select"}:
            return True
        if any(action in actions for action in ("type", "focus", "select", "toggle", "upload")):
            return True
        if label and norm_key(label) not in {norm_key(item) for item in LOW_VALUE_LABELS}:
            return True
        # ====CHANGED==== Do not show unlabeled href/src-only icons as primary
        # actions. They produce lines like `[14] link ref=e5`, which gives the
        # model no useful decision surface. Raw/full debug still contains them.
        if label and (attrs.get("href") or attrs.get("src")):
            return True
        return False

    def collect_action_nodes(self) -> list[tuple[dict[str, Any], list[str]]]:
        """Collect every declared action in deterministic index/document order."""
        rows: list[tuple[dict[str, Any], list[str]]] = []
        for node in self.nodes:
            actions = self.action_types(node)
            if not actions:
                continue
            rows.append((node, actions))
        rows.sort(key=lambda pair: (self.node_index(pair[0]) is None, self.node_index(pair[0]) or 0, self.source_order(pair[0])))
        return rows

    def group_nested_actions(self) -> dict[str, list[tuple[dict[str, Any], list[str]]]]:
        """Attach useful descendant controls to their nearest readable item."""
        grouped: dict[str, list[tuple[dict[str, Any], list[str]]]] = {}
        for node, actions in self.action_nodes:
            if not self.is_primary_action(node, actions):
                continue
            parent = self.nearest_readable_item(node)
            if not parent:
                continue
            if not self.is_useful_nested_action(node, actions, self.text(parent)):
                continue
            parent_ref = str(parent.get("ref", ""))
            node_ref = str(node.get("ref", ""))
            if parent_ref and node_ref and parent_ref != node_ref:
                grouped.setdefault(parent_ref, []).append((node, actions))
        # Controls are truncated per item, so order decides what survives. Rank
        # activation controls above navigation links: a row's buttons are how the
        # model acts on it, while its links usually restate text already shown.
        for controls in grouped.values():
            controls.sort(key=lambda pair: self.nested_action_rank(pair[0]))
        return grouped

    def nested_action_rank(self, node: dict[str, Any]) -> tuple[int, int]:
        """Rank inputs and activation controls ahead of restated navigation links."""
        tag = self.node_tag(node)
        role = self.node_role(node)
        label = self.text(node)
        if any(action in self.action_types(node) for action in ("type", "focus", "select", "toggle", "upload")):
            rank = 0
        elif CONTROL_WORDS.search(label):
            rank = 1
        elif tag == "button" or role == "button":
            rank = 2
        elif tag == "a" or role == "link":
            rank = 4
        else:
            rank = 3
        return (rank, self.source_order(node))

    def is_useful_nested_action(self, node: dict[str, Any], actions: list[str], parent_text: str) -> bool:
        """Keep nested controls that add an operation not already conveyed by text."""
        label = self.text(node)
        label_key = norm_key(label)
        parent_key = norm_key(parent_text)
        tag = clean(node.get("tag"), fix_mojibake=False).lower()

        if any(action in actions for action in ("type", "focus", "select", "toggle", "upload")):
            return True
        if tag in {"input", "textarea", "select"}:
            return True
        if not label:
            return False
        if self.low_value_nested_control(node, actions, parent_text):
            return False
        if CONTROL_WORDS.search(label):
            return True
        if tag == "button":
            return True
        if tag == "a" and len(label) > 2:
            return True
        if label_key and label_key in parent_key:
            return False
        return True

    def action_line(self, node: dict[str, Any], actions: list[str], *, include_debug: bool = False) -> str:
        """Render one executable id with semantic label and optional debug facts."""
        label = clip(self.text(node), 140 if not include_debug else 220)
        ref = str(node.get("ref", ""))
        tag = clean(node.get("tag"), fix_mojibake=False) or "?"
        role = clean(node.get("role"), fix_mojibake=False)
        kind = self.action_kind(node, actions)
        if not include_debug:
            lower = label.lower().strip()
            if THREAD_SUMMARY_RE.search(label) or re.fullmatch(r"\d+\s+repl(?:y|ies)", label, re.I):
                return f"[{self.action_id(node)}] open thread/replies"
        bits = [f"[{self.action_id(node)}]", kind]
        if label:
            bits.append(json.dumps(label, ensure_ascii=False))
        if actions != ["click"] or kind in {"search-input", "text-input", "select", "toggle", "file-upload"}:
            bits.append(f"actions={','.join(actions)}")
        attrs = attr_map(node)
        # Raw URLs are never printed. A target address is not information the model
        # can act on - it acts on the id - and permalinks, private file URLs and
        # resource ids are exactly the material tasks forbid it from reproducing.
        # Printing them supplies the text and then penalises its use.
        if attrs.get("src") and not label:
            bits.append("src=(image)")
        # Synthetic ids (A1, A2, ...) only exist in this output, so always pair
        # them with the node ref an executor can resolve.
        show_ref = bool(ref) and (self.include_refs or self.node_index(node) is None)
        if include_debug:
            bits.append(f"<{tag}>")
            if role:
                bits.append(f"role={role}")
            context = self.region_context(node, limit=140)
            if context:
                bits.append(f"context={json.dumps(context, ensure_ascii=False)}")
            visibility = self.visibility_notes(node)
            if visibility:
                bits.append(f"state={','.join(visibility)}")
            bits.append(f"hit={node.get('hitTestable')}")
            bits.append(f"viewport={node.get('inViewport')}")
            bits.append(f"sourceOrder={self.source_order(node)}")
            if show_ref:
                bits.append(f"ref={ref}")
            bounds = bounds_text(node.get("bounds"))
            if bounds:
                bits.append(f"bounds=({bounds})")
        elif show_ref:
            bits.append(f"ref={ref}")
        return " ".join(bits)

    def action_priority(self, node: dict[str, Any], actions: list[str]) -> tuple[int, int]:
        """Prioritize direct task controls over tabs, toolbars, and broad navigation."""
        label = self.text(node)
        kind = self.action_kind(node, actions)
        role = self.node_role(node)
        tag = self.node_tag(node)
        lower = label.lower()
        tokens = self.ancestor_region_tokens(node)
        context = self.region_context(node, limit=180).lower()
        is_toolbar_region = "toolbar" in tokens
        is_navigation_region = bool(tokens & {"nav", "navigation", "aside", "tree", "treeitem", "tablist"})
        is_search_region = "search" in tokens or "search" in context or role == "option" or "listbox" in tokens
        is_main_region = bool(tokens & {"main", "article", "feed", "list", "listitem", "table", "row", "cell"}) or self.nearest_readable_item(node) is not None
        is_result_like = (
            is_search_region
            and kind not in {"search-input", "text-input", "file-upload"}
            and len(label) >= 12
            and not is_toolbar_region
            and (role in {"option", "listitem", "treeitem"} or kind in {"select", "link", "clickable"})
        )
        if node.get("hitTestable") is False or node.get("inViewport") is False or node.get("visible") is False:
            return (9, self.source_order(node))
        if "nan" in lower:
            return (9, self.source_order(node))
        if kind in {"search-input", "text-input"}:
            return (0, self.source_order(node))
        if "search" in lower:
            return (1, self.source_order(node))
        if is_result_like:
            return (2, self.source_order(node))
        if lower.startswith("load "):
            return (2, self.source_order(node))
        if role == "tab":
            return (7, self.source_order(node))
        if role == "treeitem" and label and len(label) <= 32:
            level = self.attr_int(node, "aria-level")
            if level is not None and level <= 1 and self.has_deeper_treeitem_in_same_tree(node):
                return (7, self.source_order(node))
            return (3, self.source_order(node))
        if is_navigation_region and not ESSENTIAL_ACTION_WORDS.search(label):
            return (7, self.source_order(node))
        # ====CHANGED==== Non-search toolbar buttons are usually app/page chrome
        # rather than task content. Keep them available in hidden/debug actions,
        # but do not let them crowd out direct navigation or content actions in
        # the compact model-facing list.
        if "toolbar" in tokens:
            return (7, self.source_order(node))
        if (tag == "button" or role == "button") and not is_main_region and not ESSENTIAL_ACTION_WORDS.search(label) and not CONTROL_WORDS.search(label):
            return (7, self.source_order(node))
        if lower.strip() in {"user:", "user"}:
            return (8, self.source_order(node))
        if CONTROL_WORDS.search(label):
            return (2, self.source_order(node))
        if role in {"tab", "treeitem"}:
            return (5, self.source_order(node))
        if tag in {"a", "button"} or role in {"button", "link"}:
            return (3, self.source_order(node))
        return (6, self.source_order(node))

    def ancestor_region_tokens(self, node: dict[str, Any]) -> set[str]:
        """Generic region tokens from DOM/AX ancestry.

        This intentionally uses browser facts only: tag, role and semantic
        boundary. It does not inspect task names, app names, channel names or
        verifier terms.
        """
        tokens: set[str] = set()
        for ancestor in self.ancestors(node):
            for value in (
                self.node_tag(ancestor),
                self.node_role(ancestor),
                clean(ancestor.get("semanticBoundary"), fix_mojibake=False).lower(),
            ):
                if value:
                    tokens.add(value)
        return tokens

    def attr_int(self, node: dict[str, Any], name: str) -> int | None:
        """Parse one selected attribute as an integer, returning None on failure."""
        value = attr_map(node).get(name)
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def has_deeper_treeitem_in_same_tree(self, node: dict[str, Any]) -> bool:
        """Detect concrete nested tree destinations when ranking top-level categories."""
        # ====CHANGED==== Generic tree-navigation priority. If a tree contains
        # deeper items, compact model output should prefer those concrete nested
        # destinations over top-level categories/tabs. This is structural: ARIA
        # role/tree level only, no application labels or task terms.
        current_level = self.attr_int(node, "aria-level")
        if current_level is None:
            return False
        tree_ref = ""
        for ancestor in self.ancestors(node):
            if self.node_role(ancestor) == "tree":
                tree_ref = self.node_ref(ancestor)
                break
        if not tree_ref:
            return False
        for ref in self.descendants(tree_ref):
            other = self.by_ref.get(ref)
            if not other or other is node or self.node_role(other) != "treeitem":
                continue
            other_level = self.attr_int(other, "aria-level")
            if other_level is not None and other_level > current_level:
                return True
        return False

    def render_header(self) -> list[str]:
        """Render page identity, action-id guidance, and compact capture statistics."""
        stats = self.snapshot.get("stats", {}) if isinstance(self.snapshot.get("stats"), dict) else {}
        lines = [
            f"URL: {clean(self.snapshot.get('url'))}",
            f"Title: {clean(self.snapshot.get('title'))}",
            'Use only ids from this observation. Scroll with scroll("down", 1600, element_id=<id>).',
        ]
        if stats:
            parts = []
            for key in ("returnedNodes", "groups", "truncated"):
                if key in stats:
                    parts.append(f"{key}={stats.get(key)}")
            lines.append("Snapshot: " + " ".join(parts))
        return lines

    def table_rows(self, table: dict[str, Any]) -> list[list[str]]:
        """Extract ordered cell text from semantic or HTML table rows."""
        table_ref = str(table.get("ref", ""))
        refs = self.descendants(table_ref)
        rows = [
            self.by_ref[ref]
            for ref in refs
            if ref in self.by_ref
            and (
                clean(self.by_ref[ref].get("tag"), fix_mojibake=False).lower() == "tr"
                or clean(self.by_ref[ref].get("semanticBoundary"), fix_mojibake=False).lower() == "row"
            )
        ]
        rows.sort(key=self.source_order)
        rendered: list[list[str]] = []
        for row in rows:
            cells = [
                child
                for child in self.children.get(str(row.get("ref")), [])
                if clean(child.get("tag"), fix_mojibake=False).lower() in {"td", "th"}
                or clean(child.get("semanticBoundary"), fix_mojibake=False).lower() == "cell"
            ]
            cells.sort(key=self.source_order)
            row_text = [clip(clean(cell.get("directText") or cell.get("subtreeText")), self.max_cell_chars) for cell in cells]
            if row_text and any(row_text):
                rendered.append(row_text)
        return rendered

    def render_tables(self) -> tuple[list[str], set[str]]:
        """Render bounded table rows and return refs covered by the table section."""
        tables = [node for node in self.nodes if clean(node.get("tag"), fix_mojibake=False).lower() == "table"]
        tables.sort(key=self.source_order)
        lines: list[str] = []
        covered: set[str] = set()
        if not tables:
            return lines, covered
        lines.append("=== TABLES ===")
        for idx, table in enumerate(tables, start=1):
            table_ref = str(table.get("ref", ""))
            covered.add(table_ref)
            covered.update(self.descendants(table_ref))
            rows = self.table_rows(table)
            cols = max((len(row) for row in rows), default=0)
            ref_text = f" ref={table_ref}" if self.include_refs and table_ref else ""
            lines.append(f"Table {idx}{ref_text}: rows={len(rows)} columns={cols}")
            for row in rows[: self.max_table_rows]:
                lines.append("  " + " | ".join(row))
            if len(rows) > self.max_table_rows:
                lines.append(f"  [table rows hidden: {len(rows) - self.max_table_rows} more]")
        return lines, covered

    def is_content_node(self, node: dict[str, Any], covered: set[str]) -> bool:
        """Select readable semantic or own-text nodes while filtering duplicated chrome."""
        ref = str(node.get("ref", ""))
        if ref in covered or ref in self.suppressed_refs:
            return False
        tag = clean(node.get("tag"), fix_mojibake=False).lower()
        role = clean(node.get("role"), fix_mojibake=False).lower()
        semantic = clean(node.get("semanticBoundary"), fix_mojibake=False).lower()
        text = self.text(node)
        if not text:
            return False
        if self.is_low_value_content_text(text):
            return False
        if not self.include_offscreen_content and node.get("inViewport") is False:
            return False
        if (
            self.include_offscreen_content
            and node.get("inViewport") is False
            and not self.action_types(node)
            and self.has_ancestor_role_or_tag(
                node,
                {"nav", "aside", "navigation", "toolbar", "header", "footer", "menu"},
            )
        ):
            return False
        if tag in {"html", "body"} or tag in TABLE_TAGS or tag in MEDIA_TAGS:
            return False
        if self.action_types(node) and tag not in CONTENT_TAGS and role not in {"heading", "paragraph", "listitem"}:
            return False
        if tag in CONTENT_TAGS or role in {"heading", "paragraph", "listitem", "alertdialog", "dialog"} or semantic == "listitem":
            return True
        # Applications commonly render text into role-less <div>/<span> nodes. A
        # node with its own directText is real page content regardless of role;
        # without this, message/comment bodies are dropped from the observation.
        direct = clean(node.get("directText"))
        if not direct:
            return False
        # Keep action-linked text out of content when it is only a repeated
        # control caption. Numeric metadata (dates, counts, versions, sizes)
        # remains evidence even when the page also wraps it in a control.
        if (
            len(direct) <= self.chrome_label_max_chars
            and self.matches_action_label(direct)
            and not any(character.isdigit() for character in text)
        ):
            return False
        return True

    def matches_action_label(self, text: str) -> bool:
        """True when `text` restates an interactive element's name.

        Containment rather than equality, because applications decorate control
        names with counts and hints ("Home 1", "Channels Press Ctrl L to ...")
        while rendering the bare caption as a separate text node.
        """
        key = norm_key(text)
        if not key:
            return False
        if key in self.action_labels:
            return True
        return any(key in label for label in self.action_labels)

    def has_rendered_ancestor(self, node: dict[str, Any], rendered: set[str]) -> bool:
        """Whether an ancestor of `node` already had its full text emitted."""
        parent_ref = node.get("parentRef")
        walked: set[str] = set()
        while parent_ref is not None:
            key = str(parent_ref)
            if key in walked:
                break
            walked.add(key)
            if key in rendered:
                return True
            parent = self.by_ref.get(key)
            if parent is None:
                break
            parent_ref = parent.get("parentRef")
        return False

    def render_content(self, covered: set[str]) -> tuple[list[str], set[str]]:
        """Render deduplicated visible/offscreen content within an optional cap.

        A non-positive max_content_blocks value is deliberately unlimited. The
        recorder uses that mode so this projection cannot discard evidence that
        is already present in the authoritative structured snapshot.
        """
        candidates = [node for node in self.nodes if self.is_content_node(node, covered)]
        candidates.sort(key=self.source_order)
        visible_lines: list[str] = []
        offscreen_lines: list[str] = []
        rendered_refs: set[str] = set()
        # ====CHANGED==== Refs whose text was emitted in full. Applications split one
        # logical item across nested elements, so a descendant restates part of the row
        # already shown -- and because inline markup (mentions, links) lives in its own
        # child nodes, the fragment renders with those words missing and reads as a
        # broken duplicate sentence. Only fully-emitted ancestors suppress: when an
        # ancestor's text was clipped, a descendant may carry the part that was cut.
        whole_refs: set[str] = set()
        seen: set[tuple[str, str]] = set()
        context_by_bucket = {"visible": "", "offscreen": ""}
        visible_count = 0
        offscreen_count = 0
        for idx, node in enumerate(candidates):
            ref = str(node.get("ref", ""))
            if self.has_rendered_ancestor(node, whole_refs):
                continue
            full = self.text(node)
            text = clip(full, self.max_text_chars)
            # Rendering an ancestor's chosen own text does not prove that every
            # distinct descendant fact was represented. Only leaves can safely
            # suppress descendants; row/container children must still be
            # considered and deduplicated in their semantic scope.
            if (
                ref
                and not self.children.get(ref)
                and node.get("truncated") is not True
                and len(text) >= len(full)
            ):
                whole_refs.add(ref)
            key = norm_key(text)
            dedupe_key = (self.semantic_owner_ref(node), key)
            if not key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            self.rendered_content_text_keys.add(key)
            rendered_refs.add(ref)

            is_visible = node.get("visible") is not False and node.get("inViewport") is not False
            bucket = "visible" if is_visible else "offscreen"
            target_lines = visible_lines if is_visible else offscreen_lines
            if is_visible:
                visible_count += 1
            else:
                offscreen_count += 1

            context = self.display_context(node)
            if context and context != context_by_bucket[bucket]:
                target_lines.append(f"Context: {context}")
                context_by_bucket[bucket] = context

            role = self.node_role(node)
            node_actions = self.action_types(node)
            controls = self.nested_actions_by_content_ref.get(ref, [])
            attachment_labels = self.attachment_labels_for_item(full, controls)
            useful_controls = [
                (control, actions)
                for control, actions in controls
                if not self.low_value_nested_control(control, actions, full)
            ]
            item_prefix = "-"
            can_show_row_id = role != "listitem" and not self.is_date_like_text(text)
            if is_visible and can_show_row_id and node_actions and self.is_primary_action(node, node_actions) and not useful_controls:
                item_prefix = f"- [{self.action_id(node)}]"
            elif self.include_refs and ref:
                item_prefix = f"- ref={ref}"
            item_lines = self.format_content_item_lines(
                full, prefix=item_prefix, attachments=attachment_labels
            )
            target_lines.extend(item_lines)
            for evidence in self.additional_content_evidence(node, item_lines):
                target_lines.append(f"  evidence: {evidence}")
            if controls:
                rendered_controls = [
                    self.action_line(control, actions)
                    for control, actions in useful_controls[: self.max_nested_actions]
                ]
                if rendered_controls:
                    target_lines.append("  actions: " + "; ".join(rendered_controls))
                if len(useful_controls) > self.max_nested_actions:
                    target_lines.append(f"  [actions hidden: {len(useful_controls) - self.max_nested_actions} more]")
            if self.max_content_blocks > 0 and len(rendered_refs) >= self.max_content_blocks:
                remaining_keys = set()
                for rest in candidates[idx + 1:]:
                    rest_key = norm_key(clip(self.text(rest), self.max_text_chars))
                    rest_dedupe_key = (self.semantic_owner_ref(rest), rest_key)
                    if rest_key and rest_dedupe_key not in seen:
                        remaining_keys.add(rest_dedupe_key)
                if remaining_keys:
                    target_lines.append(
                        f"[content hidden: {len(remaining_keys)} more reason=max_content_blocks]"
                    )
                break
        lines: list[str] = []
        if visible_lines:
            lines.append("=== VISIBLE CONTENT ===")
            lines.extend(visible_lines)
        if offscreen_lines:
            lines.append("=== ADDITIONAL CAPTURED CONTENT ===")
            primary_scroll = self.scroll_region_rows()
            if primary_scroll:
                _, node = primary_scroll[0]
                lines.append(
                    f"Not currently clickable. To interact with these rows, scroll "
                    f"[{self.action_id(node)}] {self.scroll_region_label(node)}."
                )
            else:
                lines.append("Not currently clickable. Use page scroll to bring this content into view.")
            lines.extend(offscreen_lines)
        return lines, rendered_refs

    def render_media(self, covered: set[str]) -> list[str]:
        """Render unique media labels not already represented by content text."""
        rows: list[str] = []
        seen: set[str] = set()
        item_count = 0
        for node in sorted(self.nodes, key=self.source_order):
            ref = str(node.get("ref", ""))
            if ref in covered:
                continue
            if not self.include_offscreen_content and node.get("inViewport") is False:
                continue
            tag = clean(node.get("tag"), fix_mojibake=False).lower()
            if tag not in MEDIA_TAGS:
                continue
            attrs = attr_map(node)
            label = self.text(node) or attrs.get("alt") or attrs.get("title") or attrs.get("src")
            if not label:
                continue
            label_key = norm_key(label)
            if any(label_key and (label_key == key or label_key in key or key in label_key) for key in self.rendered_content_text_keys):
                continue
            key = f"{tag}:{norm_key(label)}"
            if key in seen:
                continue
            seen.add(key)
            if not rows:
                rows.append("=== MEDIA / IMAGE LABELS ===")
            parts = [f"- {json.dumps(clip(label, 120), ensure_ascii=False)}"]
            if attrs.get("src"):
                parts.append("source=present")
            context = self.display_context(node, limit=60)
            if context:
                parts.append(f"context={json.dumps(context, ensure_ascii=False)}")
            if self.include_refs:
                parts.append(f"ref={ref}")
            rows.append(" ".join(parts))
            item_count += 1
            media_limit = min(self.max_media, 20)
            if item_count >= media_limit:
                rows.append(f"[media hidden: more than {media_limit} items]")
                break
        return rows

    def render_actions(self, rendered_content_refs: set[str]) -> list[str]:
        """Render prioritized global actions after excluding content-nested controls."""
        nested_refs = {
            str(control.get("ref"))
            for item_ref in rendered_content_refs
            for control, _ in self.nested_actions_by_content_ref.get(item_ref, [])
        }
        rendered_descendants = {
            ref for item_ref in rendered_content_refs for ref in self.descendants(item_ref)
        }

        primary: list[tuple[dict[str, Any], list[str]]] = []
        secondary: list[tuple[dict[str, Any], list[str], str]] = []
        seen_primary: set[str] = set()
        seen_secondary: set[str] = set()
        for node, actions in self.action_nodes:
            ref = str(node.get("ref", ""))
            if ref in nested_refs or ref in rendered_content_refs or ref in rendered_descendants:
                continue
            label_key = norm_key(self.text(node))
            if node.get("hitTestable") is False and label_key:
                key = f"not-hit:{label_key}"
            else:
                key = f"{self.action_id(node)}:{','.join(actions)}:{label_key}"
            if self.is_primary_action(node, actions):
                if key in seen_primary:
                    continue
                seen_primary.add(key)
                primary.append((node, actions))
            else:
                reason = "broad/noisy"
                if "click" in actions and node.get("hitTestable") is False:
                    reason = "not_hit_testable"
                elif not self.text(node):
                    reason = "unlabeled"
                if key in seen_secondary:
                    continue
                seen_secondary.add(key)
                secondary.append((node, actions, reason))

        lines: list[str] = []
        if primary:
            # ====CHANGED==== Default model output is compact again. Grouping is
            # useful for diagnostics, but the previous default emitted too much
            # app chrome. A single priority-sorted list keeps the prompt shorter
            # while structural priorities keep direct navigation/search visible.
            primary.sort(key=lambda pair: self.action_priority(pair[0], pair[1]))
            compact_primary = [
                (node, actions)
                for node, actions in primary
                if self.action_priority(node, actions)[0] <= 3
            ]
            if not compact_primary:
                compact_primary = primary
            action_limit = min(self.max_actions, 25)
            lines.append("=== USEFUL PAGE ACTIONS ===")
            for node, actions in compact_primary[:action_limit]:
                lines.append(self.action_line(node, actions))
            shown_refs = {
                self.node_ref(node) for node, _ in compact_primary[:action_limit]
            }
            hidden = max(0, len(primary) - min(len(compact_primary), action_limit))
            if hidden:
                lines.append(f"[other actions hidden: {hidden}]")

            read_only_rows: list[str] = []
            seen_read_only: set[str] = set()
            for node, _ in primary:
                if self.node_ref(node) in shown_refs:
                    continue
                facts = [self.text(node)]
                raw_states = node.get("states", [])
                if isinstance(raw_states, list):
                    for state in raw_states:
                        if not isinstance(state, dict):
                            continue
                        name = clean(state.get("name"), fix_mojibake=False)
                        value = clean(state.get("value"))
                        if name and value:
                            facts.append(f"{name}={value}")
                fact = clean("; ".join(item for item in facts if item))
                fact_key = norm_key(fact)
                if not fact_key or fact_key in seen_read_only:
                    continue
                if any(
                    fact_key == content_key or fact_key in content_key
                    for content_key in self.rendered_content_text_keys
                ):
                    continue
                seen_read_only.add(fact_key)
                read_only_rows.append(f"- {fact}")
            if read_only_rows:
                lines.append("=== READ-ONLY CONTROL EVIDENCE ===")
                lines.extend(read_only_rows)

        if self.include_secondary and secondary:
            lines.append("=== SECONDARY / DEBUG ACTIONS ===")
            for node, actions, reason in secondary[: self.max_secondary_actions]:
                lines.append(f"{self.action_line(node, actions, include_debug=True)} reason={reason}")
            if len(secondary) > self.max_secondary_actions:
                lines.append(f"[secondary actions hidden: {len(secondary) - self.max_secondary_actions} more]")

        # Action rows intentionally keep labels compact. When the captured label
        # is richer than that executable representation, retain the complete
        # value separately as read-only evidence rather than losing its tail.
        complete_control_text: list[str] = []
        seen_complete: set[str] = set()
        for node, _ in self.action_nodes:
            full = self.text(node)
            if len(full) <= 220:
                continue
            key = norm_key(full)
            if not key or key in seen_complete:
                continue
            seen_complete.add(key)
            complete_control_text.append(f"- {full}")
        if complete_control_text:
            lines.append("=== COMPLETE READ-ONLY CONTROL TEXT ===")
            lines.extend(complete_control_text)
        return lines

    def scroll_region_rows(self) -> list[tuple[float, dict[str, Any]]]:
        """Return visible substantial scroll regions ordered by viewport area."""
        regions: list[tuple[float, dict[str, Any]]] = []
        for node in self.nodes:
            ref = self.node_ref(node)
            if ref in self.suppressed_refs:
                continue
            if not node.get("scrollable"):
                continue
            if node.get("visible") is False or node.get("inViewport") is False:
                continue
            bounds = node.get("bounds")
            if not isinstance(bounds, dict):
                continue
            try:
                width = float(bounds.get("width") or 0)
                height = float(bounds.get("height") or 0)
                area = width * height
            except (TypeError, ValueError):
                continue
            if area <= 0 or height < 320:
                continue
            regions.append((area, node))
        regions.sort(key=lambda pair: -pair[0])
        return regions

    def scroll_region_label(self, node: dict[str, Any]) -> str:
        """Name a scroll pane from its own accessible identity, not subtree content."""
        # Name the pane, not its contents. `text()` deliberately prefers a node's own
        # and subtree text (right for message rows, useless here -- a region's subtree
        # is the whole pane). The accessible name is what identifies which pane it is.
        label = (
            clean(node.get("accessibleName"))
            or clean(node.get("description"))
            or clean(node.get("role"), fix_mojibake=False)
            or clean(node.get("tag"), fix_mojibake=False)
            or "region"
        )
        context = self.display_context(node, limit=60)
        label_key = label.lower().strip()
        if label_key in LOW_VALUE_CONTEXT_LABELS and context:
            label = f"{context} content"
        elif label_key in LOW_VALUE_CONTEXT_LABELS:
            label = "page content"
        return clip(label, 80)

    def render_scroll_regions(self) -> list[str]:
        """List the page's scrollable regions with ids.

        A page routinely has several at once -- a message list, an opened side pane, a
        navigation sidebar. Scroll-only nodes are excluded from the action list (they are
        not things to click), so without this section an agent cannot tell that a choice
        exists, and a scroll tool that guesses one region will silently scroll the wrong
        thing: measured, a thread pane opened by the agent lost the guess to the channel
        list behind it, making the thread unscrollable.

        Emitted whenever ChromiumRL reports visible scrollable regions, because
        multi-pane apps need explicit region ids and single-pane pages still benefit
        from a clear scroll target.
        """
        regions = self.scroll_region_rows()
        if not regions:
            return []
        lines = ["=== SCROLLABLE REGIONS ==="]
        lines.append('Use: scroll("down", 1600, element_id=<id>) or scroll("up", 1600, element_id=<id>).')
        for _, node in regions[: self.max_scroll_regions]:
            label = self.scroll_region_label(node)
            bounds = node.get("bounds") if isinstance(node.get("bounds"), dict) else {}
            try:
                size = f" {int(float(bounds.get('width') or 0))}x{int(float(bounds.get('height') or 0))}"
            except (TypeError, ValueError):
                size = ""
            role = self.node_role(node)
            role_text = f" ({role})" if role and role not in {"generic", "none"} else ""
            lines.append(f"[{self.action_id(node)}] {clip(label, 80)}{role_text} — {size.strip() or '?'}")
        if len(regions) > self.max_scroll_regions:
            lines.append(f"[scrollable regions hidden: {len(regions) - self.max_scroll_regions} more]")
        return lines

    def render(self) -> str:
        """Assemble header, tables, content, media, actions, and scroll regions."""
        sections: list[list[str]] = [self.render_header()]
        table_lines, covered = self.render_tables()
        if table_lines:
            sections.append(table_lines)
        content_lines, rendered_content_refs = self.render_content(covered)
        if content_lines:
            sections.append(content_lines)
        media_covered = set(covered)
        media_covered.update(rendered_content_refs)
        for item_ref in rendered_content_refs:
            media_covered.update(self.descendants(item_ref))
        media_lines = self.render_media(media_covered)
        if media_lines:
            sections.append(media_lines)
        action_lines = self.render_actions(rendered_content_refs)
        if action_lines:
            sections.append(action_lines)
        region_lines = self.render_scroll_regions()
        if region_lines:
            sections.append(region_lines)
        return "\n\n".join("\n".join(section) for section in sections if section).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse model-render budgets; they never modify the captured source JSON."""
    parser = argparse.ArgumentParser(description="Render a ChromiumRL structured snapshot for model context")
    parser.add_argument("input", type=Path, help="Input structured snapshot JSON")
    parser.add_argument("-o", "--output", type=Path, help="Optional output TXT path")
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument("--max-secondary-actions", type=int, default=80)
    parser.add_argument("--max-nested-actions", type=int, default=8)
    parser.add_argument("--max-content-blocks", type=int, default=80)
    parser.add_argument("--max-table-rows", type=int, default=60)
    parser.add_argument("--max-media", type=int, default=60)
    parser.add_argument("--max-scroll-regions", type=int, default=16)
    parser.add_argument("--max-cell-chars", type=int, default=180)
    parser.add_argument("--max-text-chars", type=int, default=700)
    parser.add_argument("--chrome-label-max-chars", type=int, default=CHROME_LABEL_MAX_CHARS)
    parser.add_argument("--include-refs", action="store_true")
    parser.add_argument("--include-secondary", action="store_true")
    parser.add_argument("--suppress-authoring", action="store_true")
    parser.add_argument(
        "--include-offscreen-content",
        action="store_true",
        help="Include content/media nodes whose ChromiumRL inViewport flag is false",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Load one snapshot, apply configured projection limits, and write text."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rendered = ModelSnapshotRenderer(
        load_snapshot(args.input),
        max_actions=args.max_actions,
        max_secondary_actions=args.max_secondary_actions,
        max_nested_actions=args.max_nested_actions,
        max_content_blocks=args.max_content_blocks,
        max_table_rows=args.max_table_rows,
        max_media=args.max_media,
        max_scroll_regions=args.max_scroll_regions,
        max_cell_chars=args.max_cell_chars,
        max_text_chars=args.max_text_chars,
        include_refs=args.include_refs,
        include_secondary=args.include_secondary,
        include_offscreen_content=args.include_offscreen_content,
        suppress_authoring=args.suppress_authoring,
        chrome_label_max_chars=args.chrome_label_max_chars,
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
