"""Detailed, offline evidence-item audit over existing verifier outputs.

The module imports only the experiment's offline extraction helpers. It never
imports a verifier package, constructs a client, or calls a model.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from .evidence_error_audit import (
    CLASSIFICATIONS,
    classify,
    extract_run,
    load_json,
)


ITEM_SCHEMA_VERSION = "existing-output-evidence-item-audit/v1"
ADVANTAGE_BY_CLASSIFICATION = {
    "BOTH_CAUGHT": "TIE",
    "SCREENSHOT_MISSED_DOM_CAUGHT": "DOM",
    "DOM_MISSED_SCREENSHOT_CAUGHT": "SCREENSHOT",
    "BOTH_MISSED": "NEITHER",
    "SCREENSHOT_EVIDENCE_MISSING": "NOT_COMPARABLE",
    "DOM_EVIDENCE_MISSING": "NOT_COMPARABLE",
}
LINE_RANGE_RE = re.compile(r"^(?:m(?P<state>\d+):)?L(?P<start>\d+)-L(?P<end>\d+)$")
CANONICAL_SOURCE_RE = {
    "screenshot": re.compile(r"^screenshot(0|[1-9]\d*)\.png$"),
    "dom_model": re.compile(r"^dom_model(0|[1-9]\d*)\.txt$"),
}


def _rubric_descriptions(run_dir: Path, criterion_count: int) -> list[str]:
    source = run_dir / "_inputs" / "frozen_rubric.json"
    if not source.is_file():
        return [""] * criterion_count
    payload = load_json(source)
    rubric = payload.get("precomputed_rubric", payload) if isinstance(payload, dict) else {}
    items = rubric.get("items") if isinstance(rubric, dict) else None
    if not isinstance(items, list) or len(items) != criterion_count:
        raise ValueError("Frozen rubric does not match extracted criterion count")
    return [str(item.get("description") or "") for item in items]


def build_item_review_template(run_dir: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    audit = extract_run(run_dir)
    descriptions = _rubric_descriptions(Path(audit["run_dir"]), len(audit["criteria"]))
    review_criteria: list[dict[str, Any]] = []
    for row, description in zip(audit["criteria"], descriptions):
        review_criteria.append(
            {
                "criterion_index": row["criterion_index"],
                "criterion": row["criterion"],
                "description": description,
                "max_points": row["max_points"],
                "screenshot_context": {
                    "selected_indices": row["screenshot"]["selected_indices"],
                    "final_points": row["screenshot"]["final_points"],
                    "verifier_evidence": row["screenshot"]["verifier_evidence"],
                    "verifier_justification": row["screenshot"]["verifier_justification"],
                    "evidence_analyses": row["screenshot"]["evidence_analyses"],
                },
                "dom_model_context": {
                    "selected_indices": row["dom_model"]["selected_indices"],
                    "final_points": row["dom_model"]["final_points"],
                    "verifier_evidence": row["dom_model"]["verifier_evidence"],
                    "verifier_justification": row["dom_model"]["verifier_justification"],
                    "evidence_analyses": row["dom_model"]["evidence_analyses"],
                },
                "evidence_items": [],
            }
        )
    review = {
        "schema_version": ITEM_SCHEMA_VERSION,
        "task_id": audit["task_id"],
        "run_id": audit["run_id"],
        "rubric_sha256": audit["rubric_sha256"],
        "instructions": (
            "Add one confirmed row per concrete evidence item. Cite canonical source files, "
            "copy verifier excerpts verbatim, and judge source presence separately from recovery."
        ),
        "criteria": review_criteria,
    }
    return audit, review


def _walk_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _source_map(audit: dict[str, Any], modality: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in (audit.get("source_inventory") or {}).get(modality, []):
        name = Path(str(item["file"])).name
        if not CANONICAL_SOURCE_RE[modality].fullmatch(name):
            raise ValueError(f"Non-canonical {modality} source in inventory: {name}")
        if name in result:
            raise ValueError(f"Duplicate {modality} source index/name: {name}")
        result[name] = item
    return result


def _criterion_by_index(audit: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(row["criterion_index"]): row for row in audit.get("criteria", [])}


def _validate_excerpt(context: dict[str, Any], excerpt: object, label: str) -> str:
    value = str(excerpt or "").strip()
    if not value:
        raise ValueError(f"{label} verifier_evidence_excerpt must be nonempty")
    if not any(value in candidate for candidate in _walk_strings(context)):
        raise ValueError(f"{label} verifier excerpt is not verbatim in existing output")
    return value


def _validate_screenshot_citations(
    citations: object, source_present: bool, inventory: dict[str, dict[str, Any]]
) -> list[dict[str, str]]:
    if not isinstance(citations, list):
        raise ValueError("screenshot source_citations must be a list")
    if source_present and not citations:
        raise ValueError("Present screenshot evidence requires a source citation")
    if not source_present and citations:
        raise ValueError("Missing screenshot evidence cannot have a positive citation")
    validated: list[dict[str, str]] = []
    for citation in citations:
        if not isinstance(citation, dict):
            raise ValueError("Screenshot citation must be an object")
        name = Path(str(citation.get("file") or "")).name
        if name not in inventory:
            raise ValueError(f"Screenshot citation is not a canonical source file: {name}")
        visible_text = str(citation.get("visible_text") or "").strip()
        locator = str(citation.get("locator") or "").strip()
        if not visible_text or not locator:
            raise ValueError("Screenshot citation requires visible_text and locator")
        validated.append({"file": name, "visible_text": visible_text, "locator": locator})
    return validated


def _validate_dom_citations(
    citations: object,
    source_present: bool,
    inventory: dict[str, dict[str, Any]],
    run_dir: Path,
) -> list[dict[str, str]]:
    if not isinstance(citations, list):
        raise ValueError("DOM source_citations must be a list")
    if source_present and not citations:
        raise ValueError("Present DOM evidence requires a source citation")
    if not source_present and citations:
        raise ValueError("Missing DOM evidence cannot have a positive citation")
    validated: list[dict[str, str]] = []
    for citation in citations:
        if not isinstance(citation, dict):
            raise ValueError("DOM citation must be an object")
        name = Path(str(citation.get("file") or "")).name
        if name not in inventory:
            raise ValueError(f"DOM citation is not a canonical source file: {name}")
        match = LINE_RANGE_RE.fullmatch(str(citation.get("line_range") or ""))
        if match is None:
            raise ValueError("DOM line_range must be Lx-Ly or mN:Lx-Ly")
        state_index = int(CANONICAL_SOURCE_RE["dom_model"].fullmatch(name).group(1))
        if match.group("state") is not None and int(match.group("state")) != state_index:
            raise ValueError("DOM provenance state index differs from source filename")
        start, end = int(match.group("start")), int(match.group("end"))
        source_path = run_dir / inventory[name]["file"]
        lines = source_path.read_text(encoding="utf-8").splitlines()
        if start < 1 or end < start or end > len(lines):
            raise ValueError(f"DOM line range outside {name}: L{start}-L{end}")
        quoted = str(citation.get("quoted_text") or "").strip()
        cited_text = "\n".join(lines[start - 1 : end])
        if not quoted or quoted not in cited_text:
            raise ValueError(f"DOM quote does not occur in cited lines of {name}")
        validated.append(
            {"file": name, "line_range": f"m{state_index}:L{start}-L{end}", "quoted_text": quoted}
        )
    return validated


def _validate_modality(
    *,
    modality: str,
    decision: object,
    context: dict[str, Any],
    inventory: dict[str, dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    if not isinstance(decision, dict):
        raise ValueError(f"{modality} decision must be an object")
    source_present = decision.get("source_present")
    verifier_caught = decision.get("verifier_caught")
    if not isinstance(source_present, bool) or not isinstance(verifier_caught, bool):
        raise ValueError(f"{modality} source_present and verifier_caught must be booleans")
    if not source_present and verifier_caught:
        raise ValueError(f"{modality} evidence cannot be caught when source evidence is missing")
    if modality == "screenshot":
        citations = _validate_screenshot_citations(
            decision.get("source_citations", []), source_present, inventory
        )
    else:
        citations = _validate_dom_citations(
            decision.get("source_citations", []), source_present, inventory, run_dir
        )
    return {
        "source_present": source_present,
        "source_citations": citations,
        "verifier_caught": verifier_caught,
        "verifier_evidence_excerpt": _validate_excerpt(
            context, decision.get("verifier_evidence_excerpt"), modality
        ),
        "review_note": str(decision.get("review_note") or ""),
    }


def finalize_item_review(audit: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    for key in ("task_id", "run_id", "rubric_sha256"):
        if audit.get(key) != review.get(key):
            raise ValueError(f"Evidence-item review {key} differs from extracted audit")
    if review.get("schema_version") != ITEM_SCHEMA_VERSION:
        raise ValueError("Unsupported evidence-item review schema")
    run_dir = Path(audit["run_dir"]).resolve(strict=True)
    source_maps = {mode: _source_map(audit, mode) for mode in ("screenshot", "dom_model")}
    extracted = _criterion_by_index(audit)
    review_rows = review.get("criteria")
    if not isinstance(review_rows, list):
        raise ValueError("Evidence-item review criteria must be a list")
    seen_criteria: set[int] = set()
    seen_items: set[str] = set()
    final_criteria: list[dict[str, Any]] = []
    for review_row in review_rows:
        index = int(review_row.get("criterion_index"))
        if index in seen_criteria or index not in extracted:
            raise ValueError(f"Duplicate or unknown criterion index: {index}")
        seen_criteria.add(index)
        context = extracted[index]
        final_items: list[dict[str, Any]] = []
        evidence_items = review_row.get("evidence_items")
        if not isinstance(evidence_items, list):
            raise ValueError(f"Criterion {index} evidence_items must be a list")
        for item in evidence_items:
            evidence_id = str(item.get("evidence_id") or "").strip()
            if not evidence_id or evidence_id in seen_items:
                raise ValueError(f"Missing or duplicate evidence_id: {evidence_id!r}")
            seen_items.add(evidence_id)
            requirement = str(item.get("evidence_requirement") or "").strip()
            expected = str(item.get("expected_value") or "").strip()
            if not requirement or not expected:
                raise ValueError(f"{evidence_id} requires evidence_requirement and expected_value")
            if item.get("review_status") != "confirmed":
                final_items.append(
                    {
                        "evidence_id": evidence_id,
                        "evidence_requirement": requirement,
                        "expected_value": expected,
                        "review_status": "pending",
                        "classification": None,
                        "advantage": None,
                    }
                )
                continue
            screenshot = _validate_modality(
                modality="screenshot",
                decision=item.get("screenshot"),
                context=context["screenshot"],
                inventory=source_maps["screenshot"],
                run_dir=run_dir,
            )
            dom = _validate_modality(
                modality="dom_model",
                decision=item.get("dom_model"),
                context=context["dom_model"],
                inventory=source_maps["dom_model"],
                run_dir=run_dir,
            )
            classification = classify(
                screenshot_available=screenshot["source_present"],
                screenshot_caught=screenshot["verifier_caught"],
                dom_available=dom["source_present"],
                dom_caught=dom["verifier_caught"],
            )
            final_items.append(
                {
                    "evidence_id": evidence_id,
                    "evidence_requirement": requirement,
                    "expected_value": expected,
                    "review_status": "confirmed",
                    "screenshot": screenshot,
                    "dom_model": dom,
                    "classification": classification,
                    "advantage": ADVANTAGE_BY_CLASSIFICATION[classification],
                }
            )
        final_criteria.append(
            {
                "criterion_index": index,
                "criterion": context["criterion"],
                "max_points": context["max_points"],
                "screenshot_final_points": context["screenshot"]["final_points"],
                "dom_model_final_points": context["dom_model"]["final_points"],
                "evidence_items": final_items,
            }
        )
    if seen_criteria != set(extracted):
        raise ValueError("Evidence-item review must contain every rubric criterion exactly once")
    return {
        "schema_version": ITEM_SCHEMA_VERSION,
        "task_id": audit["task_id"],
        "run_id": audit["run_id"],
        "rubric_sha256": audit["rubric_sha256"],
        "criteria": final_criteria,
    }


def _all_items(item_audit: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for row in item_audit.get("criteria", []) for item in row.get("evidence_items", [])]


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": None if denominator == 0 else numerator / denominator,
        "percentage": None if denominator == 0 else round(100 * numerator / denominator, 2),
    }


def calculate_item_metrics(item_audit: dict[str, Any]) -> dict[str, Any]:
    items = _all_items(item_audit)
    confirmed = [item for item in items if item.get("classification") in CLASSIFICATIONS]
    counts = Counter(item["classification"] for item in confirmed)
    common = [
        item
        for item in confirmed
        if item["screenshot"]["source_present"] and item["dom_model"]["source_present"]
    ]
    screenshot_caught = sum(item["screenshot"]["verifier_caught"] for item in common)
    dom_caught = sum(item["dom_model"]["verifier_caught"] for item in common)
    screenshot_missed_dom = counts["SCREENSHOT_MISSED_DOM_CAUGHT"]
    dom_missed_screenshot = counts["DOM_MISSED_SCREENSHOT_CAUGHT"]
    both_missed = counts["BOTH_MISSED"]
    return {
        "schema_version": ITEM_SCHEMA_VERSION,
        "task_id": item_audit.get("task_id"),
        "run_id": item_audit.get("run_id"),
        "rubric_sha256": item_audit.get("rubric_sha256"),
        "evidence_item_count": len(items),
        "confirmed_count": len(confirmed),
        "pending_count": len(items) - len(confirmed),
        "present_in_both_count": len(common),
        "classification_counts": {name: counts[name] for name in CLASSIFICATIONS},
        "advantage_counts": {
            "DOM": screenshot_missed_dom,
            "SCREENSHOT": dom_missed_screenshot,
            "TIE": counts["BOTH_CAUGHT"],
            "NEITHER": both_missed,
            "NOT_COMPARABLE": counts["SCREENSHOT_EVIDENCE_MISSING"]
            + counts["DOM_EVIDENCE_MISSING"],
        },
        "dom_recovery_of_confirmed_screenshot_misses": _rate(
            screenshot_missed_dom, screenshot_missed_dom + both_missed
        ),
        "screenshot_recovery_of_confirmed_dom_misses": _rate(
            dom_missed_screenshot, dom_missed_screenshot + both_missed
        ),
        "screenshot_common_evidence_catch_rate": _rate(screenshot_caught, len(common)),
        "dom_common_evidence_catch_rate": _rate(dom_caught, len(common)),
    }


def _citation_summary(modality: dict[str, Any]) -> str:
    if not modality.get("source_present"):
        return "Absent"
    parts = []
    for citation in modality.get("source_citations", []):
        if "line_range" in citation:
            parts.append(f"{citation['file']} {citation['line_range']}")
        else:
            parts.append(f"{citation['file']}: {citation['visible_text']}")
    caught = "caught" if modality.get("verifier_caught") else "missed"
    return f"Present ({'; '.join(parts)}); verifier {caught}"


def render_item_markdown(item_audit: dict[str, Any], metrics: dict[str, Any]) -> str:
    lines = [
        f"# Evidence-Item Audit: {item_audit.get('task_id')}",
        "",
        "| Criterion | Evidence item | Expected value | Screenshot source/verifier | DOM source/verifier | Result | Advantage |",
        "|---|---|---|---|---|---|---|",
    ]
    for criterion in item_audit.get("criteria", []):
        for item in criterion.get("evidence_items", []):
            lines.append(
                "| C{index} | {requirement} | {expected} | {screenshot} | {dom} | `{classification}` | {advantage} |".format(
                    index=criterion["criterion_index"],
                    requirement=str(item["evidence_requirement"]).replace("|", "\\|"),
                    expected=str(item["expected_value"]).replace("|", "\\|"),
                    screenshot=(
                        _citation_summary(item["screenshot"]).replace("|", "\\|")
                        if item.get("classification")
                        else "Pending"
                    ),
                    dom=(
                        _citation_summary(item["dom_model"]).replace("|", "\\|")
                        if item.get("classification")
                        else "Pending"
                    ),
                    classification=item.get("classification") or "PENDING",
                    advantage=item.get("advantage") or "PENDING",
                )
            )
    dom_recovery = metrics["dom_recovery_of_confirmed_screenshot_misses"]
    screenshot_recovery = metrics["screenshot_recovery_of_confirmed_dom_misses"]
    screen_catch = metrics["screenshot_common_evidence_catch_rate"]
    dom_catch = metrics["dom_common_evidence_catch_rate"]
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"- Evidence items present in both: {metrics['present_in_both_count']}.",
            f"- Screenshot catch rate on common evidence: {screen_catch['numerator']}/{screen_catch['denominator']} ({screen_catch['percentage'] if screen_catch['percentage'] is not None else 'N/A'}%).",
            f"- DOM catch rate on common evidence: {dom_catch['numerator']}/{dom_catch['denominator']} ({dom_catch['percentage'] if dom_catch['percentage'] is not None else 'N/A'}%).",
            f"- DOM recovery of screenshot misses: {dom_recovery['numerator']}/{dom_recovery['denominator']} ({dom_recovery['percentage'] if dom_recovery['percentage'] is not None else 'N/A'}%).",
            f"- Screenshot recovery of DOM misses: {screenshot_recovery['numerator']}/{screenshot_recovery['denominator']} ({screenshot_recovery['percentage'] if screenshot_recovery['percentage'] is not None else 'N/A'}%).",
            "",
        ]
    )
    return "\n".join(lines)
