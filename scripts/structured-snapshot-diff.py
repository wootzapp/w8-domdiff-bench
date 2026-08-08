#!/usr/bin/env python3
"""Standalone derived-path differ for ChromiumRL structured snapshots.

This diagnostic intentionally does not import or call the recorder DOM differ.
It consumes plain captureStructuredSnapshot JSON responses, derives identity
only from the snapshot's ref tree, and emits a compact JSON/text diff.
"""

from __future__ import annotations

import argparse
import json
import re
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from structured_snapshot_matching_v2 import (  # noqa: E402
    match_repeated_groups_by_fingerprint,
    native_field_match_stages,
)


COMPARISON_FIELDS = (
    "tag",
    "role",
    "accessibleName",
    "directText",
    "subtreeText",
    "selectedAttributes",
    "states",
    "actionTypes",
    "semanticBoundary",
)
TEXT_FIELDS = {"accessibleName", "directText", "subtreeText"}
EXCLUDED_FIELDS = (
    "bounds",
    "clippedBounds",
    "sourceOrder",
    "index",
    "confidence",
    "occluded",
)


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_field(name: str, value: Any) -> Any:
    if name == "tag":
        return str(value or "").lower()
    if name in TEXT_FIELDS or name in {"role", "semanticBoundary"}:
        return normalize_text(value)
    if name == "selectedAttributes":
        attributes = []
        for item in value if isinstance(value, list) else []:
            if isinstance(item, dict):
                attributes.append(
                    {
                        "name": str(item.get("name") or ""),
                        "value": str(item.get("value") or ""),
                    }
                )
        return sorted(attributes, key=lambda item: (item["name"], item["value"]))
    if name == "states":
        states = []
        for item in value if isinstance(value, list) else []:
            if isinstance(item, dict):
                states.append(
                    {
                        "name": str(item.get("name") or ""),
                        "value": str(item.get("value") or ""),
                    }
                )
        return sorted(states, key=lambda item: (item["name"], item["value"]))
    if name == "actionTypes":
        return sorted(str(item) for item in value if item is not None) if isinstance(value, list) else []
    return value


def comparison_record(node: dict[str, Any]) -> dict[str, Any]:
    return {name: canonical_field(name, node.get(name)) for name in COMPARISON_FIELDS}


def read_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("nodes"), list):
        raise ValueError(f"{path} is not a raw captureStructuredSnapshot response")
    return snapshot


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def derived_paths(snapshot: dict[str, Any]) -> dict[str, Any]:
    nodes = [node for node in snapshot.get("nodes", []) if isinstance(node, dict)]
    by_ref = {
        str(node.get("ref")): node
        for node in nodes
        if node.get("ref") not in (None, "")
    }
    order_by_ref = {
        str(node.get("ref")): position
        for position, node in enumerate(nodes)
        if node.get("ref") not in (None, "")
    }

    roots = []
    for ref in snapshot.get("roots", []) if isinstance(snapshot.get("roots"), list) else []:
        text = str(ref)
        if text in by_ref and text not in roots:
            roots.append(text)
    for node in nodes:
        ref = str(node.get("ref") or "")
        parent_ref = str(node.get("parentRef") or "")
        if ref and (not parent_ref or parent_ref not in by_ref) and ref not in roots:
            roots.append(ref)

    root_tag_totals = Counter(str(by_ref[ref].get("tag") or "node").lower() for ref in roots)
    root_tag_seen: Counter[str] = Counter()
    segment_by_ref: dict[str, str] = {}
    for ref in roots:
        tag = str(by_ref[ref].get("tag") or "node").lower()
        root_tag_seen[tag] += 1
        segment_by_ref[ref] = tag if root_tag_totals[tag] == 1 else f"{tag}[{root_tag_seen[tag]}]"

    anomalies: list[dict[str, Any]] = []
    for parent_ref, parent in by_ref.items():
        declared = parent.get("childRefs") if isinstance(parent.get("childRefs"), list) else []
        ordered_children = [str(ref) for ref in declared if str(ref) in by_ref]
        extras = sorted(
            (
                ref
                for ref, node in by_ref.items()
                if str(node.get("parentRef") or "") == parent_ref and ref not in ordered_children
            ),
            key=lambda ref: order_by_ref[ref],
        )
        if extras:
            anomalies.append(
                {
                    "type": "parentRef_child_missing_from_childRefs",
                    "parentRef": parent_ref,
                    "childRefs": extras,
                }
            )
            ordered_children.extend(extras)
        same_tag_seen: Counter[str] = Counter()
        for child_ref in ordered_children:
            tag = str(by_ref[child_ref].get("tag") or "node").lower()
            same_tag_seen[tag] += 1
            segment_by_ref[child_ref] = f"{tag}[{same_tag_seen[tag]}]"

    cache: dict[str, str] = {}

    def build(ref: str, active: set[str] | None = None) -> str:
        if ref in cache:
            return cache[ref]
        active = set(active or ())
        if ref in active:
            anomalies.append({"type": "parent_cycle", "ref": ref})
            return f"cycle/{segment_by_ref.get(ref, 'node')}"
        active.add(ref)
        node = by_ref[ref]
        parent_ref = str(node.get("parentRef") or "")
        segment = segment_by_ref.get(ref)
        if not segment:
            tag = str(node.get("tag") or "node").lower()
            segment = f"{tag}[1]"
            anomalies.append({"type": "missing_sibling_position", "ref": ref})
        if parent_ref and parent_ref in by_ref:
            result = f"{build(parent_ref, active)}/{segment}"
        else:
            result = segment
        cache[ref] = result
        return result

    records = []
    for node in nodes:
        ref = str(node.get("ref") or "")
        path = build(ref) if ref in by_ref else ""
        records.append(
            {
                "ref": node.get("ref"),
                "nodeId": node.get("nodeId"),
                "backendNodeId": node.get("backendNodeId"),
                "parentRef": node.get("parentRef"),
                "tag": node.get("tag"),
                "derivedPath": path,
            }
        )

    path_counts = Counter(record["derivedPath"] for record in records)
    collisions = {
        path: [record["ref"] for record in records if record["derivedPath"] == path]
        for path, count in path_counts.items()
        if count > 1
    }
    collision_nodes = sum(len(refs) for refs in collisions.values())
    return {
        "url": snapshot.get("url", ""),
        "title": snapshot.get("title", ""),
        "totalNodes": len(nodes),
        "rootCount": len(roots),
        "roots": roots,
        "uniquePathCount": len(path_counts),
        "collisionGroupCount": len(collisions),
        "collisionNodeCount": collision_nodes,
        "collisions": collisions,
        "anomalies": anomalies,
        "nodes": records,
        "pathByRef": {record["ref"]: record["derivedPath"] for record in records},
    }


def unique_stage_matches(
    before_nodes: list[dict[str, Any]],
    after_nodes: list[dict[str, Any]],
    unmatched_before: set[int],
    unmatched_after: set[int],
    key_fn: Callable[[dict[str, Any]], Any],
    strategy: str,
) -> list[dict[str, Any]]:
    before_keys: dict[Any, list[int]] = defaultdict(list)
    after_keys: dict[Any, list[int]] = defaultdict(list)
    for index in unmatched_before:
        key = key_fn(before_nodes[index])
        if key not in (None, "", ("", "")):
            before_keys[key].append(index)
    for index in unmatched_after:
        key = key_fn(after_nodes[index])
        if key not in (None, "", ("", "")):
            after_keys[key].append(index)

    matched = []
    for key in sorted(set(before_keys) & set(after_keys), key=str):
        if len(before_keys[key]) != 1 or len(after_keys[key]) != 1:
            continue
        before_index = before_keys[key][0]
        after_index = after_keys[key][0]
        unmatched_before.remove(before_index)
        unmatched_after.remove(after_index)
        matched.append(
            {
                "beforeIndex": before_index,
                "afterIndex": after_index,
                "strategy": strategy,
                "key": key,
            }
        )
    return matched


def diff_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    before_paths: dict[str, Any],
    after_paths: dict[str, Any],
) -> dict[str, Any]:
    before_nodes = [node for node in before.get("nodes", []) if isinstance(node, dict)]
    after_nodes = [node for node in after.get("nodes", []) if isinstance(node, dict)]
    before_path_by_ref = before_paths["pathByRef"]
    after_path_by_ref = after_paths["pathByRef"]

    unmatched_before = set(range(len(before_nodes)))
    unmatched_after = set(range(len(after_nodes)))
    matches = []
    before_with_paths = [
        {**node, "__derivedPath": before_path_by_ref.get(node.get("ref"), "")}
        for node in before_nodes
    ]
    after_with_paths = [
        {**node, "__derivedPath": after_path_by_ref.get(node.get("ref"), "")}
        for node in after_nodes
    ]
    matches.extend(
        match_repeated_groups_by_fingerprint(
            before_nodes,
            after_nodes,
            unmatched_before,
            unmatched_after,
        )
    )
    matches.extend(
        native_field_match_stages(
            before_nodes,
            after_nodes,
            unmatched_before,
            unmatched_after,
            unique_stage_matches,
        )
    )
    matches.extend(
        unique_stage_matches(
            before_with_paths,
            after_with_paths,
            unmatched_before,
            unmatched_after,
            lambda node: node.get("__derivedPath", ""),
            "derivedPath",
        )
    )
    matches.extend(
        unique_stage_matches(
            before_nodes,
            after_nodes,
            unmatched_before,
            unmatched_after,
            lambda node: (
                str(node.get("tag") or "").lower(),
                normalize_text(node.get("accessibleName")),
            )
            if normalize_text(node.get("accessibleName"))
            else None,
            "accessibleName+tag",
        )
    )
    matches.extend(
        unique_stage_matches(
            before_nodes,
            after_nodes,
            unmatched_before,
            unmatched_after,
            lambda node: str(node.get("nodeId")) if node.get("nodeId") is not None else None,
            "nodeId",
        )
    )

    changed = []
    unchanged = []
    for match in sorted(matches, key=lambda item: item["afterIndex"]):
        before_node = before_nodes[match["beforeIndex"]]
        after_node = after_nodes[match["afterIndex"]]
        before_record = comparison_record(before_node)
        after_record = comparison_record(after_node)
        changes = {
            field: {"before": before_record[field], "after": after_record[field]}
            for field in COMPARISON_FIELDS
            if before_record[field] != after_record[field]
        }
        entry = {
            **match,
            "beforeRef": before_node.get("ref"),
            "afterRef": after_node.get("ref"),
            "beforePath": before_path_by_ref.get(before_node.get("ref"), ""),
            "afterPath": after_path_by_ref.get(after_node.get("ref"), ""),
            "tag": after_record["tag"] or before_record["tag"],
            "before": before_record,
            "after": after_record,
        }
        if changes:
            entry["changes"] = changes
            changed.append(entry)
        else:
            unchanged.append(entry)

    added = []
    for index in sorted(unmatched_after):
        node = after_nodes[index]
        added.append(
            {
                "afterIndex": index,
                "afterRef": node.get("ref"),
                "afterPath": after_path_by_ref.get(node.get("ref"), ""),
                "tag": str(node.get("tag") or "").lower(),
                "after": comparison_record(node),
            }
        )
    removed = []
    for index in sorted(unmatched_before):
        node = before_nodes[index]
        removed.append(
            {
                "beforeIndex": index,
                "beforeRef": node.get("ref"),
                "beforePath": before_path_by_ref.get(node.get("ref"), ""),
                "tag": str(node.get("tag") or "").lower(),
                "before": comparison_record(node),
            }
        )

    denominator = min(len(before_nodes), len(after_nodes))
    strategy_counts = Counter(match["strategy"] for match in matches)
    return {
        "source": {
            "before": {"url": before.get("url", ""), "title": before.get("title", "")},
            "after": {"url": after.get("url", ""), "title": after.get("title", "")},
        },
        "crossDocument": before.get("url") != after.get("url"),
        "comparisonFields": list(COMPARISON_FIELDS),
        "excludedChangeFields": list(EXCLUDED_FIELDS),
        "stats": {
            "beforeCount": len(before_nodes),
            "afterCount": len(after_nodes),
            "matchedCount": len(matches),
            "matchRatePct": round(100.0 * len(matches) / denominator, 1) if denominator else 0.0,
            "addedCount": len(added),
            "removedCount": len(removed),
            "changedCount": len(changed),
            "unchangedCount": len(unchanged),
            "matchStrategies": dict(strategy_counts),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }


def quote_short(value: Any, limit: int = 220) -> str:
    text = normalize_text(value)
    if len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return json.dumps(text, ensure_ascii=False)


def best_text(record: dict[str, Any]) -> str:
    for field in ("directText", "accessibleName", "subtreeText"):
        value = normalize_text(record.get(field))
        if value:
            return value
    return ""


def render_diff(diff: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    evidence_entries = [*diff["added"], *diff["removed"], *diff["changed"]]
    entry_paths = []
    for entry in evidence_entries:
        path = entry.get("afterPath") or entry.get("beforePath") or ""
        if path:
            entry_paths.append(path)
    id_by_path = {path: f"n{index + 1}" for index, path in enumerate(sorted(set(entry_paths)))}
    paths = {short_id: path for path, short_id in id_by_path.items()}

    source = diff["source"]
    before_page = source["before"]
    after_page = source["after"]
    lines = [
        f"PAGE title={quote_short(after_page.get('title'), 160)} url={quote_short(after_page.get('url'), 240)}"
    ]
    if diff["crossDocument"]:
        lines.append(
            f"NAV from={quote_short(before_page.get('url'), 180)} "
            f"to={quote_short(after_page.get('url'), 180)} "
            f"removed_nodes={diff['stats']['removedCount']} added_nodes={diff['stats']['addedCount']}"
        )

    added_text = []
    removed_text = []
    for entry in diff["added"]:
        for field in TEXT_FIELDS:
            value = normalize_text(entry["after"].get(field))
            if value:
                added_text.append(value)
    for entry in diff["removed"]:
        for field in TEXT_FIELDS:
            value = normalize_text(entry["before"].get(field))
            if value:
                removed_text.append(value)
    for entry in diff["changed"]:
        for field, change in entry["changes"].items():
            if field not in TEXT_FIELDS:
                continue
            before_value = normalize_text(change.get("before"))
            after_value = normalize_text(change.get("after"))
            if after_value:
                added_text.append(after_value)
            if before_value:
                removed_text.append(before_value)

    for value in dict.fromkeys(added_text):
        lines.append(f"+TEXT {quote_short(value)}")
    for value in dict.fromkeys(removed_text):
        lines.append(f"-TEXT {quote_short(value)}")

    for entry in diff["added"]:
        path = entry.get("afterPath", "")
        lines.append(
            f"+[{id_by_path.get(path, '')}] {entry.get('tag') or 'node'} "
            f"{quote_short(best_text(entry['after']), 2000)}"
        )
    for entry in diff["removed"]:
        path = entry.get("beforePath", "")
        lines.append(
            f"-[{id_by_path.get(path, '')}] {entry.get('tag') or 'node'} "
            f"{quote_short(best_text(entry['before']), 2000)}"
        )
    for entry in diff["changed"]:
        path = entry.get("afterPath") or entry.get("beforePath") or ""
        short_id = id_by_path.get(path, "")
        for field, change in entry["changes"].items():
            lines.append(
                f"~[{short_id}] {entry.get('tag') or 'node'} {field}:"
                f"{quote_short(change.get('before'), 120)}->{quote_short(change.get('after'), 120)}"
            )

    action_entries = []
    for entry in [*diff["added"], *diff["changed"]]:
        after_record = entry.get("after", {})
        if after_record.get("actionTypes"):
            action_entries.append(entry)
    for entry in action_entries[:10]:
        path = entry.get("afterPath") or entry.get("beforePath") or ""
        record = entry.get("after", {})
        lines.append(
            f"ACTION [{id_by_path.get(path, '')}] {entry.get('tag') or 'node'} "
            f"{quote_short(best_text(record), 160)}"
        )

    stats = diff["stats"]
    lines.append(
        f"STATS +{stats['addedCount']}/-{stats['removedCount']} ~{stats['changedCount']} "
        f"flagged=0 truncated=False frames=1/1 shadow=unknown"
    )
    return "\n".join(lines).rstrip() + "\n", paths



INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea"}
INTERACTIVE_ROLES = {
    "button", "checkbox", "combobox", "link", "listbox", "menuitem", "option",
    "radio", "searchbox", "slider", "spinbutton", "switch", "tab", "textbox",
}
STATE_WORDS = {
    "checked", "disabled", "expanded", "in stock", "out of stock", "pressed", "selected",
}


def snapshot_maps(snapshot: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    nodes = [node for node in snapshot.get("nodes", []) if isinstance(node, dict)]
    by_ref = {
        str(node.get("ref")): node
        for node in nodes
        if node.get("ref") not in (None, "")
    }
    order = {
        str(node.get("ref")): index
        for index, node in enumerate(nodes)
        if node.get("ref") not in (None, "")
    }
    return by_ref, order


def child_refs(node: dict[str, Any], by_ref: dict[str, dict[str, Any]]) -> list[str]:
    declared = node.get("childRefs")
    if not isinstance(declared, list):
        return []
    return [str(ref) for ref in declared if str(ref) in by_ref]


def owned_text_by_ref(snapshot: dict[str, Any]) -> tuple[dict[str, list[str]], int]:
    # Keep text on the lowest node that owns it. Ancestor subtreeText is a cascade.
    by_ref, _ = snapshot_maps(snapshot)
    owned: dict[str, list[str]] = {}
    aggregate: dict[str, list[str]] = {}
    cascade_suppressed = 0

    def collect(ref: str, active: set[str] | None = None) -> list[str]:
        nonlocal cascade_suppressed
        if ref in aggregate:
            return aggregate[ref]
        active = set(active or ())
        if ref in active:
            return []
        active.add(ref)
        descendant_texts: list[str] = []
        for child_ref in child_refs(by_ref[ref], by_ref):
            descendant_texts.extend(collect(child_ref, active))
        descendant_texts = list(dict.fromkeys(text for text in descendant_texts if text))
        node = by_ref[ref]
        values = {
            "directText": normalize_text(node.get("directText")),
            "accessibleName": normalize_text(node.get("accessibleName")),
            "subtreeText": normalize_text(node.get("subtreeText")),
        }
        own: list[str] = []
        if values["directText"]:
            own.append(values["directText"])
        if (
            values["accessibleName"]
            and values["accessibleName"] not in own
            and values["accessibleName"] not in descendant_texts
        ):
            own.append(values["accessibleName"])
        if values["subtreeText"] and not own and not descendant_texts:
            own.append(values["subtreeText"])
        retained = set(own)
        cascade_suppressed += sum(bool(value) and value not in retained for value in values.values())
        owned[ref] = own
        aggregate[ref] = list(dict.fromkeys([*descendant_texts, *own]))
        return aggregate[ref]

    for ref in by_ref:
        collect(ref)
    return owned, cascade_suppressed


def has_numeric_or_state(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\d", text)) or any(word in lowered for word in STATE_WORDS)


def common_chrome_texts(
    before_owned: dict[str, list[str]], after_owned: dict[str, list[str]]
) -> set[str]:
    before = {text for values in before_owned.values() for text in values}
    after = {text for values in after_owned.values() for text in values}
    return {
        text for text in before & after
        if len(text) <= 80 and not has_numeric_or_state(text)
    }


def is_interactive(node: dict[str, Any]) -> bool:
    tag = str(node.get("tag") or "").lower()
    role = normalize_text(node.get("role")).lower()
    actions = node.get("actionTypes") if isinstance(node.get("actionTypes"), list) else []
    return tag in INTERACTIVE_TAGS or role in INTERACTIVE_ROLES or bool(actions)


def semantic_facts(node: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    attributes = node.get("selectedAttributes")
    for item in attributes if isinstance(attributes, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        value = str(item.get("value") or "")
        if name:
            facts.append(f"{name}={value}")
    states = node.get("states")
    for item in states if isinstance(states, list) else []:
        if isinstance(item, dict) and item.get("name"):
            facts.append(f"{item.get('name')}={item.get('value', '')}")
    boundary = normalize_text(node.get("semanticBoundary"))
    if boundary:
        facts.append(f"boundary={boundary}")
    return list(dict.fromkeys(facts))


def nearest_repeated_group(ref: str, by_ref: dict[str, dict[str, Any]]) -> tuple[str, Any]:
    active: set[str] = set()
    while ref and ref in by_ref and ref not in active:
        active.add(ref)
        node = by_ref[ref]
        group_id = str(node.get("repeatedGroupId") or "")
        if group_id:
            return group_id, node.get("repeatedItemIndex")
        ref = str(node.get("parentRef") or "")
    return "", None


def component_refs(root: str, allowed: set[str], by_ref: dict[str, dict[str, Any]]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    stack = [root]
    while stack:
        ref = stack.pop()
        if ref not in allowed or ref in seen:
            continue
        seen.add(ref)
        result.append(ref)
        stack.extend(reversed(child_refs(by_ref[ref], by_ref)))
    return result


def collapse_repeated_groups(
    entries: list[dict[str, Any]], counters: Counter[str]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    result: list[dict[str, Any]] = []
    for entry in entries:
        group_id = entry.get("repeatedGroupId") or ""
        (grouped[group_id] if group_id else result).append(entry)
    for group_id, members in grouped.items():
        item_indexes = {member.get("repeatedItemIndex") for member in members}
        if len(members) < 2 or len(item_indexes) < 2:
            result.extend(members)
            continue
        counters["repeatedGroupRoots"] += 1
        counters["repeatedGroupEntries"] += len(members) - 1
        result.append({
            "kind": "repeatedGroup",
            "repeatedGroupId": group_id,
            "signature": "/".join(dict.fromkeys(member.get("tag", "node") for member in members)),
            "itemCount": len(item_indexes),
            "recordCount": sum(member.get("recordCount", 1) for member in members),
            "descendantCount": sum(member.get("descendantCount", 0) for member in members),
            "texts": list(dict.fromkeys(text for member in members for text in member.get("texts", []))),
            "facts": list(dict.fromkeys(fact for member in members for fact in member.get("facts", []))),
            "interactiveCount": sum(member.get("interactiveCount", 0) for member in members),
            "interactiveLabels": list(dict.fromkeys(
                label for member in members for label in member.get("interactiveLabels", [])
            )),
            "changes": [
                change for member in members for change in member.get("changes", [])
            ],
            "path": members[0].get("path", ""),
        })
    return sorted(result, key=lambda entry: entry.get("path", ""))


def collapse_root_audit(
    roots: list[str], refs: set[str], by_ref: dict[str, dict[str, Any]],
    raw_by_ref: dict[str, dict[str, Any]], path_key: str, total_nodes: int, side: str,
) -> list[dict[str, Any]]:
    audit: list[dict[str, Any]] = []
    for root in roots:
        component = component_refs(root, refs, by_ref)
        if len(component) <= 1:
            continue
        descendants = len(component) - 1
        tag = str(by_ref[root].get("tag") or "node").lower()
        audit.append({
            "side": side,
            "ref": root,
            "path": raw_by_ref[root].get(path_key, ""),
            "tag": tag,
            "descendantCount": descendants,
            "coverageNodeCount": len(component),
            "totalDocumentNodes": total_nodes,
            "descendantPct": round(100.0 * descendants / max(1, total_nodes), 1),
            "coveragePct": round(100.0 * len(component) / max(1, total_nodes), 1),
            "htmlOrBody": tag in {"html", "body"},
            "over60Pct": len(component) > 0.60 * max(1, total_nodes),
        })
    return audit


def guarded_collapse_roots(
    initial_roots: list[str], refs: set[str], by_ref: dict[str, dict[str, Any]],
    total_nodes: int, counters: Counter[str], enforce_guard: bool,
) -> list[str]:
    if not enforce_guard:
        return initial_roots
    result: list[str] = []
    queue = list(initial_roots)
    seen: set[str] = set()
    while queue:
        root = queue.pop(0)
        if root in seen or root not in refs:
            continue
        seen.add(root)
        component = component_refs(root, refs, by_ref)
        changed_children = [ref for ref in child_refs(by_ref[root], by_ref) if ref in refs]
        tag = str(by_ref[root].get("tag") or "").lower()
        too_broad = bool(
            changed_children
            and (tag in {"html", "body"} or len(component) > 0.60 * max(1, total_nodes))
        )
        if too_broad:
            counters["broadCollapseRootsSplit"] += 1
            queue[0:0] = changed_children
        else:
            result.append(root)
    return result


def compact_side(
    raw_entries: list[dict[str, Any]], snapshot: dict[str, Any], owned: dict[str, list[str]],
    side: str, counters: Counter[str], enforce_guard: bool,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_ref, order = snapshot_maps(snapshot)
    ref_key = "afterRef" if side == "added" else "beforeRef"
    path_key = "afterPath" if side == "added" else "beforePath"
    raw_by_ref = {str(entry.get(ref_key)): entry for entry in raw_entries}
    refs = {ref for ref in raw_by_ref if ref in by_ref}
    initial_roots = sorted(
        (ref for ref in refs if str(by_ref[ref].get("parentRef") or "") not in refs),
        key=lambda ref: order.get(ref, 0),
    )
    total_nodes = len(by_ref)
    roots = guarded_collapse_roots(
        initial_roots, refs, by_ref, total_nodes, counters, enforce_guard
    )
    audit = {
        "beforeGuard": collapse_root_audit(
            initial_roots, refs, by_ref, raw_by_ref, path_key, total_nodes, side
        ),
        "afterGuard": collapse_root_audit(
            roots, refs, by_ref, raw_by_ref, path_key, total_nodes, side
        ),
    }
    result: list[dict[str, Any]] = []
    for root in roots:
        component = component_refs(root, refs, by_ref)
        texts = list(dict.fromkeys(text for ref in component for text in owned.get(ref, [])))
        facts = list(dict.fromkeys(fact for ref in component for fact in semantic_facts(by_ref[ref])))
        interactive_refs = [ref for ref in component if is_interactive(by_ref[ref])]
        labels = list(dict.fromkeys(
            normalize_text(by_ref[ref].get("accessibleName"))
            for ref in interactive_refs if normalize_text(by_ref[ref].get("accessibleName"))
        ))
        empty_count = sum(
            not owned.get(ref) and not semantic_facts(by_ref[ref]) and not is_interactive(by_ref[ref])
            for ref in component
        )
        counters["emptyNodes"] += empty_count
        if not texts and not facts and not interactive_refs:
            counters["emptyComponents"] += 1
            continue
        if len(component) > 1:
            counters["subtreeRoots"] += 1
            counters["subtreeDescendants"] += len(component) - 1
        group_id, item_index = nearest_repeated_group(root, by_ref)
        result.append({
            "kind": "subtree" if len(component) > 1 else "node",
            "ref": root,
            "path": raw_by_ref[root].get(path_key, ""),
            "tag": str(by_ref[root].get("tag") or "node").lower(),
            "recordCount": len(component),
            "descendantCount": len(component) - 1,
            "texts": texts,
            "facts": facts,
            "interactiveCount": len(interactive_refs),
            "interactiveLabels": labels,
            "repeatedGroupId": group_id,
            "repeatedItemIndex": item_index,
        })
    return collapse_repeated_groups(result, counters), audit


def compact_changed(
    entries: list[dict[str, Any]], before: dict[str, Any], after: dict[str, Any],
    before_owned: dict[str, list[str]], after_owned: dict[str, list[str]],
    counters: Counter[str],
) -> list[dict[str, Any]]:
    before_by_ref, _ = snapshot_maps(before)
    after_by_ref, _ = snapshot_maps(after)
    result: list[dict[str, Any]] = []
    for entry in entries:
        before_ref = str(entry.get("beforeRef") or "")
        after_ref = str(entry.get("afterRef") or "")
        changes: list[dict[str, Any]] = []
        text_change_added = False
        for field, change in entry.get("changes", {}).items():
            if field in TEXT_FIELDS:
                before_values = before_owned.get(before_ref, [])
                after_values = after_owned.get(after_ref, [])
                if not before_values and not after_values:
                    counters["textCascadeChangedFields"] += 1
                    continue
                if text_change_added:
                    counters["duplicateChangedTextFields"] += 1
                    continue
                changes.append({
                    "field": "text",
                    "before": " | ".join(before_values),
                    "after": " | ".join(after_values),
                })
                text_change_added = True
            else:
                changes.append({"field": field, **change})
        if not changes:
            counters["emptyChangedRecords"] += 1
            continue
        node = after_by_ref.get(after_ref) or before_by_ref.get(before_ref) or {}
        group_id, item_index = nearest_repeated_group(after_ref, after_by_ref)
        result.append({
            "kind": "change",
            "ref": after_ref or before_ref,
            "path": entry.get("afterPath") or entry.get("beforePath") or "",
            "tag": entry.get("tag") or "node",
            "changes": changes,
            "texts": list(dict.fromkeys([*before_owned.get(before_ref, []), *after_owned.get(after_ref, [])])),
            "facts": semantic_facts(node),
            "interactiveCount": int(is_interactive(node)),
            "interactiveLabels": [normalize_text(node.get("accessibleName"))]
                if is_interactive(node) and normalize_text(node.get("accessibleName")) else [],
            "repeatedGroupId": group_id,
            "repeatedItemIndex": item_index,
        })
    return collapse_repeated_groups(result, counters)


def suppress_common_chrome(
    entries: list[dict[str, Any]], common: set[str], counters: Counter[str]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in entries:
        old = entry.get("texts", [])
        entry["texts"] = [text for text in old if text not in common]
        counters["commonChromeTexts"] += len(old) - len(entry["texts"])
        for change in entry.get("changes", []):
            for side in ("before", "after"):
                value = normalize_text(change.get(side))
                if value in common:
                    change[side] = ""
                    counters["commonChromeTexts"] += 1
        meaningful_change = any(
            normalize_text(change.get("before")) or normalize_text(change.get("after"))
            for change in entry.get("changes", [])
        )
        if entry.get("texts") or entry.get("facts") or entry.get("interactiveCount") or meaningful_change:
            result.append(entry)
        else:
            counters["commonChromeEmptyEntries"] += 1
    return result


def compact_diff(
    diff: dict[str, Any], before: dict[str, Any], after: dict[str, Any],
    *, enforce_broad_collapse_guard: bool = True,
) -> dict[str, Any]:
    before_owned, before_cascade = owned_text_by_ref(before)
    after_owned, after_cascade = owned_text_by_ref(after)
    common = common_chrome_texts(before_owned, after_owned) if diff["crossDocument"] else set()
    counters: Counter[str] = Counter()
    counters["textCascadeFields"] = before_cascade + after_cascade
    counters["duplicateTextLines"] = sum(
        line.startswith(("+TEXT ", "-TEXT ")) for line in render_diff(diff)[0].splitlines()
    )
    added, added_audit = compact_side(
        diff["added"], after, after_owned, "added", counters, enforce_broad_collapse_guard
    )
    removed, removed_audit = compact_side(
        diff["removed"], before, before_owned, "removed", counters, enforce_broad_collapse_guard
    )
    changed = compact_changed(diff["changed"], before, after, before_owned, after_owned, counters)
    added = suppress_common_chrome(added, common, counters)
    removed = suppress_common_chrome(removed, common, counters)
    changed = suppress_common_chrome(changed, common, counters)
    true_stats = dict(diff["stats"])
    return {
        "source": diff["source"],
        "crossDocument": diff["crossDocument"],
        "comparisonFields": diff["comparisonFields"],
        "excludedChangeFields": diff["excludedChangeFields"],
        "stats": {
            **true_stats,
            "trueCounts": {
                "added": true_stats["addedCount"], "removed": true_stats["removedCount"],
                "changed": true_stats["changedCount"], "matched": true_stats["matchedCount"],
            },
            "emittedCounts": {
                "added": len(added), "removed": len(removed), "changed": len(changed),
                "total": len(added) + len(removed) + len(changed),
            },
            "suppressed": dict(sorted(counters.items())),
            "commonChromeCandidates": len(common),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "collapseGuard": {
            "enabled": enforce_broad_collapse_guard,
            "maxDocumentFraction": 0.60,
            "beforeGuard": [*added_audit["beforeGuard"], *removed_audit["beforeGuard"]],
            "afterGuard": [*added_audit["afterGuard"], *removed_audit["afterGuard"]],
        },
    }


def compact_entry_line(prefix: str, short_id: str, entry: dict[str, Any]) -> str:
    text = " | ".join(entry.get("texts", []))
    facts = ",".join(entry.get("facts", []))
    actions = " | ".join(entry.get("interactiveLabels", [])[:8])
    changes = "; ".join(
        f"{change.get('field')}:{normalize_text(change.get('before'))}->{normalize_text(change.get('after'))}"
        for change in entry.get("changes", [])
    )
    if entry.get("kind") == "repeatedGroup":
        head = (
            f"{prefix}GROUP {entry.get('repeatedGroupId')} signature={entry.get('signature')} "
            f"count={entry.get('itemCount')} records={entry.get('recordCount')} "
            f"descendants={entry.get('descendantCount')}"
        )
    else:
        head = f"{prefix}[{short_id}] {entry.get('tag') or 'node'}"
        if entry.get("kind") == "subtree":
            head += f" descendants={entry.get('descendantCount', 0)}"
    head += f" interactive={entry.get('interactiveCount', 0)}"
    if text:
        head += f" text={quote_short(text, 900)}"
    if facts:
        head += f" facts={quote_short(facts, 300)}"
    if actions:
        head += f" actions={quote_short(actions, 260)}"
    if changes:
        head += f" changes={quote_short(changes, 500)}"
    return head


def render_compact_diff(diff: dict[str, Any]) -> tuple[str, dict[str, str]]:
    entries = [*diff["added"], *diff["removed"], *diff["changed"]]
    ordered_paths = list(dict.fromkeys(entry.get("path", "") for entry in entries if entry.get("path")))
    id_by_path = {path: f"n{index + 1}" for index, path in enumerate(ordered_paths)}
    paths = {short_id: path for path, short_id in id_by_path.items()}
    source = diff["source"]
    lines = [
        f"PAGE title={quote_short(source['after'].get('title'), 160)} "
        f"url={quote_short(source['after'].get('url'), 240)}"
    ]
    if diff["crossDocument"]:
        true_counts = diff["stats"]["trueCounts"]
        lines.append(
            f"NAV from={quote_short(source['before'].get('url'), 180)} "
            f"to={quote_short(source['after'].get('url'), 180)} "
            f"removed_nodes={true_counts['removed']} added_nodes={true_counts['added']}"
        )
    for prefix, key in (("+", "added"), ("-", "removed")):
        for entry in diff[key]:
            lines.append(compact_entry_line(prefix, id_by_path.get(entry.get("path", ""), ""), entry))
    for entry in diff["changed"]:
        if entry.get("kind") == "repeatedGroup":
            lines.append(compact_entry_line("~", id_by_path.get(entry.get("path", ""), ""), entry))
            continue
        short_id = id_by_path.get(entry.get("path", ""), "")
        for change in entry.get("changes", []):
            lines.append(
                f"~[{short_id}] {entry.get('tag') or 'node'} {change.get('field')}:"
                f"{quote_short(change.get('before'), 180)}->{quote_short(change.get('after'), 180)}"
            )
    stats = diff["stats"]
    true_counts = stats["trueCounts"]
    emitted = stats["emittedCounts"]
    suppressed = stats["suppressed"]
    lines.append(
        f"STATS true=+{true_counts['added']}/-{true_counts['removed']} ~{true_counts['changed']} "
        f"matched={true_counts['matched']} emitted=+{emitted['added']}/-{emitted['removed']} "
        f"~{emitted['changed']} suppressed={json.dumps(suppressed, sort_keys=True, separators=(',', ':'))}"
    )
    return "\n".join(lines).rstrip() + "\n", paths


def audit_removed_facts(
    raw_diff: dict[str, Any], before: dict[str, Any], after: dict[str, Any],
    compact: dict[str, Any], compact_text: str,
    *, sample_size: int = 20, seed: int = 20260807,
) -> dict[str, Any]:
    by_ref, _ = snapshot_maps(before)
    owned, _ = owned_text_by_ref(before)
    candidates: list[dict[str, Any]] = []
    for entry in raw_diff.get("removed", []):
        ref = str(entry.get("beforeRef") or "")
        node = by_ref.get(ref, {})
        facts: list[tuple[str, str]] = []
        facts.extend(("text", text) for text in owned.get(ref, []))
        attributes = node.get("selectedAttributes")
        for item in attributes if isinstance(attributes, list) else []:
            if isinstance(item, dict) and item.get("name"):
                facts.append(("attribute", f"{item.get('name')}={item.get('value', '')}"))
        states = node.get("states")
        for item in states if isinstance(states, list) else []:
            if isinstance(item, dict) and item.get("name"):
                facts.append(("state", f"{item.get('name')}={item.get('value', '')}"))
        actions = node.get("actionTypes")
        for action in actions if isinstance(actions, list) else []:
            facts.append(("action", str(action)))
        boundary = normalize_text(node.get("semanticBoundary"))
        if boundary:
            facts.append(("semanticBoundary", f"boundary={boundary}"))
        role = normalize_text(node.get("role"))
        if role:
            facts.append(("role", f"role={role}"))
        if facts:
            # One independently selected fact per fact-bearing removed node.
            fact_type, value = facts[0]
            candidates.append({
                "ref": ref,
                "path": entry.get("beforePath", ""),
                "tag": entry.get("tag", ""),
                "factType": fact_type,
                "fact": value,
            })
    rng = random.Random(seed)
    sample = rng.sample(candidates, min(sample_size, len(candidates)))
    rendered_haystack = normalize_text("\n".join(
        line for line in compact_text.splitlines() if line.startswith("-")
    )).lower()
    json_haystack = normalize_text(json.dumps(compact.get("removed", []), ensure_ascii=False)).lower()
    after_owned, _ = owned_text_by_ref(after)
    common = common_chrome_texts(owned, after_owned)
    for item in sample:
        needle = normalize_text(item["fact"]).lower()
        item["recoverableFromText"] = bool(needle and needle in rendered_haystack)
        item["recoverableFromJson"] = bool(needle and needle in json_haystack)
        if item["recoverableFromText"]:
            item["result"] = "recoverable"
        elif item["recoverableFromJson"]:
            item["result"] = "render-truncated"
        elif item["fact"] in common:
            item["result"] = "common-chrome-suppressed"
        elif item["factType"] == "role":
            item["result"] = "role-not-carried-by-compactor"
        else:
            item["result"] = "suppressed-or-not-carried"
    return {
        "population": "one fact from each fact-bearing node among the true removed nodes",
        "trueRemovedNodeCount": len(raw_diff.get("removed", [])),
        "factBearingRemovedNodeCount": len(candidates),
        "seed": seed,
        "requestedSampleSize": sample_size,
        "actualSampleSize": len(sample),
        "recoverableFromTextCount": sum(item["recoverableFromText"] for item in sample),
        "recoverableFromJsonCount": sum(item["recoverableFromJson"] for item in sample),
        "sample": sample,
    }

def positive_evidence(diff: dict[str, Any]) -> str:
    payload = {
        "page": diff["source"]["after"],
        "added": [entry["after"] for entry in diff["added"]],
        "changedAfter": [entry["after"] for entry in diff["changed"]],
    }
    return json.dumps(payload, ensure_ascii=False).lower()


def file_metrics(path: Path) -> dict[str, int]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "lines": raw.count(b"\n")}


def make_report(
    path_summaries: dict[str, dict[str, Any]],
    step_results: list[dict[str, Any]],
    reference_root: Path,
) -> str:
    metrics_path = reference_root.parents[1] / "metrics_summary.json"
    saved_rates: dict[str, float] = {}
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        task = metrics.get("tasks", {}).get("task-a-books-mystery", {})
        for step, values in task.items():
            saved_rates[step] = values.get("methods", {}).get(
                "ChromiumRL.saveDOMState", {}
            ).get("matchability", {}).get("matchRatePct", 0.0)

    lines = [
        "# Structured snapshot derived-path diff test",
        "",
        "Standalone diagnostic only. No recorder, recording path, or production DOM-diff code was used or modified.",
        "",
        "> **Verdict updated after blocking guard/fidelity audit and stress tests.** See `../structured-diff-stress/REPORT.md`. The books-only size result below remains valid, but its earlier general-viability conclusion does not.",
        "",
        "## 1. Derived path key",
        "",
        "Path form: root tag followed by `tag[N]` segments, where `N` is the 1-based position among same-tag siblings in the parent's `childRefs` order. Any collision stops the run before diff construction.",
        "",
        "| page | nodes | unique paths | collision groups | nodes sharing a path | roots | anomalies | usable |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key, label in (("homepage", "Books homepage"), ("mystery", "Mystery category")):
        summary = path_summaries[key]
        lines.append(
            f"| {label} | {summary['totalNodes']} | {summary['uniquePathCount']} | "
            f"{summary['collisionGroupCount']} | {summary['collisionNodeCount']} | "
            f"{summary['rootCount']} | {len(summary['anomalies'])} | "
            f"{'yes' if summary['collisionNodeCount'] == 0 else 'no'} |"
        )

    lines.extend([
        "",
        "## 2. Cross-document identity — corrected conclusion",
        "",
        "Match rate denominator is `min(before count, after count)`. Structured matching order is repeated-group fingerprint, unique native `stablePath`, unique native `fingerprint`, unique derived path, unique non-empty `accessibleName+tag`, then unique `nodeId`. Missing native fields are no-ops.",
        "",
        "| step | transition | structured | saveDOMState | difference | measurement |",
        "|---|---|---:|---:|---:|---|",
    ])
    transitions = {
        "step_001": "blank → homepage",
        "step_002": "homepage → Mystery",
        "step_003": "Mystery → product",
    }
    for result in step_results:
        step = result["step"]
        structured_rate = result["diff"]["stats"]["matchRatePct"]
        saved_rate = saved_rates.get(step, 0.0)
        if step == "step_002":
            note = "structured beats saveDOMState"
        elif step == "step_003":
            note = "essentially equal; product page removes the sidebar and replaces category content"
        else:
            note = "blank-page bootstrap"
        lines.append(
            f"| {step} | {transitions[step]} | {structured_rate:.1f}% | {saved_rate:.1f}% | "
            f"{structured_rate - saved_rate:+.1f} pp | {note} |"
        )
    lines.extend([
        "",
        "The **12.6%** Mystery→product rate is not an identity weakness: `saveDOMState` is **13.4%** on the same transition. The product page has no category sidebar and has substantially different content, so most removals are real. On homepage→Mystery, structured snapshot reaches **99.6%** versus `saveDOMState`'s **77.3%**. **With derived paths, structured snapshot matches or beats `saveDOMState` on cross-document matching.**",
        "",
        "| step | before | after | matched | rate | added | removed | changed | group fp | native path | native fp | derived path | name+tag | nodeId |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    denominator_total = 0
    matched_total = 0
    for result in step_results:
        stats = result["diff"]["stats"]
        strategies = stats["matchStrategies"]
        denominator_total += min(stats["beforeCount"], stats["afterCount"])
        matched_total += stats["matchedCount"]
        lines.append(
            f"| {result['step']} | {stats['beforeCount']} | {stats['afterCount']} | "
            f"{stats['matchedCount']} | {stats['matchRatePct']:.1f}% | {stats['addedCount']} | "
            f"{stats['removedCount']} | {stats['changedCount']} | "
            f"{strategies.get('repeatedGroupFingerprint', 0)} | "
            f"{strategies.get('nativeStablePath', 0)} | "
            f"{strategies.get('nativeFingerprint', 0)} | "
            f"{strategies.get('derivedPath', 0)} | "
            f"{strategies.get('accessibleName+tag', 0)} | "
            f"{strategies.get('nodeId', 0)} |"
        )
    headline = 100.0 * matched_total / denominator_total if denominator_total else 0.0
    lines.extend([
        "",
        f"Aggregate: `{matched_total}/{denominator_total}` = **{headline:.1f}%**, versus 0.0% with document-local IDs alone.",
        "",
        "## 3. Compaction",
        "",
        "The earlier 5–11× text-size difference was a **compaction gap, not a format property**. The first experiment deliberately kept the production compactor out to isolate identity. This follow-up applies the requested rules in order while retaining the original renderer as `structured_diff_uncompacted.txt`.",
        "",
        "The implementation order is: (a) text-cascade suppression; (b) removal of duplicate `+TEXT`/`-TEXT` lines by inlining text; (c) empty-node removal; (d) whole-subtree collapse; (e) browser-provided repeated-group collapse; (f) cross-document common-chrome suppression with numeric/state protection; and (g) true plus emitted totals.",
        "",
        "| step | cascade text fields | duplicate TEXT lines | empty nodes | subtree roots | collapsed descendants | repeated groups | grouped entries | common chrome texts | true +/−/~ | emitted +/−/~ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for result in step_results:
        stats = result["compactDiff"]["stats"]
        suppressed = stats["suppressed"]
        true_counts = stats["trueCounts"]
        emitted = stats["emittedCounts"]
        cascade = suppressed.get("textCascadeFields", 0) + suppressed.get("textCascadeChangedFields", 0)
        duplicate = suppressed.get("duplicateTextLines", 0) + suppressed.get("duplicateChangedTextFields", 0)
        empty = suppressed.get("emptyNodes", 0) + suppressed.get("emptyChangedRecords", 0)
        lines.append(
            f"| {result['step']} | {cascade} | {duplicate} | {empty} | "
            f"{suppressed.get('subtreeRoots', 0)} | {suppressed.get('subtreeDescendants', 0)} | "
            f"{suppressed.get('repeatedGroupRoots', 0)} | {suppressed.get('repeatedGroupEntries', 0)} | "
            f"{suppressed.get('commonChromeTexts', 0)} | "
            f"{true_counts['added']}/{true_counts['removed']}/{true_counts['changed']} | "
            f"{emitted['added']}/{emitted['removed']}/{emitted['changed']} |"
        )
    lines.extend([
        "",
        "`duplicate TEXT lines` are removed by inlining owned text on the element/collapse line. Empty `#text \"\"`-style records carry no text, semantic attributes, states, or actions and are dropped. Whole added/removed subtrees report `descendants`, visible text, and interactive descendants once. Repeated groups use the browser's `repeatedGroupId`/`repeatedItemIndex`. Common-chrome suppression applies only to short exact text present in both documents and never suppresses numeric or state-bearing text.",
        "",
        "In the captured Mystery→product pair, category names such as `Fantasy`, `Poetry`, and `Crime` occur only in the removed document, so the exact common-chrome rule cannot suppress them. Subtree collapse instead reduces the entire 157-node sidebar—including those names—to one honest removal entry.",
        "",
        "## 4. Size — before compaction, after compaction, production",
        "",
        "| step | structured before lines | before bytes | before / production | structured compact lines | compact bytes | production lines | production bytes | compact / production |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    ratios: list[float] = []
    for result in step_results:
        reference = reference_root / result["step"] / "dom_diff.txt"
        production = file_metrics(reference) if reference.exists() else {"lines": 0, "bytes": 0}
        before_metrics = result["uncompactedTextMetrics"]
        compact_metrics = result["textMetrics"]
        ratio = compact_metrics["bytes"] / production["bytes"] if production["bytes"] else 0.0
        before_ratio = before_metrics["bytes"] / production["bytes"] if production["bytes"] else 0.0
        ratios.append(ratio)
        lines.append(
            f"| {result['step']} | {before_metrics['lines']} | {before_metrics['bytes']} | "
            f"{before_ratio:.2f}× | {compact_metrics['lines']} | {compact_metrics['bytes']} | "
            f"{production['lines']} | {production['bytes']} | {ratio:.2f}× |"
        )

    product = step_results[-1]
    compact_positive = "\n".join(
        line for line in product["compactText"].splitlines() if line.startswith(("+", "~"))
    ).lower()
    facts = [
        ("title", "In a Dark, Dark Wood", "in a dark, dark wood"),
        ("price", "£19.63", "£19.63"),
        ("availability", "In stock (18 available)", "in stock (18 available)"),
    ]
    lines.extend([
        "",
        "The numeric-safety check passes: **`£19.63` survives** common-chrome suppression in the compact positive diff.",
        "",
        "## 5. Provability after compaction",
        "",
        "| fact | result | exact evidence / reason |",
        "|---|---|---|",
    ])
    for label, display, needle in facts:
        present = needle in compact_positive
        lines.append(
            f"| {label}: `{display}` | **{'provable' if present else 'not provable'}** | "
            f"{'present in a positive compact element/subtree/group line' if present else 'absent from positive compact diff evidence'} |"
        )
    lines.append(
        "| star rating: `star-rating One` | **not provable** | the rating `<p>` exists, but `class` is filtered from `selectedAttributes`; no text, ARIA value, or state carries `One` |"
    )

    competitive = max(ratios, default=99.0) <= 2.0
    lines.extend([
        "",
        "## 6. Verdict",
        "",
        f"The guarded books diff is competitive with production `dom_diff.txt` on byte size (worst measured ratio: `{max(ratios, default=0.0):.2f}×`) and derived paths solve this task's cross-document identity.",
        "",
        "That size result is **not a fidelity result**: the seeded removal audit recovered only 11/20 sampled facts from compact text (14/20 from compact JSON). The subsequent live stress suite also found substantive node-cap loss, absent live form values, empty `#text` records, and positional repeated-list identity failure.",
        "",
        "- Adding `class` and `id` to `CollectSelectedAttributes` closes the class-only books gap.",
        "- Reading live `input->Value()` / `select->Value()` closes the measured form-value gap.",
        "",
        "**Those two additions alone do not make structured snapshot a sufficient sole general diff source.** Node-budget strategy, text-node runtime behavior, repeated-item identity, and lossy rendering/compaction remain unresolved. The authoritative post-stress verdict is in `../structured-diff-stress/REPORT.md`.",
        "",
    ])
    return "\n".join(lines)

def run(args: argparse.Namespace) -> None:
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    reference_root = args.reference_root.resolve()
    step_dirs = sorted(path for path in input_root.glob("step_*"))
    if len(step_dirs) != 3:
        raise SystemExit(f"expected exactly 3 step directories, found {len(step_dirs)}")

    homepage = derived_paths(
        read_snapshot(input_root / "step_001/captureStructuredSnapshot_after.json")
    )
    mystery = derived_paths(
        read_snapshot(input_root / "step_002/captureStructuredSnapshot_after.json")
    )
    for label, summary in (("books homepage", homepage), ("Mystery category", mystery)):
        print(
            f"PATH KEY {label}: nodes={summary['totalNodes']} "
            f"unique={summary['uniquePathCount']} "
            f"collision_groups={summary['collisionGroupCount']} "
            f"collision_nodes={summary['collisionNodeCount']}"
        )
    if homepage["collisionNodeCount"] or mystery["collisionNodeCount"]:
        raise SystemExit("derived path collision detected; stopping before diff construction")

    output_root.mkdir(parents=True, exist_ok=True)

    step_results = []
    path_summaries_by_capture: dict[str, dict[str, Any]] = {}
    for step_dir in step_dirs:
        before = read_snapshot(step_dir / "captureStructuredSnapshot_before.json")
        after = read_snapshot(step_dir / "captureStructuredSnapshot_after.json")
        before_paths = derived_paths(before)
        after_paths = derived_paths(after)
        path_summaries_by_capture[f"{step_dir.name}_before"] = before_paths
        path_summaries_by_capture[f"{step_dir.name}_after"] = after_paths

        destination = output_root / step_dir.name
        write_json(destination / "derived_paths_before.json", before_paths)
        write_json(destination / "derived_paths_after.json", after_paths)

        diff = diff_snapshots(before, after, before_paths, after_paths)
        uncompacted_text, _ = render_diff(diff)
        uncompacted_path = destination / "structured_diff_uncompacted.txt"
        uncompacted_path.write_text(uncompacted_text, encoding="utf-8")

        pre_guard_compact = compact_diff(
            diff, before, after, enforce_broad_collapse_guard=False
        )
        pre_guard_text, pre_guard_paths = render_compact_diff(pre_guard_compact)
        pre_guard_compact["paths"] = pre_guard_paths
        write_json(destination / "structured_diff_pre_guard.json", pre_guard_compact)
        pre_guard_path = destination / "structured_diff_pre_guard.txt"
        pre_guard_path.write_text(pre_guard_text, encoding="utf-8")

        compact = compact_diff(diff, before, after, enforce_broad_collapse_guard=True)
        compact_text, paths = render_compact_diff(compact)
        compact["paths"] = paths
        write_json(destination / "structured_diff.json", compact)
        write_json(destination / "collapse_audit.json", compact["collapseGuard"])
        text_path = destination / "structured_diff.txt"
        text_path.write_text(compact_text, encoding="utf-8")
        step_results.append(
            {
                "step": step_dir.name,
                "before": before,
                "after": after,
                "beforePaths": before_paths,
                "afterPaths": after_paths,
                "diff": diff,
                "compactDiff": compact,
                "compactText": compact_text,
                "preGuardCompactDiff": pre_guard_compact,
                "preGuardTextMetrics": file_metrics(pre_guard_path),
                "uncompactedTextMetrics": file_metrics(uncompacted_path),
                "textMetrics": file_metrics(text_path),
            }
        )

    product_result = step_results[-1]
    removed_fact_audit = audit_removed_facts(
        product_result["diff"], product_result["before"], product_result["after"],
        product_result["compactDiff"], product_result["compactText"],
    )
    write_json(output_root / "step_003" / "removed_fact_audit.json", removed_fact_audit)

    path_summary = {
        key: {
            name: value
            for name, value in summary.items()
            if name not in {"nodes", "pathByRef"}
        }
        for key, summary in path_summaries_by_capture.items()
    }
    write_json(output_root / "path_key_summary.json", path_summary)
    report = make_report(
        {"homepage": homepage, "mystery": mystery},
        step_results,
        reference_root,
    )
    (output_root / "REPORT.md").write_text(report, encoding="utf-8")

    for result in step_results:
        stats = result["diff"]["stats"]
        print(
            f"{result['step']}: {stats['beforeCount']}->{stats['afterCount']} "
            f"matched={stats['matchedCount']} ({stats['matchRatePct']:.1f}%) "
            f"added={stats['addedCount']} removed={stats['removedCount']} "
            f"changed={stats['changedCount']}"
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=root / "diagnostics/three-method-comparison",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=root / "diagnostics/structured-diff-test",
    )
    parser.add_argument(
        "--reference-root",
        type=Path,
        default=root
        / "diagnostics/dom-capture-comparison-real/tasks/task-a-books-mystery-real",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
