"""Offline audit of evidence already emitted by both verifier modes.

This module never imports either verifier package and never calls an LLM.  It
reads completed result artifacts, preserves their evidence text verbatim, and
joins manual review decisions to the six experiment classifications.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "existing-output-evidence-audit/v1"
CLASSIFICATIONS = (
    "BOTH_CAUGHT",
    "SCREENSHOT_MISSED_DOM_CAUGHT",
    "DOM_MISSED_SCREENSHOT_CAUGHT",
    "BOTH_MISSED",
    "SCREENSHOT_EVIDENCE_MISSING",
    "DOM_EVIDENCE_MISSING",
)
MODALITIES = ("screenshot", "dom_model")
_INDEX_RE = re.compile(r"(\d+)(?=\.[^.]+$)")
_SOURCE_FILE_RE = {
    "screenshot": re.compile(r"^screenshot(0|[1-9]\d*)\.png$"),
    "dom_model": re.compile(r"^dom_model(0|[1-9]\d*)\.txt$"),
}
_EXPLICIT_STATUS_RE = re.compile(
    r"\bEVIDENCE_STATUS\s*:\s*(SUPPORTED|PARTIAL|CONTRADICTED|UNKNOWN|MISSING|UNSUPPORTED)\b",
    re.IGNORECASE,
)
_MISSING_LANGUAGE_RE = re.compile(
    r"\b(no (?:visible |relevant |supporting )?evidence|"
    r"not (?:visible|legible|readable|supported)|"
    r"cannot be (?:validated|verified|confirmed)|"
    r"does not show|unsupported|unreadable|unknown)\b",
    re.IGNORECASE,
)


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, value: object) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _index(path: Path) -> int:
    match = _INDEX_RE.search(path.name)
    if match is None:
        raise ValueError(f"Evidence filename has no numeric index: {path}")
    return int(match.group(1))


def _source_inventory(run_dir: Path, modality: str) -> list[dict[str, Any]]:
    source_dir = run_dir / "_inputs" / modality
    pattern = "screenshot*.png" if modality == "screenshot" else "dom_model*.txt"
    files = sorted(
        (
            path
            for path in source_dir.glob(pattern)
            if not path.is_symlink() and _SOURCE_FILE_RE[modality].fullmatch(path.name)
        ),
        key=_index,
    )
    return [
        {
            "index": _index(path),
            "file": path.relative_to(run_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in files
    ]


def _criterion_value(container: object, index: int, default: object) -> object:
    if isinstance(container, dict):
        return container.get(str(index), container.get(index, default))
    if isinstance(container, list) and index < len(container):
        return container[index]
    return default


def _analysis_rows(intermediate: dict[str, Any], index: int) -> list[dict[str, Any]]:
    raw = _criterion_value(intermediate.get("step4_evidence_by_criterion"), index, [])
    if not isinstance(raw, list):
        return []
    allowed = (
        "screenshot_idx",
        "dom_model_state_idx",
        "screenshot_evidence",
        "dom_model_evidence",
        "criterion_analysis",
        "discrepancies",
        "environment_issues_confirmed",
        "condition_verification",
    )
    return [{key: row.get(key) for key in allowed if key in row} for row in raw if isinstance(row, dict)]


def _selected_indices(intermediate: dict[str, Any], index: int) -> list[int]:
    grouped = intermediate.get("step3_grouped_dom_states")
    if grouped is None:
        grouped = intermediate.get("step3_grouped_screenshots")
    raw = _criterion_value(grouped, index, [])
    if not isinstance(raw, list):
        return []
    return [int(value) for value in raw if isinstance(value, (int, float, str)) and str(value).isdigit()]


def _relevance_rows(intermediate: dict[str, Any], index: int) -> list[dict[str, Any]]:
    raw = intermediate.get("step2_relevance_scores") or {}
    if not isinstance(raw, dict):
        return []
    rows: list[dict[str, Any]] = []
    for key, scores in raw.items():
        if not isinstance(scores, dict):
            continue
        source_index = scores.get("dom_model_state_idx", scores.get("screenshot_idx"))
        if source_index is None:
            match = re.search(r"(\d+)$", str(key))
            source_index = int(match.group(1)) if match else None
        score = scores.get(str(index), scores.get(index))
        if source_index is not None and score is not None:
            rows.append({"source_index": int(source_index), "score": score})
    return sorted(rows, key=lambda row: row["source_index"])


def _status_signals(analyses: list[dict[str, Any]], scoring: dict[str, Any]) -> dict[str, Any]:
    fields: list[str] = []
    for analysis in analyses:
        fields.extend(
            str(analysis.get(key) or "")
            for key in ("screenshot_evidence", "dom_model_evidence", "criterion_analysis", "discrepancies")
        )
    fields.extend(
        str(scoring.get(key) or "")
        for key in ("applicable_evidence", "post_image_justification", "reality_notes")
    )
    text = "\n".join(fields)
    return {
        "explicit_statuses": sorted({match.upper() for match in _EXPLICIT_STATUS_RE.findall(text)}),
        "contains_missing_or_unknown_language": bool(_MISSING_LANGUAGE_RE.search(text)),
    }


def _extract_mode(result: dict[str, Any], mode: str, criterion_index: int) -> dict[str, Any]:
    intermediate = result.get("intermediate_mm_rubric_steps") or {}
    scoring_rows = intermediate.get("step6_rescoring_summary") or []
    scoring = scoring_rows[criterion_index]
    analyses = _analysis_rows(intermediate, criterion_index)
    extracted_scoring = {
        key: scoring.get(key)
        for key in (
            "criterion",
            "earned_points",
            "post_image_earned_points",
            "max_points",
            "justification",
            "applicable_evidence",
            "post_image_justification",
            "reality_notes",
            "penalty",
        )
        if key in scoring
    }
    return {
        "mode": mode,
        "relevance_scores": _relevance_rows(intermediate, criterion_index),
        "selected_indices": _selected_indices(intermediate, criterion_index),
        "evidence_analyses": analyses,
        "scoring": extracted_scoring,
        "verifier_evidence": scoring.get("applicable_evidence", ""),
        "verifier_justification": scoring.get(
            "post_image_justification", scoring.get("justification", "")
        ),
        "action_only_points": scoring.get("earned_points"),
        "final_points": scoring.get("post_image_earned_points", scoring.get("earned_points")),
        "max_points": scoring.get("max_points"),
        "evidence_signals": _status_signals(analyses, scoring),
        "manual_review": {
            "evidence_available": None,
            "caught_correctly": None,
            "review_note": "",
        },
    }


def _validate_pair(screenshot: dict[str, Any], dom: dict[str, Any]) -> tuple[str, str, int]:
    task_id = str(screenshot.get("task_id") or "")
    rubric_hash = str(screenshot.get("rubric_sha256") or "")
    if not task_id or task_id != str(dom.get("task_id") or ""):
        raise ValueError("Screenshot and DOM results have different or missing task_id")
    if not rubric_hash or rubric_hash != str(dom.get("rubric_sha256") or ""):
        raise ValueError("Screenshot and DOM results have different or missing rubric_sha256")
    screenshot_rows = (screenshot.get("intermediate_mm_rubric_steps") or {}).get(
        "step6_rescoring_summary"
    ) or []
    dom_rows = (dom.get("intermediate_mm_rubric_steps") or {}).get(
        "step6_rescoring_summary"
    ) or []
    if not screenshot_rows or len(screenshot_rows) != len(dom_rows):
        raise ValueError("Screenshot and DOM results have different or empty criterion rows")
    for index, (screen_row, dom_row) in enumerate(zip(screenshot_rows, dom_rows)):
        if screen_row.get("criterion") != dom_row.get("criterion"):
            raise ValueError(f"Criterion mismatch at index {index}")
        if float(screen_row.get("max_points", 0)) != float(dom_row.get("max_points", 0)):
            raise ValueError(f"Criterion maximum mismatch at index {index}")
    return task_id, rubric_hash, len(screenshot_rows)


def _different(left: object, right: object) -> bool:
    try:
        return float(left) != float(right)
    except (TypeError, ValueError):
        return left != right


def disagreement_reasons(screenshot: dict[str, Any], dom: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _different(screenshot.get("final_points"), dom.get("final_points")):
        reasons.append("final_criterion_score_mismatch")
    if not screenshot.get("evidence_analyses"):
        reasons.append("screenshot_evidence_analysis_missing")
    if not dom.get("evidence_analyses"):
        reasons.append("dom_evidence_analysis_missing")
    screen_environment = any(
        row.get("environment_issues_confirmed") is True
        for row in screenshot.get("evidence_analyses", [])
    )
    dom_environment = any(
        row.get("environment_issues_confirmed") is True
        for row in dom.get("evidence_analyses", [])
    )
    if screen_environment != dom_environment:
        reasons.append("environment_issue_conclusion_mismatch")
    screen_signals = screenshot.get("evidence_signals") or {}
    dom_signals = dom.get("evidence_signals") or {}
    if screen_signals.get("explicit_statuses") and dom_signals.get("explicit_statuses"):
        if screen_signals["explicit_statuses"] != dom_signals["explicit_statuses"]:
            reasons.append("explicit_evidence_status_mismatch")
    if screen_signals.get("contains_missing_or_unknown_language") != dom_signals.get(
        "contains_missing_or_unknown_language"
    ):
        reasons.append("evidence_missing_language_mismatch")
    return reasons


def extract_run(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).resolve(strict=True)
    screenshot_path = root / "microsoft_verifier" / "result.json"
    dom_path = root / "dom_model" / "result.json"
    screenshot = load_json(screenshot_path)
    dom = load_json(dom_path)
    task_id, rubric_hash, criterion_count = _validate_pair(screenshot, dom)
    inventories = {mode: _source_inventory(root, mode) for mode in MODALITIES}
    criteria: list[dict[str, Any]] = []
    for index in range(criterion_count):
        screen_record = _extract_mode(screenshot, "screenshot", index)
        dom_record = _extract_mode(dom, "dom_model", index)
        reasons = disagreement_reasons(screen_record, dom_record)
        criteria.append(
            {
                "criterion_index": index,
                "criterion": screen_record["scoring"]["criterion"],
                "max_points": screen_record["max_points"],
                "screenshot": screen_record,
                "dom_model": dom_record,
                "disagreement_flag": bool(reasons),
                "disagreement_reasons": reasons,
                "manual_review_required": bool(reasons),
                "manual_review_status": "pending" if reasons else "not_required",
                "classification": None,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "run_id": root.name,
        "run_dir": str(root),
        "rubric_sha256": rubric_hash,
        "source_artifacts": {
            "screenshot_result": str(screenshot_path),
            "dom_model_result": str(dom_path),
        },
        "source_inventory": inventories,
        "criteria": criteria,
    }


def review_template(audit: dict[str, Any], *, include_all: bool = False) -> dict[str, Any]:
    reviews = []
    for row in audit.get("criteria", []):
        if not include_all and not row.get("manual_review_required"):
            continue
        reviews.append(
            {
                "criterion_index": row["criterion_index"],
                "criterion": row["criterion"],
                "disagreement_reasons": row.get("disagreement_reasons", []),
                "screenshot": {
                    "evidence_available": None,
                    "caught_correctly": None,
                    "review_note": "",
                },
                "dom_model": {
                    "evidence_available": None,
                    "caught_correctly": None,
                    "review_note": "",
                },
                "review_status": "pending",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": audit["task_id"],
        "run_id": audit["run_id"],
        "rubric_sha256": audit["rubric_sha256"],
        "instructions": (
            "Inspect only the cited source screenshots/DOM states. Set both booleans for each "
            "modality, add a short source note, and change review_status to confirmed."
        ),
        "reviews": reviews,
    }


def classify(
    *,
    screenshot_available: bool,
    screenshot_caught: bool,
    dom_available: bool,
    dom_caught: bool,
) -> str:
    values = (screenshot_available, screenshot_caught, dom_available, dom_caught)
    if not all(isinstance(value, bool) for value in values):
        raise ValueError("Classification requires four boolean review values")
    if not screenshot_available:
        if screenshot_caught:
            raise ValueError("Screenshot cannot be caught when screenshot evidence is missing")
        return "SCREENSHOT_EVIDENCE_MISSING"
    if not dom_available:
        if dom_caught:
            raise ValueError("DOM cannot be caught when DOM evidence is missing")
        return "DOM_EVIDENCE_MISSING"
    if screenshot_caught and dom_caught:
        return "BOTH_CAUGHT"
    if not screenshot_caught and dom_caught:
        return "SCREENSHOT_MISSED_DOM_CAUGHT"
    if screenshot_caught and not dom_caught:
        return "DOM_MISSED_SCREENSHOT_CAUGHT"
    return "BOTH_MISSED"


def apply_reviews(audit: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    for key in ("task_id", "run_id", "rubric_sha256"):
        if audit.get(key) != review.get(key):
            raise ValueError(f"Review {key} does not match audit")
    by_index = {row["criterion_index"]: row for row in audit.get("criteria", [])}
    seen: set[int] = set()
    for decision in review.get("reviews", []):
        index = decision.get("criterion_index")
        if index in seen or index not in by_index:
            raise ValueError(f"Duplicate or unknown review criterion index: {index}")
        seen.add(index)
        if decision.get("review_status") != "confirmed":
            continue
        row = by_index[index]
        values: dict[str, bool] = {}
        for mode in MODALITIES:
            mode_review = decision.get(mode) or {}
            available = mode_review.get("evidence_available")
            caught = mode_review.get("caught_correctly")
            if available is False and caught is None:
                caught = False
            if not isinstance(available, bool) or not isinstance(caught, bool):
                raise ValueError(f"Confirmed review {index}/{mode} requires boolean fields")
            row[mode]["manual_review"] = {
                "evidence_available": available,
                "caught_correctly": caught,
                "review_note": str(mode_review.get("review_note") or ""),
            }
            values[f"{mode}_available"] = available
            values[f"{mode}_caught"] = caught
        row["classification"] = classify(
            screenshot_available=values["screenshot_available"],
            screenshot_caught=values["screenshot_caught"],
            dom_available=values["dom_model_available"],
            dom_caught=values["dom_model_caught"],
        )
        row["manual_review_status"] = "confirmed"
    return audit


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": None if denominator == 0 else numerator / denominator,
        "percentage": None if denominator == 0 else round(100 * numerator / denominator, 2),
    }


def calculate_metrics(audit: dict[str, Any]) -> dict[str, Any]:
    rows = audit.get("criteria", [])
    counts = Counter(
        row.get("classification") for row in rows if row.get("classification") in CLASSIFICATIONS
    )
    screenshot_dom = counts["SCREENSHOT_MISSED_DOM_CAUGHT"]
    dom_screenshot = counts["DOM_MISSED_SCREENSHOT_CAUGHT"]
    both_missed = counts["BOTH_MISSED"]
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": audit.get("task_id"),
        "run_id": audit.get("run_id"),
        "rubric_sha256": audit.get("rubric_sha256"),
        "criterion_count": len(rows),
        "classification_counts": {name: counts[name] for name in CLASSIFICATIONS},
        "classified_count": sum(counts.values()),
        "pending_or_unreviewed_count": sum(
            1 for row in rows if row.get("classification") not in CLASSIFICATIONS
        ),
        "dom_recovery_of_confirmed_screenshot_misses": _rate(
            screenshot_dom, screenshot_dom + both_missed
        ),
        "screenshot_recovery_of_confirmed_dom_misses": _rate(
            dom_screenshot, dom_screenshot + both_missed
        ),
    }


def render_markdown(audit: dict[str, Any], metrics: dict[str, Any]) -> str:
    lines = [
        f"# Evidence Error Audit: {audit.get('task_id')}",
        "",
        f"Run: `{audit.get('run_id')}`  ",
        f"Rubric SHA-256: `{audit.get('rubric_sha256')}`",
        "",
        "| Criterion | Screenshot evidence reported | DOM evidence reported | Screenshot points | DOM points | Review | Classification |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in audit.get("criteria", []):
        screen = str(row["screenshot"].get("verifier_evidence") or "").replace("\n", " ").replace("|", "\\|")
        dom = str(row["dom_model"].get("verifier_evidence") or "").replace("\n", " ").replace("|", "\\|")
        if len(screen) > 240:
            screen = screen[:237] + "..."
        if len(dom) > 240:
            dom = dom[:237] + "..."
        lines.append(
            "| {index}: {criterion} | {screen} | {dom} | {sp}/{maximum} | {dp}/{maximum} | {review} | {classification} |".format(
                index=row["criterion_index"],
                criterion=str(row["criterion"]).replace("|", "\\|"),
                screen=screen,
                dom=dom,
                sp=row["screenshot"].get("final_points"),
                dp=row["dom_model"].get("final_points"),
                maximum=row.get("max_points"),
                review=row.get("manual_review_status"),
                classification=row.get("classification") or "PENDING",
            )
        )
    dom_rate = metrics["dom_recovery_of_confirmed_screenshot_misses"]
    screen_rate = metrics["screenshot_recovery_of_confirmed_dom_misses"]
    lines.extend(
        [
            "",
            "## Recovery metrics",
            "",
            f"- DOM recovery of confirmed screenshot misses: {dom_rate['numerator']}/{dom_rate['denominator']} ({dom_rate['percentage'] if dom_rate['percentage'] is not None else 'N/A'}%).",
            f"- Screenshot recovery of confirmed DOM misses: {screen_rate['numerator']}/{screen_rate['denominator']} ({screen_rate['percentage'] if screen_rate['percentage'] is not None else 'N/A'}%).",
            f"- Classified criteria: {metrics['classified_count']}/{metrics['criterion_count']}.",
            "",
        ]
    )
    return "\n".join(lines)
