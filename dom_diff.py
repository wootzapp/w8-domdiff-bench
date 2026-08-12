"""Pure structured-snapshot comparison and DOM-diff artifact generation."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from artifacts import write_json, write_text
from recorder_errors import RunnerError

def snapshot_endpoint(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Select the stable endpoint metadata stored beside each diff."""
    return {
        "snapshot_id": snapshot.get("snapshotId"),
        "document_revision": snapshot.get("documentRevision"),
        "url": snapshot.get("url"),
    }


DOM_DIFF_SOURCE = "runner_snapshot_diff"
DOM_DIFF_INTERVAL = "before_snapshot_to_after_snapshot"
DOM_DIFF_FIELDS = (
    "tag",
    "role",
    "accessibleName",
    "directText",
    "selectedAttributes",
    "states",
    "actionTypes",
    "semanticBoundary",
)
ORDER_INSENSITIVE_DOM_FIELDS = {"selectedAttributes", "states", "actionTypes"}


class SnapshotIdentityError(RunnerError):
    def __init__(self, side: str, problems: list[dict[str, Any]]):
        """Carry every path-safety problem instead of emitting a misleading diff."""
        super().__init__(f"{side} snapshot cannot be assigned safe unique node paths")
        self.side = side
        self.problems = problems


def load_snapshot_file(path: Path) -> dict[str, Any]:
    """Accept wrapped and bare captureStructuredSnapshot JSON formats."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RunnerError(f"snapshot file is not a JSON object: {path}")
    result = data.get("result")
    if isinstance(result, dict) and isinstance(result.get("snapshot"), dict):
        return result["snapshot"]
    if isinstance(data.get("snapshot"), dict):
        return data["snapshot"]
    if isinstance(data.get("nodes"), list):
        return data
    raise RunnerError(f"snapshot file has no result.snapshot, snapshot, or nodes[]: {path}")


def clean_dom_text(value: Any) -> str:
    """Normalize whitespace for matching while preserving visible characters."""
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def node_tag(node: dict[str, Any]) -> str:
    """Return a path-safe lowercase tag, using '?' when capture omitted it."""
    return clean_dom_text(node.get("tag") or "?").lower().replace("/", "_")


def canonical_dom_value(field: str, value: Any) -> Any:
    """Canonicalize unordered node facts so array ordering is not a false change."""
    if field not in ORDER_INSENSITIVE_DOM_FIELDS or not isinstance(value, list):
        return value
    normalized = [
        {key: item[key] for key in sorted(item)} if isinstance(item, dict) else item
        for item in value
    ]
    return sorted(
        normalized,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def compared_node_fields(node: dict[str, Any], *, omit_empty: bool = False) -> dict[str, Any]:
    """Select semantic fields; geometry, ids, order, and subtreeText are excluded."""
    fields: dict[str, Any] = {}
    for field in DOM_DIFF_FIELDS:
        value = canonical_dom_value(field, node.get(field))
        if omit_empty and value in (None, "", [], {}):
            continue
        fields[field] = value
    return fields


def collision_node(node: dict[str, Any]) -> dict[str, Any]:
    """Keep enough raw identity facts to diagnose an unsafe path collision."""
    return {
        "ref": node.get("ref"),
        "parentRef": node.get("parentRef"),
        "childRefs": node.get("childRefs"),
        **compared_node_fields(node, omit_empty=True),
    }


def stable_node_anchor(node: dict[str, Any]) -> str:
    """Return a short own-content discriminator without inherited AX labels.

    Accessible names routinely propagate from a focused descendant to broad
    ancestors. Using those inherited labels in every ancestor segment renames a
    whole tree when a modal opens. Own direct text is safe; an accessible name is
    used only for a leaf, semantic node, or real non-scroll control.
    """
    direct = clean_dom_text(node.get("directText"))
    value = direct
    if not value:
        role = clean_dom_text(node.get("role")).lower()
        semantic = clean_dom_text(node.get("semanticBoundary")).lower()
        actions = [
            clean_dom_text(action).lower()
            for action in node.get("actionTypes", []) or []
            if clean_dom_text(action).lower() != "scroll"
        ]
        has_children = bool(node.get("childRefs") or [])
        meaningful_role = role not in {
            "",
            "application",
            "document",
            "generic",
            "main",
            "none",
        }
        if not has_children or semantic or actions or meaningful_role:
            value = clean_dom_text(node.get("accessibleName"))
    value = value.casefold()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:20]


def build_snapshot_path_index(
    snapshot: dict[str, Any], *, side: str
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Build unique content-anchored paths and reject inconsistent trees.

    Own text anchors keep siblings stable after insertions. Duplicate or missing
    anchors fall back to sibling positions; any remaining collision fails loudly.
    """
    nodes = [node for node in snapshot.get("nodes", []) if isinstance(node, dict)]
    by_ref: dict[str, dict[str, Any]] = {}
    problems: list[dict[str, Any]] = []
    for node in nodes:
        raw_ref = node.get("ref")
        if raw_ref in (None, ""):
            problems.append({"kind": "missing_ref", "nodes": [collision_node(node)]})
            continue
        ref = str(raw_ref)
        if ref in by_ref:
            problems.append(
                {
                    "kind": "duplicate_ref",
                    "ref": ref,
                    "nodes": [collision_node(by_ref[ref]), collision_node(node)],
                }
            )
            continue
        by_ref[ref] = node

    node_position = {ref: position for position, ref in enumerate(by_ref)}

    def child_order(ref: str) -> tuple[int, int]:
        """Order unlisted children by captured source order, then input position."""
        try:
            source_order = int(by_ref[ref].get("sourceOrder", node_position[ref]) or node_position[ref])
        except (TypeError, ValueError):
            source_order = node_position[ref]
        return source_order, node_position[ref]

    children_from_parent: dict[str, list[str]] = {ref: [] for ref in by_ref}
    for ref, node in by_ref.items():
        parent_ref = node.get("parentRef")
        if parent_ref is not None and str(parent_ref) in by_ref:
            children_from_parent[str(parent_ref)].append(ref)

    ordered_children: dict[str, list[str]] = {}
    for ref, node in by_ref.items():
        child_refs = [str(value) for value in node.get("childRefs", []) or []]
        duplicate_children = sorted({value for value in child_refs if child_refs.count(value) > 1})
        if duplicate_children:
            problems.append(
                {
                    "kind": "duplicate_child_ref",
                    "parent_ref": ref,
                    "child_refs": duplicate_children,
                    "nodes": [collision_node(node)],
                }
            )
        listed_children: list[str] = []
        for child_ref in child_refs:
            child = by_ref.get(child_ref)
            if child is None:
                continue
            if str(child.get("parentRef")) != ref:
                problems.append(
                    {
                        "kind": "parent_child_disagreement",
                        "parent_ref": ref,
                        "child_ref": child_ref,
                        "nodes": [collision_node(node), collision_node(child)],
                    }
                )
                continue
            if child_ref not in listed_children:
                listed_children.append(child_ref)

        all_children = children_from_parent[ref]
        if set(listed_children) == set(all_children):
            ordered_children[ref] = listed_children
        else:
            # captureStructuredSnapshot can clip a large parent's childRefs when
            # maxNodes is reached while still returning some of those children.
            # parentRef preserves containment; sourceOrder reconstructs their
            # document order without using either value as a cross-snapshot key.
            ordered_children[ref] = sorted(all_children, key=child_order)

    root_refs: list[str] = []
    for value in snapshot.get("roots", []) or []:
        ref = str(value)
        if ref in by_ref and ref not in root_refs:
            root_refs.append(ref)
    for ref, node in by_ref.items():
        parent_ref = node.get("parentRef")
        if (parent_ref is None or str(parent_ref) not in by_ref) and ref not in root_refs:
            root_refs.append(ref)

    identity_stats = {
        "nodes": len(by_ref),
        "anchored_nodes": 0,
        "positional_nodes": 0,
        "duplicate_anchor_bases": 0,
        "duplicate_anchor_nodes": 0,
        "path_collisions": 0,
    }
    paths_by_ref: dict[str, str] = {}
    visiting: set[str] = set()

    def sibling_segments(refs: list[str]) -> dict[str, str]:
        """Assign anchored path segments, numbering only duplicate anchors/tags."""
        bases = [
            (node_tag(by_ref[ref]), stable_node_anchor(by_ref[ref]))
            for ref in refs
        ]
        totals = Counter(base for base in bases if base[1])
        duplicate_bases = {base: count for base, count in totals.items() if count > 1}
        identity_stats["duplicate_anchor_bases"] += len(duplicate_bases)
        identity_stats["duplicate_anchor_nodes"] += sum(duplicate_bases.values())
        anchored_seen: Counter[tuple[str, str]] = Counter()
        positional_seen: Counter[str] = Counter()
        segments: dict[str, str] = {}
        for ref, (tag, anchor) in zip(refs, bases):
            if anchor:
                anchored_seen[(tag, anchor)] += 1
                segments[ref] = f"{tag}{{{anchor}}}[{anchored_seen[(tag, anchor)]}]"
                identity_stats["anchored_nodes"] += 1
            else:
                positional_seen[tag] += 1
                segments[ref] = f"{tag}[{positional_seen[tag]}]"
                identity_stats["positional_nodes"] += 1
        return segments

    def walk(ref: str, path: str) -> None:
        """Traverse once while detecting cycles and multiply reached nodes."""
        if ref in visiting:
            problems.append({"kind": "cycle", "path": path, "nodes": [collision_node(by_ref[ref])]})
            return
        if ref in paths_by_ref:
            problems.append(
                {
                    "kind": "node_reached_more_than_once",
                    "path": path,
                    "existing_path": paths_by_ref[ref],
                    "nodes": [collision_node(by_ref[ref])],
                }
            )
            return
        visiting.add(ref)
        paths_by_ref[ref] = path
        child_refs = ordered_children.get(ref, [])
        child_segments = sibling_segments(child_refs)
        for child_ref in child_refs:
            walk(child_ref, f"{path}/{child_segments[child_ref]}")
        visiting.remove(ref)

    root_segments = sibling_segments(root_refs)
    for ref in root_refs:
        walk(ref, root_segments[ref])

    unreachable = [ref for ref in by_ref if ref not in paths_by_ref]
    if unreachable:
        problems.append(
            {
                "kind": "unreachable_nodes",
                "nodes": [collision_node(by_ref[ref]) for ref in unreachable],
            }
        )
    refs_by_path: dict[str, list[str]] = {}
    for ref, path in paths_by_ref.items():
        refs_by_path.setdefault(path, []).append(ref)
    for path, refs in refs_by_path.items():
        if len(refs) > 1:
            identity_stats["path_collisions"] += 1
            problems.append(
                {
                    "kind": "path_collision",
                    "path": path,
                    "nodes": [collision_node(by_ref[ref]) for ref in refs],
                }
            )
    if problems:
        raise SnapshotIdentityError(side, problems)
    return {path: by_ref[ref] for ref, path in paths_by_ref.items()}, identity_stats


def visible_document_text(snapshot: dict[str, Any]) -> list[str]:
    """Collect ordered unique visible facts for cross-document text deltas."""
    rows: list[tuple[int, str]] = []
    for position, node in enumerate(snapshot.get("nodes", []) or []):
        if not isinstance(node, dict) or node.get("visible") is False:
            continue
        direct = clean_dom_text(node.get("directText"))
        subtree = clean_dom_text(node.get("subtreeText"))
        text = direct
        # ChromiumRL can explicitly mark a node truncated while retaining its
        # complete logical row in subtreeText. Prefer that row only when it is
        # a bounded enrichment of the node's own text; this recovers trailing
        # facts without emitting full-page ancestor subtrees.
        if (
            node.get("truncated") is True
            and direct
            and len(subtree) > len(direct)
            and len(subtree) <= max(1200, len(direct) * 4)
        ):
            text = subtree
        if not text:
            role = clean_dom_text(node.get("role")).lower()
            boundary = clean_dom_text(node.get("semanticBoundary")).lower()
            is_fact_node = not (node.get("childRefs") or []) or bool(role or boundary or node.get("actionTypes"))
            if is_fact_node:
                text = clean_dom_text(node.get("accessibleName") or node.get("subtreeText"))
        if text:
            try:
                order = int(node.get("sourceOrder", position) or position)
            except (TypeError, ValueError):
                order = position
            rows.append((order, text))
    seen: set[str] = set()
    result: list[str] = []
    for _order, text in sorted(rows, key=lambda row: row[0]):
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def viewport_node_text(node: dict[str, Any]) -> str:
    """Return a node's own readable viewport fact, never inherited subtree text."""
    text = clean_dom_text(node.get("directText"))
    if not text:
        role = clean_dom_text(node.get("role")).lower()
        boundary = clean_dom_text(node.get("semanticBoundary")).lower()
        actions = node.get("actionTypes") if isinstance(node.get("actionTypes"), list) else []
        is_semantic = bool(role or boundary or actions or not (node.get("childRefs") or []))
        if is_semantic:
            text = clean_dom_text(node.get("accessibleName"))
    if len(text) > MAX_COLLAPSE_TEXT_CHARS:
        return text[: MAX_COLLAPSE_TEXT_CHARS - 1].rstrip() + "…"
    return text


def viewport_membership(node: dict[str, Any]) -> bool | None:
    """Combine structured-snapshot viewport facts without inventing a viewport."""
    if node.get("visible") is False:
        return False
    signals = [
        node.get(field)
        for field in ("inViewport", "hitTestable")
        if isinstance(node.get(field), bool)
    ]
    if not signals:
        return None
    return any(signals)


def numeric_bounds(node: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Parse usable x/y/width/height geometry or return None for partial bounds."""
    bounds = node.get("bounds")
    if not isinstance(bounds, dict):
        return None
    try:
        x, y, width, height = (float(bounds[key]) for key in ("x", "y", "width", "height"))
        return x, y, width, height
    except (KeyError, TypeError, ValueError):
        return None


def viewport_delta(
    before_index: dict[str, dict[str, Any]],
    after_index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Compact viewport evidence derived from the same two structured snapshots.

    Geometry is summarized rather than emitted per node. Readable text is emitted
    only when ChromiumRL's own inViewport/hitTestable facts cross the viewport
    boundary, so a scroll can expose its evidence without turning every shifted
    descendant into a normal semantic node change.
    """
    entered_nodes = 0
    exited_nodes = 0
    in_viewport_changed = 0
    hit_testable_changed = 0
    entered_rows: list[tuple[int, str]] = []
    exited_rows: list[tuple[int, str]] = []
    movement_counts: Counter[tuple[float, float]] = Counter()
    geometry_compared = 0
    shifted_nodes = 0
    dimension_changed_nodes = 0

    for fallback_order, path in enumerate(sorted(set(before_index) & set(after_index))):
        before_node = before_index[path]
        after_node = after_index[path]
        before_member = viewport_membership(before_node)
        after_member = viewport_membership(after_node)
        if (
            isinstance(before_node.get("inViewport"), bool)
            and isinstance(after_node.get("inViewport"), bool)
            and before_node.get("inViewport") != after_node.get("inViewport")
        ):
            in_viewport_changed += 1
        if (
            isinstance(before_node.get("hitTestable"), bool)
            and isinstance(after_node.get("hitTestable"), bool)
            and before_node.get("hitTestable") != after_node.get("hitTestable")
        ):
            hit_testable_changed += 1
        if before_member is not None and after_member is not None and before_member != after_member:
            selected_node = after_node if after_member else before_node
            text = viewport_node_text(selected_node)
            try:
                order = int(selected_node.get("sourceOrder", fallback_order) or fallback_order)
            except (TypeError, ValueError):
                order = fallback_order
            if after_member:
                entered_nodes += 1
                if text:
                    entered_rows.append((order, text))
            else:
                exited_nodes += 1
                if text:
                    exited_rows.append((order, text))

        before_bounds = numeric_bounds(before_node)
        after_bounds = numeric_bounds(after_node)
        if before_bounds is None or after_bounds is None:
            continue
        geometry_compared += 1
        dx = round(after_bounds[0] - before_bounds[0], 1)
        dy = round(after_bounds[1] - before_bounds[1], 1)
        if abs(dx) >= 0.5 or abs(dy) >= 0.5:
            shifted_nodes += 1
            movement_counts[(dx, dy)] += 1
        if abs(after_bounds[2] - before_bounds[2]) >= 0.5 or abs(
            after_bounds[3] - before_bounds[3]
        ) >= 0.5:
            dimension_changed_nodes += 1

    def unique_text(rows: list[tuple[int, str]]) -> list[str]:
        """Preserve document order while removing repeated viewport labels."""
        seen: set[str] = set()
        result: list[str] = []
        for _order, text in sorted(rows, key=lambda row: (row[0], row[1])):
            key = clean_dom_text(text).casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    entered_text = unique_text(entered_rows)
    exited_text = unique_text(exited_rows)
    dominant_shift: dict[str, Any] | None = None
    if movement_counts:
        (dx, dy), count = sorted(
            movement_counts.items(),
            key=lambda item: (-item[1], -abs(item[0][0]) - abs(item[0][1]), item[0]),
        )[0]
        dominant_shift = {
            "delta_x": dx,
            "delta_y": dy,
            "matched_nodes": count,
            "share_of_shifted_nodes_percent": round((count / shifted_nodes) * 100, 2),
        }

    if not (
        entered_nodes
        or exited_nodes
        or in_viewport_changed
        or hit_testable_changed
        or shifted_nodes
        or dimension_changed_nodes
    ):
        return None
    return {
        "aggregation": "structured_snapshot_viewport_flags_and_dominant_geometry_shift",
        "viewport_state": {
            "entered_nodes": entered_nodes,
            "exited_nodes": exited_nodes,
            "in_viewport_changed_nodes": in_viewport_changed,
            "hit_testable_changed_nodes": hit_testable_changed,
            "entered_text_total": len(entered_text),
            "exited_text_total": len(exited_text),
        },
        "geometry": {
            "compared_nodes": geometry_compared,
            "shifted_nodes": shifted_nodes,
            "stationary_nodes": max(0, geometry_compared - shifted_nodes),
            "dimension_changed_nodes": dimension_changed_nodes,
            "movement_clusters_total": len(movement_counts),
            "dominant_shift": dominant_shift,
            "per_node_geometry_emitted": False,
        },
        "visible_text_entered": entered_text,
        "visible_text_exited": exited_text,
    }


MAX_COLLAPSE_DOCUMENT_SHARE = 0.60  # Never hide most of a document under one root.
MAX_COLLAPSE_TEXT_CHARS = 300  # Per collapsed-root preview; raw snapshots remain whole.
MAX_COLLAPSE_CONTROLS = 20  # Interactive samples per root; total count is also recorded.
# Persist every semantic entry. The stored corpus demonstrated that an entry
# count cap discards field-level evidence while all uncapped artifacts still fit
# below the reviewed line threshold. Oversized artifacts are made loud instead
# of being silently shortened.
# Persisted diffs are not cut at this size: it is an audit warning threshold.
MAX_DOM_DIFF_JSON_BYTES = 500 * 1024
# These two caps affect only valid JSON summaries sent back to the model/reviewer.
# dom_diff.json and dom_diff.txt retain every emitted semantic entry.
MAX_MODEL_DOM_DIFF_ENTRIES = 32
MAX_TERMINATION_REVIEW_DIFF_ENTRIES_PER_STEP = 8


def meaningful_diff_node(node: dict[str, Any]) -> bool:
    """Structural wrappers without semantic facts are counted but not emitted."""
    return bool(
        clean_dom_text(node.get("directText"))
        or clean_dom_text(node.get("accessibleName"))
        or node.get("selectedAttributes")
        or node.get("states")
        or node.get("actionTypes")
    )


def node_delta(path: str, node: dict[str, Any]) -> dict[str, Any]:
    """Render one meaningful node as an added/removed diff entry."""
    result: dict[str, Any] = {
        "kind": "node",
        "path": path,
        "node": compared_node_fields(node, omit_empty=True),
    }
    if node.get("repeatedGroupId") not in (None, ""):
        result["repeated_group_id"] = node.get("repeatedGroupId")
        if node.get("repeatedItemIndex") is not None:
            result["repeated_item_index"] = node.get("repeatedItemIndex")
    return result


def child_paths(index: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Derive path children from slash-delimited validated node paths."""
    children: dict[str, list[str]] = {path: [] for path in index}
    for path in index:
        parent, separator, _segment = path.rpartition("/")
        if separator and parent in children:
            children[parent].append(path)
    for rows in children.values():
        rows.sort()
    return children


def operation_subtree(root: str, selected: set[str], children: dict[str, list[str]]) -> list[str]:
    """Return selected descendants of an added/removed root in tree order."""
    found: list[str] = []
    stack = [root]
    while stack:
        path = stack.pop()
        if path not in selected:
            continue
        found.append(path)
        stack.extend(reversed(children.get(path, [])))
    return found


def collapse_visible_text(
    root: str,
    members: list[str],
    index: dict[str, dict[str, Any]],
) -> str:
    """Keep a bounded, deduplicated text preview for one collapsed subtree."""
    node = index[root]
    text = clean_dom_text(node.get("subtreeText") or node.get("directText") or node.get("accessibleName"))
    if not text:
        fragments: list[str] = []
        for path in members:
            fragment = clean_dom_text(index[path].get("directText") or index[path].get("accessibleName"))
            if fragment and fragment not in fragments:
                fragments.append(fragment)
            if len(fragments) >= 5:
                break
        text = " | ".join(fragments)
    if len(text) > MAX_COLLAPSE_TEXT_CHARS:
        text = text[: MAX_COLLAPSE_TEXT_CHARS - 1].rstrip() + "…"
    return text


def compress_tree_operation(
    selected: set[str],
    index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collapse complete added/removed subtrees without hiding most of a document."""
    children = child_paths(index)
    roots = [
        path
        for path in sorted(selected)
        if not (path.rpartition("/")[1] and path.rpartition("/")[0] in selected)
    ]
    emitted: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "noise_nodes_skipped": 0,
        "collapsed_descendants": 0,
        "collapse_roots": [],
    }
    document_nodes = max(1, len(index))

    def emit_root(path: str) -> None:
        """Collapse one subtree unless it exceeds the document-share guard."""
        members = operation_subtree(path, selected, children)
        meaningful_members = [member for member in members if meaningful_diff_node(index[member])]
        if not meaningful_members:
            stats["noise_nodes_skipped"] += len(members)
            return
        share = len(members) / document_nodes
        selected_children = [child for child in children.get(path, []) if child in selected]
        if share > MAX_COLLAPSE_DOCUMENT_SHARE and selected_children:
            if meaningful_diff_node(index[path]):
                emitted.append(node_delta(path, index[path]))
            else:
                stats["noise_nodes_skipped"] += 1
            for child in selected_children:
                emit_root(child)
            return
        if len(members) == 1:
            if meaningful_diff_node(index[path]):
                emitted.append(node_delta(path, index[path]))
            else:
                stats["noise_nodes_skipped"] += 1
            return

        interactive: list[str] = []
        for member in members:
            node = index[member]
            actions = node.get("actionTypes") if isinstance(node.get("actionTypes"), list) else []
            if not actions:
                continue
            label = clean_dom_text(node.get("directText") or node.get("accessibleName"))[:120]
            interactive.append(
                f"{member} | actions={','.join(str(action) for action in actions)} | label={label}"
            )
            if len(interactive) >= MAX_COLLAPSE_CONTROLS:
                break
        entry = node_delta(path, index[path])
        entry.update(
            {
                "kind": "subtree",
                "descendant_count": len(members) - 1,
                "subtree_node_count": len(members),
                "document_percent": round(share * 100, 2),
                "visible_text": collapse_visible_text(path, members, index),
                "interactive_descendants": interactive,
                "interactive_descendants_total": sum(
                    1 for member in members if index[member].get("actionTypes")
                ),
            }
        )
        emitted.append(entry)
        stats["collapsed_descendants"] += len(members) - 1
        stats["collapse_roots"].append(
            {
                "path": path,
                "descendant_count": len(members) - 1,
                "document_percent": round(share * 100, 2),
            }
        )

    for root in roots:
        emit_root(root)
    return emitted, stats


def repeated_signature(entry: dict[str, Any]) -> str:
    """Describe the generic shape of a repeated-group diff entry."""
    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
    fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else {}
    signature = {
        "kind": entry.get("kind", "node"),
        "tag": node.get("tag"),
        "role": node.get("role"),
        "changed_fields": sorted(fields),
    }
    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def condense_repeated_groups(
    entries: list[dict[str, Any]], operation: str
) -> tuple[list[dict[str, Any]], int]:
    """Combine same-shaped repeated items while preserving samples and counts."""
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in entries:
        group_id = entry.get("repeated_group_id")
        if group_id in (None, ""):
            continue
        buckets.setdefault((str(group_id), repeated_signature(entry)), []).append(entry)
    condensed: list[dict[str, Any]] = []
    consumed: set[int] = set()
    members_condensed = 0
    for entry in entries:
        if id(entry) in consumed:
            continue
        group_id = entry.get("repeated_group_id")
        bucket = buckets.get((str(group_id), repeated_signature(entry)), []) if group_id not in (None, "") else []
        if len(bucket) < 2:
            condensed.append(entry)
            continue
        consumed.update(id(item) for item in bucket)
        members_condensed += len(bucket)
        sample: list[str] = []
        for item in bucket[:3]:
            sample.append(
                f"path={item.get('path')} visible_text={clean_dom_text(item.get('visible_text'))[:120]}"
            )
        condensed.append(
            {
                "kind": "repeated_group",
                "operation": operation,
                "repeated_group_id": group_id,
                "signature": json.loads(repeated_signature(entry)),
                "count": len(bucket),
                "item_indices": [
                    item.get("repeated_item_index")
                    for item in bucket
                    if item.get("repeated_item_index") is not None
                ],
                "sample_paths": [item.get("path") for item in bucket[:5]],
                "sample_summaries": sample,
            }
        )
    return condensed, members_condensed


def semantic_fingerprint(node: dict[str, Any]) -> str:
    """Serialize compared semantic facts for conservative relocation matching."""
    return json.dumps(
        compared_node_fields(node, omit_empty=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def path_distance(before_path: str, after_path: str) -> tuple[int, int, str, str]:
    """Structural distance used only among already-identical semantic nodes."""
    before_parts = before_path.split("/")
    after_parts = after_path.split("/")
    common = 0
    for before_part, after_part in zip(before_parts, after_parts):
        if before_part != after_part:
            break
        common += 1
    return (
        len(before_parts) + len(after_parts) - (2 * common),
        abs(len(before_parts) - len(after_parts)),
        before_path,
        after_path,
    )


def match_relocated_paths(old_paths: list[str], new_paths: list[str]) -> list[tuple[str, str]]:
    """Pair duplicate semantic nodes by nearest tree position, not arbitrary zip order."""
    candidates = sorted(
        (path_distance(old_path, new_path), old_path, new_path)
        for old_path in old_paths
        for new_path in new_paths
    )
    paired_old: set[str] = set()
    paired_new: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for _distance, old_path, new_path in candidates:
        if old_path in paired_old or new_path in paired_new:
            continue
        paired_old.add(old_path)
        paired_new.add(new_path)
        pairs.append((old_path, new_path))
        if len(pairs) >= min(len(old_paths), len(new_paths)):
            break
    return pairs


def entry_text_fragment(entry: dict[str, Any], *, limit: int = 180) -> str:
    """Recoverable semantic summary for ranked selection and dropped evidence."""
    candidates: list[str] = []
    for key in ("visible_text", "sample_summaries"):
        value = entry.get(key)
        if isinstance(value, list):
            candidates.extend(clean_dom_text(item) for item in value)
        else:
            candidates.append(clean_dom_text(value))
    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
    for key in ("directText", "accessibleName"):
        candidates.append(clean_dom_text(node.get(key)))
    fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else {}
    for key in ("directText", "accessibleName", "selectedAttributes", "states", "actionTypes"):
        change = fields.get(key)
        if not isinstance(change, dict):
            continue
        for side in ("after", "before"):
            value = change.get(side)
            if value not in (None, "", [], {}):
                candidates.append(clean_dom_text(json.dumps(value, ensure_ascii=False)))
    fragment = next((value for value in candidates if value), "")
    return fragment if len(fragment) <= limit else fragment[: limit - 1].rstrip() + "…"


def entry_priority(entry: dict[str, Any]) -> tuple[int, int, int, int, str]:
    """Semantic facts outrank wrapper/path-only entries before truncation."""
    fragment = entry_text_fragment(entry)
    fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else {}
    node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
    has_action = bool(node.get("actionTypes") or "actionTypes" in fields)
    has_state = bool(node.get("states") or "states" in fields)
    has_numeric = bool(re.search(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?!\w)", fragment))
    has_text = bool(fragment)
    score = (8 if has_action else 0) + (6 if has_state else 0) + (4 if has_numeric else 0) + (2 if has_text else 0)
    return (-score, -int(has_text), -int(has_numeric), -int(has_state or has_action), str(entry.get("path", "")))


def dropped_entry_summary(operation: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Retain paths and text for any entry omitted from a bounded prompt view."""
    paths = entry.get("sample_paths") if isinstance(entry.get("sample_paths"), list) else []
    path = clean_dom_text(entry.get("path"))
    return {
        "operation": operation,
        "kind": entry.get("kind", "node"),
        "paths": [path] if path else [str(item) for item in paths],
        "text_fragment": entry_text_fragment(entry),
    }


def truncate_diff_entries(
    added: list[dict[str, Any]],
    removed: list[dict[str, Any]],
    changed: list[dict[str, Any]],
    *,
    max_entries: int | None = None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
    list[dict[str, Any]],
]:
    """Balance and rank optional bounded output without starving an operation.

    Persisted diffs call this with ``max_entries=None``. A numeric limit is used
    only by bounded consumers, and every omitted item receives a recoverable
    path/text summary.
    """
    operations = {"added": added, "removed": removed, "changed": changed}
    ranked = {operation: sorted(rows, key=entry_priority) for operation, rows in operations.items()}
    before = {operation: len(rows) for operation, rows in ranked.items()}
    nonempty = [operation for operation, rows in ranked.items() if rows]
    kept: dict[str, list[dict[str, Any]]] = {operation: [] for operation in operations}
    selected_ids: set[int] = set()
    limit = None if max_entries is None else max(0, int(max_entries))

    if limit is None or sum(before.values()) <= limit:
        kept = ranked
        selected_ids = {id(entry) for rows in kept.values() for entry in rows}
    elif limit and nonempty:
        guaranteed_share = max(1, limit // (2 * len(nonempty)))
        for operation in nonempty:
            for entry in ranked[operation][:guaranteed_share]:
                kept[operation].append(entry)
                selected_ids.add(id(entry))
        remaining = limit - len(selected_ids)
        candidates = sorted(
            (
                entry_priority(entry),
                operation,
                position,
                entry,
            )
            for operation in nonempty
            for position, entry in enumerate(ranked[operation])
            if id(entry) not in selected_ids
        )
        for _priority, operation, _position, entry in candidates[:remaining]:
            kept[operation].append(entry)
            selected_ids.add(id(entry))
        for rows in kept.values():
            rows.sort(key=entry_priority)
    truncated = {
        operation: before[operation] - len(kept[operation])
        for operation in ("added", "removed", "changed")
    }
    dropped = [
        dropped_entry_summary(operation, entry)
        for operation, rows in ranked.items()
        for entry in rows
        if id(entry) not in selected_ids
    ]
    return kept["added"], kept["removed"], kept["changed"], truncated, dropped


def model_diff_entry_summary(operation: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Compact one diff entry without cutting its JSON representation."""
    summary: dict[str, Any] = {
        "operation": operation,
        "kind": entry.get("kind", "node"),
    }
    for key in ("path", "path_before", "path_after"):
        value = clean_dom_text(entry.get(key))
        if value:
            summary[key] = value[:400]
    sample_paths = entry.get("sample_paths")
    if isinstance(sample_paths, list) and sample_paths:
        summary["sample_paths"] = [clean_dom_text(path)[:400] for path in sample_paths[:3]]
    fragment = entry_text_fragment(entry, limit=320)
    if fragment:
        summary["text_fragment"] = fragment
    fields = entry.get("fields")
    if isinstance(fields, dict) and fields:
        summary["changed_fields"] = sorted(str(name) for name in fields)
    node = entry.get("node")
    if isinstance(node, dict):
        facts: dict[str, Any] = {}
        for key in ("tag", "role", "semanticBoundary"):
            value = clean_dom_text(node.get(key))
            if value:
                facts[key] = value
        for key in ("actionTypes", "states"):
            value = node.get(key)
            if value not in (None, [], {}):
                facts[key] = value
        if facts:
            summary["node"] = facts
    for key in ("count", "descendant_count", "document_percent", "signature"):
        if entry.get(key) not in (None, ""):
            summary[key] = entry[key]
    return summary


def bounded_dom_diff_for_model(
    record: dict[str, Any] | None,
    *,
    max_entries: int = MAX_MODEL_DOM_DIFF_ENTRIES,
) -> dict[str, Any]:
    """Build valid, bounded JSON evidence from a potentially large DOM diff."""
    if not isinstance(record, dict) or not record:
        return {}

    compression = record.get("compression") if isinstance(record.get("compression"), dict) else {}
    diff = record.get("diff") if isinstance(record.get("diff"), dict) else {}
    text_delta = diff.get("text_delta") if isinstance(diff.get("text_delta"), dict) else {}
    summary: dict[str, Any] = {
        "status": record.get("status"),
        "action_type": record.get("action_type"),
        "totals": record.get("totals", {}),
        "emitted_counts": record.get("emitted_counts", {}),
        "entries_truncated": compression.get(
            "entries_truncated", text_delta.get("truncated", {})
        ),
    }

    viewport = diff.get("viewport_delta") if isinstance(diff.get("viewport_delta"), dict) else {}
    if viewport:
        summary["viewport_delta"] = {
            "aggregation": viewport.get("aggregation"),
            "viewport_state": viewport.get("viewport_state", {}),
            "geometry": viewport.get("geometry", {}),
        }

    operations: dict[str, list[dict[str, Any]]] = {}
    for operation in ("added", "removed", "changed"):
        rows = diff.get(operation)
        if isinstance(rows, list):
            operations[operation] = [row for row in rows if isinstance(row, dict)]
    for operation, key in (("added_text", "added"), ("removed_text", "removed")):
        rows = text_delta.get(key)
        if isinstance(rows, list):
            operations[operation] = [
                {
                    "kind": "text",
                    "path": f"{operation}[{position}]",
                    "node": {"directText": clean_dom_text(value)},
                }
                for position, value in enumerate(rows, start=1)
                if clean_dom_text(value)
            ]
    for operation, key in (
        ("viewport_entered", "visible_text_entered"),
        ("viewport_exited", "visible_text_exited"),
    ):
        rows = viewport.get(key)
        if isinstance(rows, list):
            operations[operation] = [
                {
                    "kind": "viewport_text",
                    "path": f"{operation}[{position}]",
                    "node": {"directText": clean_dom_text(value)},
                }
                for position, value in enumerate(rows, start=1)
                if clean_dom_text(value)
            ]

    ranked = {
        operation: sorted(rows, key=entry_priority)
        for operation, rows in operations.items()
        if rows
    }
    available = {operation: len(rows) for operation, rows in ranked.items()}
    selected: dict[str, list[dict[str, Any]]] = {operation: [] for operation in ranked}
    selected_keys: set[tuple[str, int]] = set()
    nonempty = list(ranked)
    limit = max(0, int(max_entries))
    if limit and sum(available.values()) <= limit:
        selected = {operation: list(rows) for operation, rows in ranked.items()}
    elif limit and nonempty:
        guaranteed_share = max(1, limit // (2 * len(nonempty)))
        for operation in nonempty:
            for position, entry in enumerate(ranked[operation][:guaranteed_share]):
                selected[operation].append(entry)
                selected_keys.add((operation, position))
        remaining = max(0, limit - sum(len(rows) for rows in selected.values()))
        candidates = sorted(
            (
                entry_priority(entry),
                operation,
                position,
                entry,
            )
            for operation, rows in ranked.items()
            for position, entry in enumerate(rows)
            if (operation, position) not in selected_keys
        )
        for _priority, operation, _position, entry in candidates[:remaining]:
            selected[operation].append(entry)

    included = {operation: len(rows) for operation, rows in selected.items()}
    summary["model_evidence"] = {
        "entry_limit": limit,
        "available_counts": available,
        "included_counts": included,
        "entries_truncated": {
            operation: available[operation] - included.get(operation, 0)
            for operation in available
        },
        "selection": "balanced_operation_share_then_entry_priority",
        "entries": [
            model_diff_entry_summary(operation, entry)
            for operation, rows in selected.items()
            for entry in sorted(rows, key=entry_priority)
        ],
    }
    return summary


def bounded_dom_diff_history_for_review(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep evidence from every executed step in valid, bounded JSON.

    The artifact itself is never truncated. Only the separate reviewer prompt is
    bounded per step, so an early source page remains available in cross-site
    tasks without allowing one large navigation diff to consume the whole input.
    """
    history: list[dict[str, Any]] = []
    for step, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        history.append(
            {
                "step": step,
                "before": record.get("before", {}),
                "after": record.get("after", {}),
                "evidence": bounded_dom_diff_for_model(
                    record,
                    max_entries=MAX_TERMINATION_REVIEW_DIFF_ENTRIES_PER_STEP,
                ),
            }
        )
    return history


def unsafe_identity_record(
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    errors: list[SnapshotIdentityError],
    *,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Emit an explicit non-diff record when node identity cannot be trusted."""
    return {
        "source": DOM_DIFF_SOURCE,
        "interval": DOM_DIFF_INTERVAL,
        "status": "unsafe_node_identity",
        "action_type": action_type,
        "geometry_excluded": True,
        "covers_live_control_state": False,
        "before": snapshot_endpoint(before_snapshot),
        "after": snapshot_endpoint(after_snapshot),
        "change_count": 0,
        "totals": {"added": 0, "removed": 0, "changed": 0, "changes": 0},
        "emitted_counts": {"added": 0, "removed": 0, "changed": 0, "changes": 0},
        "diff": {
            "errors": [
                {"side": error.side, "message": str(error), "problems": error.problems}
                for error in errors
            ]
        },
    }


def same_document_except_fragment(before_url: str, after_url: str) -> bool:
    """Return whether only the URL fragment may differ."""
    before = urlsplit(before_url)
    after = urlsplit(after_url)
    return (
        before.scheme.lower(),
        before.netloc.lower(),
        before.path,
        before.query,
    ) == (
        after.scheme.lower(),
        after.netloc.lower(),
        after.path,
        after.query,
    )


def dom_diff_record(
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    *,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Compute a deterministic semantic diff from two stored snapshots.

    Cross-document navigation uses a text delta because node paths cannot carry
    identity across documents. Fragment-only navigation stays in the same-node
    path so newly visible viewport text is retained.
    """
    before_endpoint = snapshot_endpoint(before_snapshot)
    after_endpoint = snapshot_endpoint(after_snapshot)
    indexes: dict[str, dict[str, dict[str, Any]]] = {}
    identity_stats: dict[str, dict[str, int]] = {}
    identity_errors: list[SnapshotIdentityError] = []
    for side, snapshot in (("before", before_snapshot), ("after", after_snapshot)):
        try:
            indexes[side], identity_stats[side] = build_snapshot_path_index(snapshot, side=side)
        except SnapshotIdentityError as error:
            identity_errors.append(error)
    if identity_errors:
        return unsafe_identity_record(
            before_snapshot, after_snapshot, identity_errors, action_type=action_type
        )

    common_metadata = {
        "source": DOM_DIFF_SOURCE,
        "interval": DOM_DIFF_INTERVAL,
        "action_type": action_type,
        "geometry_excluded": True,
        "covers_live_control_state": False,
        "identity": {
            "strategy": "own_content_or_semantic_anchor_with_positional_fallback",
            "before": identity_stats["before"],
            "after": identity_stats["after"],
        },
    }

    if before_endpoint["url"] != after_endpoint["url"] and not same_document_except_fragment(
        before_endpoint["url"], after_endpoint["url"]
    ):
        before_nodes = [node for node in before_snapshot.get("nodes", []) if isinstance(node, dict)]
        after_nodes = [node for node in after_snapshot.get("nodes", []) if isinstance(node, dict)]
        before_text = visible_document_text(before_snapshot)
        after_text = visible_document_text(after_snapshot)
        before_text_set = set(before_text)
        after_text_set = set(after_text)
        removed_text = [text for text in before_text if text not in after_text_set]
        added_text = [text for text in after_text if text not in before_text_set]
        totals = {
            "removed_nodes": len(before_nodes),
            "added_nodes": len(after_nodes),
            "removed_text": len(removed_text),
            "added_text": len(added_text),
        }
        change_count = len(before_nodes) + len(after_nodes)
        # Navigation is already represented as a compact text delta rather than
        # node records. Keep all unique captured text so relevant evidence is not
        # lost to an arbitrary per-side prefix cap.
        # Preserve each captured row verbatim: clipping by character count can
        # remove the decisive tail of an otherwise retained fact while saving
        # no JSON/TXT lines at all.
        emitted_removed_text = list(removed_text)
        emitted_added_text = list(added_text)
        return {
            **common_metadata,
            "status": "document_replaced",
            "before": before_endpoint,
            "after": after_endpoint,
            "change_count": change_count,
            "totals": totals,
            "emitted_counts": {
                "removed_nodes": 0,
                "added_nodes": 0,
                "removed_text": len(emitted_removed_text),
                "added_text": len(emitted_added_text),
            },
            "diff": {
                "navigation": {"from": before_endpoint["url"], "to": after_endpoint["url"]},
                "removed_node_count": len(before_nodes),
                "added_node_count": len(after_nodes),
                "text_delta": {
                    "removed": emitted_removed_text,
                    "added": emitted_added_text,
                    "removed_total": len(removed_text),
                    "added_total": len(added_text),
                    "truncated": {"removed": 0, "added": 0},
                },
            },
        }

    before_index = indexes["before"]
    after_index = indexes["after"]
    before_keys = set(before_index)
    after_keys = set(after_index)
    added_keys = after_keys - before_keys
    removed_keys = before_keys - after_keys
    raw_added_before_relocation_match = len(added_keys)
    raw_removed_before_relocation_match = len(removed_keys)
    removed_by_fingerprint: dict[str, list[str]] = {}
    added_by_fingerprint: dict[str, list[str]] = {}
    for path in sorted(removed_keys):
        if meaningful_diff_node(before_index[path]):
            removed_by_fingerprint.setdefault(semantic_fingerprint(before_index[path]), []).append(path)
    for path in sorted(added_keys):
        if meaningful_diff_node(after_index[path]):
            added_by_fingerprint.setdefault(semantic_fingerprint(after_index[path]), []).append(path)
    relocated_nodes_suppressed = 0
    for fingerprint, old_paths in removed_by_fingerprint.items():
        new_paths = added_by_fingerprint.get(fingerprint, [])
        for old_path, new_path in match_relocated_paths(old_paths, new_paths):
            removed_keys.discard(old_path)
            added_keys.discard(new_path)
            relocated_nodes_suppressed += 1
    raw_changed: list[dict[str, Any]] = []
    subtree_text_changes_ignored = 0
    for path in sorted(before_keys & after_keys):
        before_fields = compared_node_fields(before_index[path])
        after_fields = compared_node_fields(after_index[path])
        field_changes = {
            field: {"before": before_fields[field], "after": after_fields[field]}
            for field in DOM_DIFF_FIELDS
            if before_fields[field] != after_fields[field]
        }
        if field_changes:
            entry: dict[str, Any] = {"kind": "node", "path": path, "fields": field_changes}
            after_node = after_index[path]
            if after_node.get("repeatedGroupId") not in (None, ""):
                entry["repeated_group_id"] = after_node.get("repeatedGroupId")
                if after_node.get("repeatedItemIndex") is not None:
                    entry["repeated_item_index"] = after_node.get("repeatedItemIndex")
            raw_changed.append(entry)
        elif clean_dom_text(before_index[path].get("subtreeText")) != clean_dom_text(
            after_index[path].get("subtreeText")
        ):
            subtree_text_changes_ignored += 1

    added, added_stats = compress_tree_operation(added_keys, after_index)
    removed, removed_stats = compress_tree_operation(removed_keys, before_index)
    changed: list[dict[str, Any]] = []
    changed_noise_skipped = 0
    for entry in raw_changed:
        path = str(entry["path"])
        if meaningful_diff_node(before_index[path]) or meaningful_diff_node(after_index[path]):
            changed.append(entry)
        else:
            changed_noise_skipped += 1
    added, added_group_members = condense_repeated_groups(added, "added")
    removed, removed_group_members = condense_repeated_groups(removed, "removed")
    changed, changed_group_members = condense_repeated_groups(changed, "changed")
    viewport = viewport_delta(before_index, after_index)
    viewport_state = (
        viewport.get("viewport_state")
        if isinstance(viewport, dict) and isinstance(viewport.get("viewport_state"), dict)
        else {}
    )
    viewport_change_count = int(viewport_state.get("entered_text_total") or 0) + int(
        viewport_state.get("exited_text_total") or 0
    )
    emitted_before_truncation = {
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
    }
    added, removed, changed, entries_truncated, dropped_entries = truncate_diff_entries(
        added, removed, changed
    )

    totals = {
        "added": len(added_keys),
        "removed": len(removed_keys),
        "changed": len(raw_changed),
        "semantic_changes": len(added_keys) + len(removed_keys) + len(raw_changed),
        "viewport_text_changed": viewport_change_count,
        "changes": len(added_keys) + len(removed_keys) + len(raw_changed) + viewport_change_count,
    }
    emitted_counts = {
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "viewport_text_changed": viewport_change_count,
        "changes": len(added) + len(removed) + len(changed) + viewport_change_count,
    }
    status = "changes_present" if totals["semantic_changes"] else "no_dom_change"
    if not totals["semantic_changes"] and viewport_change_count:
        status = "viewport_content_changed"
    elif not totals["changes"] and str(action_type or "").lower() == "scroll":
        status = "no_semantic_change_scroll"
    diff: dict[str, Any] = {"added": added, "removed": removed, "changed": changed}
    if viewport:
        diff["viewport_delta"] = viewport
    return {
        **common_metadata,
        "status": status,
        "before": before_endpoint,
        "after": after_endpoint,
        "change_count": totals["changes"],
        "semantic_change_count": totals["semantic_changes"],
        "viewport_change_count": viewport_change_count,
        "totals": totals,
        "emitted_counts": emitted_counts,
        "compression": {
            "subtree_text_changes_ignored": subtree_text_changes_ignored,
            "raw_added_before_relocation_match": raw_added_before_relocation_match,
            "raw_removed_before_relocation_match": raw_removed_before_relocation_match,
            "relocated_nodes_suppressed": relocated_nodes_suppressed,
            "relocation_matching": "structural_nearest_within_semantic_fingerprint",
            "noise_nodes_skipped": (
                added_stats["noise_nodes_skipped"]
                + removed_stats["noise_nodes_skipped"]
                + changed_noise_skipped
            ),
            "collapsed_descendants": (
                added_stats["collapsed_descendants"] + removed_stats["collapsed_descendants"]
            ),
            "repeated_group_members_condensed": (
                added_group_members + removed_group_members + changed_group_members
            ),
            "emitted_before_truncation": emitted_before_truncation,
            "entries_truncated": entries_truncated,
            "entry_limit": None,
            "truncation_selection": "none_all_semantic_entries_emitted",
            "dropped_entries": dropped_entries,
            "max_collapse_document_percent": max(
                (
                    float(item["document_percent"])
                    for item in [
                        *added_stats["collapse_roots"],
                        *removed_stats["collapse_roots"],
                    ]
                ),
                default=0.0,
            ),
            "collapse_roots": [
                *(
                    f"operation=added path={item['path']} "
                    f"descendant_count={item['descendant_count']} "
                    f"document_percent={item['document_percent']}"
                    for item in added_stats["collapse_roots"]
                ),
                *(
                    f"operation=removed path={item['path']} "
                    f"descendant_count={item['descendant_count']} "
                    f"document_percent={item['document_percent']}"
                    for item in removed_stats["collapse_roots"]
                ),
            ],
        },
        "diff": diff,
    }


def dom_diff_text(record: dict[str, Any]) -> str:
    """Render the JSON diff as one verifier-friendly fact per line."""
    def encoded(value: Any) -> str:
        """Serialize nested facts deterministically on a single line."""
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    lines = [
        f"source: {record.get('source')}",
        f"interval: {record.get('interval')}",
        f"status: {record.get('status')}",
        f"action_type: {record.get('action_type')}",
        f"geometry_excluded: {str(bool(record.get('geometry_excluded'))).lower()}",
        f"covers_live_control_state: {str(bool(record.get('covers_live_control_state'))).lower()}",
        f"before: {encoded(record.get('before'))}",
        f"after: {encoded(record.get('after'))}",
        f"change_count: {record.get('change_count', 0)}",
        f"totals: {encoded(record.get('totals', {}))}",
        f"emitted_counts: {encoded(record.get('emitted_counts', {}))}",
        f"identity: {encoded(record.get('identity', {}))}",
        f"compression: {encoded(record.get('compression', {}))}",
    ]
    diff = record.get("diff") if isinstance(record.get("diff"), dict) else {}
    if record.get("status") == "document_replaced":
        lines.append(f"navigation: {encoded(diff.get('navigation'))}")
        lines.append(f"removed_node_count: {diff.get('removed_node_count', 0)}")
        lines.append(f"added_node_count: {diff.get('added_node_count', 0)}")
        text_delta = diff.get("text_delta") if isinstance(diff.get("text_delta"), dict) else {}
        lines.extend(f"text_removed: {encoded(text)}" for text in text_delta.get("removed", []) or [])
        lines.extend(f"text_added: {encoded(text)}" for text in text_delta.get("added", []) or [])
    elif record.get("status") == "unsafe_node_identity":
        lines.extend(f"identity_error: {encoded(error)}" for error in diff.get("errors", []) or [])
    else:
        lines.extend(f"node_added: {encoded(item)}" for item in diff.get("added", []) or [])
        lines.extend(f"node_removed: {encoded(item)}" for item in diff.get("removed", []) or [])
        for item in diff.get("changed", []) or []:
            path = item.get("path")
            fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
            for field, change in fields.items():
                lines.append(f"node_changed: path={encoded(path)} field={field} change={encoded(change)}")
        viewport = diff.get("viewport_delta") if isinstance(diff.get("viewport_delta"), dict) else {}
        if viewport:
            lines.append(f"viewport_state: {encoded(viewport.get('viewport_state', {}))}")
            lines.append(f"viewport_geometry: {encoded(viewport.get('geometry', {}))}")
            lines.extend(
                f"visible_text_entered: {encoded(text)}"
                for text in viewport.get("visible_text_entered", []) or []
            )
            lines.extend(
                f"visible_text_exited: {encoded(text)}"
                for text in viewport.get("visible_text_exited", []) or []
            )
    return "\n".join(lines).rstrip() + "\n"


def write_dom_diff_files(
    before_path: Path,
    after_path: Path,
    json_path: Path,
    *,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Generate matching JSON/TXT diffs and record size without truncating them."""
    record = dom_diff_record(
        load_snapshot_file(before_path),
        load_snapshot_file(after_path),
        action_type=action_type,
    )
    record["artifact"] = {
        "max_json_bytes": MAX_DOM_DIFF_JSON_BYTES,
        "json_bytes": 0,
        "json_lines": 0,
        "over_size_limit": False,
    }
    # The metadata itself contributes bytes and can change digit width. Settle
    # both informational LOC and the enforced byte measurement before writing.
    for _ in range(5):
        serialized = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        record["artifact"]["json_lines"] = len(serialized.splitlines())
        record["artifact"]["json_bytes"] = len(serialized.encode("utf-8"))
        record["artifact"]["over_size_limit"] = (
            record["artifact"]["json_bytes"] > MAX_DOM_DIFF_JSON_BYTES
        )
    write_json(json_path, record)
    write_text(json_path.with_suffix(".txt"), dom_diff_text(record))
    return record
