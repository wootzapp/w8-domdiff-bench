#!/usr/bin/env python3
"""Analyze the real three-method captures with one shared semantic differ."""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
SIMULATED = ROOT.parent / "dom-capture-comparison-simulated" / "metrics_summary.json"

METHOD_SAVE = "ChromiumRL.saveDOMState"
METHOD_OBS = "ChromiumRL.getAgentObservation"
METHOD_STRUCT = "ChromiumRL.captureStructuredSnapshot"
METHODS = (METHOD_SAVE, METHOD_OBS, METHOD_STRUCT)


def load_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compact_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def size_record(value: Any) -> dict[str, int]:
    raw = compact_bytes(value)
    return {"rawBytes": len(raw), "gzipBytes": len(gzip.compress(raw, compresslevel=6))}


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def attribute_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    result: dict[str, Any] = {}
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            for item in value:
                name = item.get("name")
                if name is not None:
                    result[str(name)] = item.get("value", "")
        else:
            for index in range(0, len(value) - 1, 2):
                result[str(value[index])] = value[index + 1]
    return result


def first_identity(node: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, str]:
    for field in fields:
        value = node.get(field)
        if value not in (None, ""):
            return field, str(value)
    return "", ""


def normalize_save(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for node in payload.get("nodes", []) or []:
        key_type, key = first_identity(
            node, ("stablePath", "cssSelector", "xpath", "fingerprint")
        )
        if not key:
            continue
        records.append(
            {
                "id": key,
                "identityField": key_type,
                "semantic": {
                    "tag": str(node.get("tagName") or "").lower(),
                    "text": normalize_text(node.get("textContent")),
                    "attributes": attribute_map(node.get("attributes")),
                },
                "raw": node,
            }
        )
    return records


def observation_semantic(item: dict[str, Any], kind: str) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    for name in (
        "role", "value", "placeholder", "type", "href", "disabled",
        "checked", "expanded", "selected", "required", "readonly",
        "invalid", "autocomplete", "options", "table",
    ):
        if item.get(name) not in (None, "", [], {}):
            attributes[name] = item.get(name)
    text_parts = [
        item.get("text"), item.get("accessibleName"), item.get("context"),
    ]
    return {
        "tag": str(item.get("tag") or "").lower(),
        "text": normalize_text(" ".join(str(part) for part in text_parts if part)),
        "attributes": attributes,
        "recordKinds": [kind],
    }


def merge_observation_record(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    current = existing["semantic"]
    added = incoming["semantic"]
    if not current.get("tag"):
        current["tag"] = added.get("tag", "")
    text = normalize_text(f"{current.get('text', '')} {added.get('text', '')}")
    current["text"] = text
    current.setdefault("attributes", {}).update(added.get("attributes", {}))
    current.setdefault("recordKinds", []).extend(added.get("recordKinds", []))
    existing.setdefault("raw", []).extend(incoming.get("raw", []))


def normalize_observation(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for kind, items in (
        ("element", payload.get("elements", []) or []),
        ("content", payload.get("content", []) or []),
    ):
        for item in items:
            key_type, key = first_identity(item, ("selector", "fingerprint"))
            if not key:
                continue
            record = {
                "id": key,
                "identityField": key_type,
                "semantic": observation_semantic(item, kind),
                "raw": [item],
            }
            if key in records:
                merge_observation_record(records[key], record)
            else:
                records[key] = record
    return list(records.values())


def normalize_structured(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for node in payload.get("nodes", []) or []:
        # Do not derive a path from parentRef. Use only IDs carried by PageNode.
        key_type, key = first_identity(node, ("nodeId", "backendNodeId", "ref"))
        if not key:
            continue
        attributes = attribute_map(node.get("selectedAttributes"))
        for state in node.get("states", []) or []:
            if state.get("name"):
                attributes[f"state:{state['name']}"] = state.get("value")
        if node.get("actionTypes"):
            attributes["actionTypes"] = node.get("actionTypes")
        for name in ("role", "accessibleName", "description", "semanticBoundary"):
            if node.get(name) not in (None, ""):
                attributes[name] = node.get(name)
        records.append(
            {
                "id": key,
                "identityField": key_type,
                "semantic": {
                    "tag": str(node.get("tag") or "").lower(),
                    "text": normalize_text(
                        f"{node.get('directText', '')} {node.get('subtreeText', '')}"
                    ),
                    "attributes": attributes,
                },
                "raw": node,
            }
        )
    return records


NORMALIZERS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
    METHOD_SAVE: normalize_save,
    METHOD_OBS: normalize_observation,
    METHOD_STRUCT: normalize_structured,
}


def record_map(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], int]:
    result: dict[str, dict[str, Any]] = {}
    collisions = 0
    for record in records:
        key = record.get("id", "")
        if not key:
            continue
        if key in result:
            collisions += 1
            continue
        result[key] = record
    return result, collisions


def semantic_diff(
    before_records: list[dict[str, Any]], after_records: list[dict[str, Any]]
) -> dict[str, Any]:
    """The one matching/change implementation used for all representations."""
    before, before_collisions = record_map(before_records)
    after, after_collisions = record_map(after_records)
    before_keys = set(before)
    after_keys = set(after)
    common = before_keys & after_keys
    changed = []
    for key in sorted(common):
        if before[key]["semantic"] != after[key]["semantic"]:
            changed.append(
                {"id": key, "before": before[key], "after": after[key]}
            )
    denominator = min(len(before_records), len(after_records))
    return {
        "beforeCount": len(before_records),
        "afterCount": len(after_records),
        "matchedCount": len(common),
        "matchRatePct": round(100.0 * len(common) / denominator, 1) if denominator else 0.0,
        "addedCount": len(after_keys - before_keys),
        "removedCount": len(before_keys - after_keys),
        "changedCount": len(changed),
        "identityCollisionsBefore": before_collisions,
        "identityCollisionsAfter": after_collisions,
        "added": [after[key] for key in sorted(after_keys - before_keys)],
        "removed": [before[key] for key in sorted(before_keys - after_keys)],
        "changed": changed,
    }


def logical_payload(method: str, method_result: dict[str, Any]) -> dict[str, Any]:
    if method == METHOD_SAVE:
        return method_result.get("state", {}) or {}
    if method == METHOD_OBS:
        return method_result.get("observation", {}) or {}
    return method_result.get("snapshot", {}) or {}


def load_capture(path: Path) -> dict[str, Any]:
    wrapper = load_gzip_json(path)
    methods = {}
    for method in METHODS:
        entry = wrapper["methods"][method]
        methods[method] = {
            "ok": bool(entry.get("ok")),
            "params": entry.get("params", {}),
            "elapsedMs": entry.get("elapsedMs"),
            "payload": logical_payload(method, entry.get("result", {}) or {}),
        }
    return {"page": wrapper.get("page", {}), "methods": methods, "path": str(path.relative_to(ROOT))}


def evidence_records(diff: dict[str, Any], *, after: bool = True) -> list[dict[str, Any]]:
    records = list(diff["added"])
    records.extend(change["after"] for change in diff["changed"])
    if not after:
        records.extend(diff["removed"])
        records.extend(change["before"] for change in diff["changed"])
    return records


def evidence_contains(diff: dict[str, Any], needle: str) -> bool:
    lowered = needle.lower()
    return any(
        lowered in json.dumps(record["semantic"], ensure_ascii=False).lower()
        for record in evidence_records(diff)
    )


def coverage(method: str, payload: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    if method == METHOD_SAVE:
        return {"nodes": len(payload.get("nodes", []) or []), "reportedDrops": {}}
    if method == METHOD_OBS:
        stats = payload.get("stats", {}) or {}
        elements = len(payload.get("elements", []) or [])
        content = len(payload.get("content", []) or [])
        cap = params.get("maxElements")
        return {
            "elements": elements,
            "contentBlocks": content,
            "totalRecords": elements + content,
            "reportedDrops": {key: value for key, value in stats.items() if key.startswith("dropped")},
            "stats": stats,
            "cap": cap,
            "capFired": bool(cap and elements >= int(cap)),
        }
    stats = payload.get("stats", {}) or {}
    returned = len(payload.get("nodes", []) or [])
    raw = int(stats.get("rawNodes", 0) or 0)
    reported_drop_total = sum(
        int(stats.get(key, 0) or 0)
        for key in ("droppedHidden", "droppedOffscreen", "droppedDuplicate", "droppedForTextBudget")
    )
    return {
        "nodes": returned,
        "stats": stats,
        "nodeCap": 700,
        "textBudget": 24000,
        "nodeCapFired": returned >= 700,
        "textBudgetFired": bool(stats.get("droppedForTextBudget", 0)) or (
            bool(stats.get("truncated")) and int(stats.get("textChars", 0) or 0) >= 24000
        ),
        "unclassifiedRawMinusReturnedAndReportedDrops": max(0, raw - returned - reported_drop_total),
    }


def attrs_have(node: dict[str, Any], name: str, contains: str | None = None) -> bool:
    attrs = attribute_map(node.get("attributes"))
    if name not in attrs:
        return False
    return contains is None or contains in str(attrs[name])


def selected_have(node: dict[str, Any], name: str, value: str | None = None) -> bool:
    attrs = attribute_map(node.get("selectedAttributes"))
    if name not in attrs:
        return False
    return value is None or str(attrs[name]) == value


def find_star_records(product_capture: dict[str, Any]) -> dict[str, Any]:
    save_nodes = product_capture["methods"][METHOD_SAVE]["payload"].get("nodes", []) or []
    primary = next(
        (
            node for node in save_nodes
            if attrs_have(node, "class", "star-rating One")
            and "article.product_page > div.row" in str(node.get("stablePath", ""))
        ),
        None,
    )
    node_id = primary.get("nodeId") if primary else None
    observation = product_capture["methods"][METHOD_OBS]["payload"]
    obs_records = list(observation.get("elements", []) or []) + list(observation.get("content", []) or [])
    observed = next((item for item in obs_records if item.get("nodeId") == node_id), None)
    structured_nodes = product_capture["methods"][METHOD_STRUCT]["payload"].get("nodes", []) or []
    structured = next((node for node in structured_nodes if node.get("nodeId") == node_id), None)
    return {"nodeId": node_id, "saveDOMState": primary, "getAgentObservation": observed, "captureStructuredSnapshot": structured}


def find_form_records(capture: dict[str, Any], field: str) -> dict[str, Any]:
    save_nodes = capture["methods"][METHOD_SAVE]["payload"].get("nodes", []) or []
    save = next((node for node in save_nodes if attrs_have(node, "name", field)), None)
    observation = capture["methods"][METHOD_OBS]["payload"]
    obs_items = observation.get("elements", []) or []
    observed = next(
        (
            item for item in obs_items
            if field in str(item.get("selector", "")) or item.get("nodeId") == (save or {}).get("nodeId")
        ),
        None,
    )
    structured_nodes = capture["methods"][METHOD_STRUCT]["payload"].get("nodes", []) or []
    structured = next(
        (
            node for node in structured_nodes
            if selected_have(node, "name", field) or node.get("nodeId") == (save or {}).get("nodeId")
        ),
        None,
    )
    return {"saveDOMState": save, "getAgentObservation": observed, "captureStructuredSnapshot": structured}


def structured_features(snapshot: dict[str, Any]) -> dict[str, Any]:
    nodes = snapshot.get("nodes", []) or []
    roles = Counter(str(node.get("role")) for node in nodes if node.get("role"))
    boundaries = Counter(str(node.get("semanticBoundary")) for node in nodes if node.get("semanticBoundary"))
    actions = Counter(action for node in nodes for action in (node.get("actionTypes", []) or []))
    states = Counter(
        str(state.get("name")) for node in nodes for state in (node.get("states", []) or []) if state.get("name")
    )
    repeated_ids = {str(node.get("repeatedGroupId")) for node in nodes if node.get("repeatedGroupId")}
    table_nodes = [node for node in nodes if node.get("tag") == "table"]
    return {
        "nodes": len(nodes),
        "nodesWithParentRef": sum(1 for node in nodes if node.get("parentRef")),
        "childRefEdges": sum(len(node.get("childRefs", []) or []) for node in nodes),
        "nodesWithRole": sum(1 for node in nodes if node.get("role")),
        "roleCounts": dict(roles),
        "nodesWithSemanticBoundary": sum(1 for node in nodes if node.get("semanticBoundary")),
        "semanticBoundaryCounts": dict(boundaries),
        "nodesWithActions": sum(1 for node in nodes if node.get("actionTypes")),
        "actionTypeTotal": sum(actions.values()),
        "actionTypeCounts": dict(actions),
        "nodesWithStates": sum(1 for node in nodes if node.get("states")),
        "stateTotal": sum(states.values()),
        "stateCounts": dict(states),
        "tableNodes": len(table_nodes),
        "tableNodesWithText": sum(1 for node in table_nodes if node.get("directText") or node.get("subtreeText")),
        "structuredTableInfoObjects": sum(1 for node in nodes if node.get("table") is not None),
        "scrollableNodes": sum(1 for node in nodes if node.get("scrollable") is True),
        "repeatedGroupNodes": sum(1 for node in nodes if node.get("repeatedGroupId")),
        "repeatedGroups": len(repeated_ids),
    }


def build_verification() -> dict[str, Any]:
    verification = json.loads((ROOT / "build-verification.json").read_text(encoding="utf-8"))
    snapshot = verification.get("result", {}).get("snapshot", {})
    nodes = snapshot.get("nodes", []) or []
    required = ("ref", "nodeId", "backendNodeId", "selectedAttributes", "states", "actionTypes")
    return {
        "commandResponded": bool(snapshot),
        "nodeCount": len(nodes),
        "pageNodeWithRequiredFields": any(all(field in node for field in required) for node in nodes),
        "nodesWithDifferentBackendId": sum(1 for node in nodes if node.get("nodeId") != node.get("backendNodeId")),
        "stats": snapshot.get("stats", {}),
        "hasDroppedForTextBudget": "droppedForTextBudget" in (snapshot.get("stats", {}) or {}),
        "hasTraversedNodeCount": "traversedNodeCount" in snapshot,
        "nodesWithOccludedField": sum(1 for node in nodes if "occluded" in node),
    }


def main() -> None:
    captures: dict[str, dict[str, Any]] = {}
    metrics: dict[str, Any] = {
        "buildVerification": build_verification(),
        "configuration": {
            "model": "gpt-5.1",
            "getAgentObservationParams": {"includeContent": True, "maxElements": 250, "maxInteractiveElements": 250},
            "captureStructuredSnapshotParams": {},
            "structuredDefaults": {"maxNodes": 700, "maxTextChars": 24000},
        },
        "tasks": {},
    }

    for task_dir in sorted(TASKS.glob("*-real")):
        task_key = task_dir.name.replace("-real", "")
        task_metrics: dict[str, Any] = {}
        for step_dir in sorted(task_dir.glob("step_*")):
            before = load_capture(step_dir / "capture_before.json.gz")
            after = load_capture(step_dir / "capture_after.json.gz")
            capture_key = f"{task_key}/{step_dir.name}"
            captures[capture_key] = {"before": before, "after": after}
            cross_document = before["page"].get("url") != after["page"].get("url")
            step_metrics: dict[str, Any] = {
                "crossDocument": cross_document,
                "beforeUrl": before["page"].get("url", ""),
                "afterUrl": after["page"].get("url", ""),
                "methods": {},
            }
            for method in METHODS:
                before_method = before["methods"][method]
                after_method = after["methods"][method]
                before_records = NORMALIZERS[method](before_method["payload"])
                after_records = NORMALIZERS[method](after_method["payload"])
                diff = semantic_diff(before_records, after_records)
                step_metrics["methods"][method] = {
                    "matchability": {key: value for key, value in diff.items() if key.endswith("Count") or key.endswith("Pct") or key.startswith("identityCollisions")},
                    "coverageBefore": coverage(method, before_method["payload"], before_method["params"]),
                    "coverageAfter": coverage(method, after_method["payload"], after_method["params"]),
                    "sizeBefore": size_record(before_method["payload"]),
                    "sizeAfter": size_record(after_method["payload"]),
                    "elapsedMsBefore": before_method["elapsedMs"],
                    "elapsedMsAfter": after_method["elapsedMs"],
                    "_diff": diff,
                }
            task_metrics[step_dir.name] = step_metrics
        metrics["tasks"][task_key] = task_metrics

    facts: dict[str, Any] = {}
    task_a = metrics["tasks"]["task-a-books-mystery"]["step_003"]
    for fact, needle in (
        ("bookTitle", "In a Dark, Dark Wood"),
        ("price", "£19.63"),
        ("availability", "In stock (18 available)"),
        ("starRating", "star-rating One"),
    ):
        facts[fact] = {
            method: evidence_contains(task_a["methods"][method]["_diff"], needle)
            for method in METHODS
        }
    task_b = metrics["tasks"]["task-b-quotes-login"]
    facts["usernameAfterFill"] = {
        method: evidence_contains(task_b["step_002"]["methods"][method]["_diff"], "wrong")
        for method in METHODS
    }
    facts["passwordAfterFill"] = {
        method: evidence_contains(task_b["step_003"]["methods"][method]["_diff"], "wrong")
        for method in METHODS
    }
    facts["postSubmitText"] = {
        method: evidence_contains(task_b["step_004"]["methods"][method]["_diff"], "Logout")
        for method in METHODS
    }
    metrics["facts"] = facts

    product = captures["task-a-books-mystery/step_003"]["after"]
    star_records = find_star_records(product)
    write_json(ROOT / "star_rating_records.json", star_records)

    form_records = {
        "usernameBefore": find_form_records(captures["task-b-quotes-login/step_002"]["before"], "username"),
        "usernameAfter": find_form_records(captures["task-b-quotes-login/step_002"]["after"], "username"),
        "passwordBefore": find_form_records(captures["task-b-quotes-login/step_003"]["before"], "password"),
        "passwordAfter": find_form_records(captures["task-b-quotes-login/step_003"]["after"], "password"),
    }
    write_json(ROOT / "form_value_records.json", form_records)

    page_features: dict[str, Any] = {}
    for capture_key, phases in captures.items():
        after = phases["after"]
        url = str(after["page"].get("url") or "")
        if url and url != "about:blank" and url not in page_features:
            snapshot = after["methods"][METHOD_STRUCT]["payload"]
            page_features[url] = structured_features(snapshot)
    metrics["structuredFeatureCounts"] = page_features
    write_json(ROOT / "feature_counts.json", page_features)

    if SIMULATED.exists():
        simulated = json.loads(SIMULATED.read_text(encoding="utf-8"))
        metrics["simulatedSourcePresent"] = True
        metrics["simulatedTaskKeys"] = sorted((simulated.get("tasks") or {}).keys())

    # Keep details in a separate audit file and publish compact metrics without raw nodes.
    details: dict[str, Any] = {}
    for task, task_data in metrics["tasks"].items():
        details[task] = {}
        for step, step_data in task_data.items():
            details[task][step] = {
                method: step_data["methods"][method].pop("_diff")
                for method in METHODS
            }
    write_json(ROOT / "match_details.json", details)
    write_json(ROOT / "metrics_summary.json", metrics)


if __name__ == "__main__":
    main()
