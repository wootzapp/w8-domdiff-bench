"""Audit inventory, citation and adjudication contracts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .audit_evidence import _single_task_data, verifier_action_history



LINE_RANGE_RE = re.compile(r"^L0*(\d+)(?:-L0*(\d+))?$")


CITATION_KEYS = ("source", "location", "quote")


def _inventory_decisions(raw: dict, index: int, errors: list, screenshot_sources: set, dom_sources: set, screenshot_root: Path, dom_root: Path) -> dict:
    decisions = {}
    for modality, sources, source_root in (
        ("screenshot", screenshot_sources, screenshot_root),
        ("dom_model", dom_sources, dom_root),
    ):
        try:
            decisions[modality] = _validate_modality_decision(
                raw.get(modality), modality=modality,
                allowed_sources=sources, source_root=source_root,
            )
        except (ValueError, TypeError) as error:
            errors.append(f"criterion {index}, {modality}: {error}")
    return decisions


def _inventory_loss(raw: dict, screen: dict, dom: dict, screenshot_root: Path) -> tuple[bool, bool]:
    screenshot_loss = raw.get("screenshot_evidence_loss")
    dom_loss = raw.get("dom_model_evidence_loss")
    if not isinstance(screenshot_loss, bool) or not isinstance(dom_loss, bool):
        raise ValueError("Evidence-loss decisions must be booleans")
    if screenshot_loss and (screen["coverage"] == "COMPLETE" or dom["coverage"] == "ABSENT"):
        raise ValueError("Screenshot loss conflicts with the reported pairwise coverage")
    if dom_loss and (dom["coverage"] == "COMPLETE" or screen["coverage"] == "ABSENT"):
        raise ValueError("DOM loss conflicts with the reported pairwise coverage")
    context = (_single_task_data(screenshot_root).get("evaluation_context") or {}) if (screenshot_root / "task_data.json").is_file() else {}
    if context:
        eligible = set(context["audit_eligible_states"])
        for loss, counterpart, prefix, extension in ((screenshot_loss, dom, "dom_model", "txt"), (dom_loss, screen, "screenshot", "png")):
            allowed = {f"{prefix}{index}.{extension}" for index in eligible}
            if loss and not any(citation["source"] in allowed for citation in counterpart["citations"]):
                raise ValueError("Directional loss lacks decisive evidence from an eligible paired state")
    return screenshot_loss, dom_loss


def _inventory_row(raw: object, by_index: dict, errors: list, screenshot_sources: set, dom_sources: set, screenshot_root: Path, dom_root: Path) -> tuple:
    expected_keys = {
        "criterion_index", "required_evidence", "screenshot", "dom_model",
        "screenshot_evidence_loss", "dom_model_evidence_loss", "explanation",
    }
    if not isinstance(raw, dict):
        raise ValueError("Evidence auditor criterion row has an invalid schema")
    actual_keys = set(raw)
    # Classification follows the validated coverage and directional loss.
    if not expected_keys.issubset(actual_keys) or bool(
        actual_keys - expected_keys - {"classification"}
    ):
        raise ValueError("Evidence auditor criterion row has an invalid schema")
    index = raw.get("criterion_index")
    if isinstance(index, bool) or not isinstance(index, int) or index in by_index:
        raise ValueError("Evidence auditor criterion indices must be unique integers")
    required = str(raw.get("required_evidence") or "").strip()
    if not required:
        raise ValueError("Required evidence description must be non-empty")
    decisions = _inventory_decisions(raw, index, errors, screenshot_sources, dom_sources, screenshot_root, dom_root)
    if len(decisions) != 2:
        return index, None
    screen, dom = decisions["screenshot"], decisions["dom_model"]
    screenshot_loss, dom_loss = _inventory_loss(raw, screen, dom, screenshot_root)
    derived_classification = classification(screen, dom, screenshot_loss, dom_loss)
    explanation = str(raw.get("explanation") or "").strip()
    if not explanation:
        raise ValueError("Evidence auditor explanation must be non-empty")
    return index, {
        "required_evidence": required,
        "screenshot": screen,
        "dom_model": dom,
        "screenshot_evidence_loss": screenshot_loss,
        "dom_model_evidence_loss": dom_loss,
        "classification": derived_classification,
        "explanation": explanation,
    }


def validate_audit_response(
    value: dict[str, Any],
    *,
    criteria: list[dict[str, Any]],
    screenshot_sources: set[str],
    dom_sources: set[str],
    screenshot_root: Path,
    dom_root: Path,
) -> list[dict[str, Any]]:
    raw_rows = value.get("criteria")
    if not isinstance(raw_rows, list) or len(raw_rows) != len(criteria):
        raise ValueError("Evidence auditor returned an incomplete criteria list")
    by_index: dict[int, dict[str, Any]] = {}
    errors: list[str] = []
    for raw in raw_rows:
        index, row = _inventory_row(raw, by_index, errors, screenshot_sources, dom_sources, screenshot_root, dom_root)
        if row is None:
            continue
        by_index[index] = row
    if errors:
        raise ValueError("\n".join(errors))
    expected = list(range(len(criteria)))
    if sorted(by_index) != expected:
        raise ValueError(f"Evidence auditor criterion indices differ: {sorted(by_index)} != {expected}")
    return [{"criterion_index": index, **by_index[index]} for index in expected]


def _validate_string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    cleaned = [str(item).strip() for item in value]
    if any(not item for item in cleaned):
        raise ValueError(f"{field} contains an empty item")
    return cleaned


def _indexed_source(raw: str, allowed_sources: set[str], modality: str) -> str | None:
    number_match = re.search(r"(\d+)\D*$", raw)
    if number_match:
        cited_index = int(number_match.group(1))
        prefix = "screenshot" if modality == "screenshot" else "dom_model"
        extension = "png" if modality == "screenshot" else "txt"
        direct_name = f"{prefix}{cited_index}.{extension}"
        direct = direct_name if direct_name in allowed_sources else None
        one_based_index = cited_index - 1
        one_based = (
            f"screenshot{one_based_index}.png"
            if modality == "screenshot"
            else f"dom_model{one_based_index}.txt"
        )
        one_based_exists = cited_index > 0 and one_based in allowed_sources
        if direct and one_based_exists:
            allowed = ", ".join(sorted(allowed_sources))
            raise ValueError(
                f"Ambiguous {modality} citation source {raw!r}; use an exact filename from: "
                f"{allowed}"
            )
        if direct:
            return direct
        if one_based_exists:
            return one_based
    return None


def _resolve_source_name(source: object, allowed_sources: set[str], modality: str) -> str:
    """Resolve harmless source-label variants without guessing between real states."""

    raw = Path(str(source).strip()).name
    if raw in allowed_sources:
        return raw
    case_matches = [name for name in allowed_sources if name.casefold() == raw.casefold()]
    if len(case_matches) == 1:
        return case_matches[0]

    def normalized(value: str) -> str:
        stem = re.sub(r"\.(png|jpe?g|webp|txt)$", "", value, flags=re.IGNORECASE)
        return re.sub(r"[^a-z0-9]", "", stem.casefold())

    raw_normalized = normalized(raw)
    has_file_extension = re.search(r"\.(png|jpe?g|webp|txt)$", raw, re.IGNORECASE) is not None
    if has_file_extension:
        normalized_matches = [name for name in allowed_sources if normalized(name) == raw_normalized]
        if len(normalized_matches) == 1:
            return normalized_matches[0]
    indexed = _indexed_source(raw, allowed_sources, modality)
    if indexed is not None:
        return indexed
    allowed = ", ".join(sorted(allowed_sources))
    raise ValueError(
        f"Unknown {modality} citation source {raw!r}; allowed sources are: {allowed}"
    )


def _validate_text_citation(source: str, location: str, quote: str, source_root: Path) -> None:
    match = LINE_RANGE_RE.fullmatch(location)
    if match is None:
        raise ValueError(f"DOM citation location must be Lx or Lx-Ly: {source}, {location!r}")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    lines = (verifier_action_history(source_root).splitlines() if source == "action_history"
             else (source_root / source).read_text(encoding="utf-8").splitlines())
    if start < 1 or end < start or end > len(lines):
        raise ValueError(
            f"DOM citation line range is outside its source file: {source}, "
            f"{location!r}; source has {len(lines)} lines"
        )
    cited_text = "\n".join(lines[start - 1:end])
    if " ".join(quote.split()) not in " ".join(cited_text.split()):
        raise ValueError(
            "DOM citation quote is not present in the cited line range: "
            f"{source}, {location!r}, quote={quote!r}. Use a literal contiguous "
            "excerpt, without line-number labels, paraphrases or added ellipses."
        )


def _validate_citation(citation: object, modality: str, allowed_sources: set[str], source_root: Path) -> dict[str, str]:
    if not isinstance(citation, dict) or set(citation) != set(CITATION_KEYS):
        received = sorted(citation) if isinstance(citation, dict) else type(citation).__name__
        raise ValueError(
            "Evidence citation has an invalid schema; expected exactly "
            f"{list(CITATION_KEYS)!r}, received {received!r}"
        )
    sources = allowed_sources | ({"action_history"} if (source_root / "web_surfer.log").is_file() else set())
    context = (_single_task_data(source_root).get("evaluation_context") or {}) if (source_root / "task_data.json").is_file() else {}
    declared_source = Path(str(citation["source"])).name
    if context and re.fullmatch(r"(?:dom_model\d+\.txt|screenshot\d+\.png)", declared_source) and declared_source not in sources:
        raise ValueError(f"Unknown {modality} citation source {declared_source!r}: capture unavailable")
    source = _resolve_source_name(citation["source"], sources, modality)
    location = str(citation["location"]).strip()
    quote = str(citation["quote"]).strip()
    if not location:
        raise ValueError(f"Evidence citation location is empty for {source}")
    if not quote:
        raise ValueError(f"Evidence citation quote is empty for {source}")
    if modality == "dom_model" or source == "action_history":
        _validate_text_citation(source, location, quote, source_root)
    return {"source": source, "location": location, "quote": quote}


def _validate_citations(
    citations: list,
    *,
    modality: str,
    allowed_sources: set[str],
    source_root: Path,
) -> list[dict[str, str]]:
    clean_citations: list[dict[str, str]] = []
    citation_errors: list[str] = []
    for ordinal, citation in enumerate(citations, start=1):
        try:
            clean_citations.append(_validate_citation(citation, modality, allowed_sources, source_root))
        except (ValueError, TypeError) as error:
            citation_errors.append(f"citation {ordinal}: {error}")
    if citation_errors:
        raise ValueError("\n".join(citation_errors))
    return clean_citations


def _validate_coverage(coverage: str, available: list, missing: list, citations: list, modality: str) -> None:
    if coverage == "COMPLETE" and (not available or missing or not citations):
        raise ValueError(f"{modality} COMPLETE coverage has inconsistent detail")
    if coverage == "PARTIAL" and (not available or not missing or not citations):
        raise ValueError(f"{modality} PARTIAL coverage has inconsistent detail")
    if coverage == "ABSENT" and (available or not missing or citations):
        raise ValueError(f"{modality} ABSENT coverage has inconsistent detail")


def _validate_modality_decision(
    value: object,
    *,
    modality: str,
    allowed_sources: set[str],
    source_root: Path,
) -> dict[str, Any]:
    keys = {
        "coverage", "available_evidence", "missing_required_evidence",
        "verifier_caught", "citations",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{modality} decision has an invalid schema")
    coverage = value.get("coverage")
    if coverage not in {"COMPLETE", "PARTIAL", "ABSENT"}:
        raise ValueError(f"{modality} coverage must be COMPLETE, PARTIAL, or ABSENT")
    available = _validate_string_list(value.get("available_evidence"), "available_evidence")
    missing = _validate_string_list(
        value.get("missing_required_evidence"), "missing_required_evidence"
    )
    caught = value.get("verifier_caught")
    if not isinstance(caught, bool):
        raise ValueError(f"{modality} verifier_caught must be boolean")
    citations = value.get("citations")
    if not isinstance(citations, list):
        raise ValueError(f"{modality} citations must be a list")
    _validate_coverage(coverage, available, missing, citations, modality)
    clean_citations = _validate_citations(citations, modality=modality,
        allowed_sources=allowed_sources, source_root=source_root)
    return {
        "coverage": coverage,
        "available_evidence": available,
        "missing_required_evidence": missing,
        "verifier_caught": caught,
        "citations": clean_citations,
    }


def _finding_details(value: object, label: str) -> tuple:
    if not isinstance(value, dict) or set(value) != {
        "confirmed", "decisive_evidence", "citations", "explanation"
    }:
        raise ValueError(f"{label} finding has an invalid schema")
    confirmed = value.get("confirmed")
    if not isinstance(confirmed, bool):
        raise ValueError(f"{label} confirmed must be boolean")
    evidence = str(value.get("decisive_evidence") or "").strip()
    explanation = str(value.get("explanation") or "").strip()
    citations = value.get("citations")
    if not explanation or not isinstance(citations, list):
        raise ValueError(f"{label} requires an explanation and citation list")
    return confirmed, evidence, explanation, citations


def _finding_citation(citation: object, citation_modality: str, allowed_sources: set, source_root: Path, counterpart_sources: set, counterpart_root: Path | None, shared_sources: set) -> tuple:
    if not isinstance(citation, dict) or set(citation) != set(CITATION_KEYS):
        received = sorted(citation) if isinstance(citation, dict) else type(citation).__name__
        raise ValueError(f"Evidence citation has an invalid schema; expected exactly {list(CITATION_KEYS)!r}, received {received!r}")
    context = (_single_task_data(source_root).get("evaluation_context") or {}) if (source_root / "task_data.json").is_file() else {}
    declared_source = Path(str(citation["source"])).name
    if context and re.fullmatch(r"(?:dom_model\d+\.txt|screenshot\d+\.png)", declared_source) and declared_source not in allowed_sources | counterpart_sources:
        raise ValueError(f"Unknown {citation_modality} citation source {declared_source!r}: unavailable for this finding")
    source = _resolve_source_name(
        citation["source"], allowed_sources | counterpart_sources | shared_sources,
        citation_modality,
    )
    primary = source in allowed_sources or source in shared_sources
    actual_modality = citation_modality if primary else (
        "screenshot" if citation_modality == "dom_model" else "dom_model"
    )
    checked = _validate_citations(
        [{**citation, "source": source}],
        modality=actual_modality,
        allowed_sources=allowed_sources if primary else counterpart_sources,
        source_root=source_root if primary else counterpart_root,
    )
    return checked, primary, source


def _validate_finding_citations(citations: list, label: str, citation_modality: str, allowed_sources: set, source_root: Path, counterpart_sources: set, counterpart_root: Path | None, shared_sources: set) -> list:
    checked_citations, errors = [], []
    decisive = False
    for ordinal, citation in enumerate(citations, start=1):
        try:
            checked, primary, source = _finding_citation(citation, citation_modality, allowed_sources, source_root, counterpart_sources, counterpart_root, shared_sources)
            checked_citations.extend(checked)
            if primary and (not label.endswith("evidence loss") or source != "action_history"):
                decisive = True
        except (ValueError, TypeError) as error:
            errors.append(f"citation {ordinal}: {error}")
    if errors:
        raise ValueError(f"{label} requires {citation_modality} evidence: " + "\n".join(errors))
    if not decisive:
        raise ValueError(f"{label} requires decisive {citation_modality} evidence; supporting citations cannot replace the required source")
    return checked_citations


def _validate_finding(
    value: object,
    *,
    label: str,
    citation_modality: str,
    allowed_sources: set[str],
    source_root: Path,
    counterpart_sources: set[str] | None = None,
    counterpart_root: Path | None = None,
) -> dict[str, Any]:
    confirmed, evidence, explanation, citations = _finding_details(value, label)
    if not confirmed:
        if evidence or citations:
            raise ValueError(f"Unconfirmed {label} must not claim evidence or citations")
        return {
            "confirmed": False,
            "decisive_evidence": "",
            "citations": [],
            "explanation": explanation,
        }
    if not evidence or not citations:
        raise ValueError(f"Confirmed {label} requires decisive evidence and citations")
    counterpart_sources = counterpart_sources or set()
    if counterpart_sources and counterpart_root is None:
        raise ValueError("Counterpart citations require their source directory")
    shared_sources = {"action_history"} if (source_root / "web_surfer.log").is_file() else set()
    checked_citations = _validate_finding_citations(citations, label, citation_modality, allowed_sources, source_root, counterpart_sources, counterpart_root, shared_sources)
    return {
        "confirmed": True,
        "decisive_evidence": evidence,
        "citations": checked_citations,
        "explanation": explanation,
    }


def _adjudicated_findings(raw: dict, index: int, errors: list, screenshot_sources: set, dom_sources: set, screenshot_root: Path, dom_root: Path) -> dict:
    findings = {}
    for field, label, modality, sources, source_root in (
        ("screenshot_evidence_loss", "screenshot evidence loss", "dom_model", dom_sources, dom_root),
        ("dom_model_evidence_loss", "DOM evidence loss", "screenshot", screenshot_sources, screenshot_root),
        ("screenshot_verifier_miss", "screenshot verifier miss", "screenshot", screenshot_sources, screenshot_root),
        ("dom_model_verifier_miss", "DOM verifier miss", "dom_model", dom_sources, dom_root),
    ):
        try:
            counterpart_sources = screenshot_sources if modality == "dom_model" else dom_sources
            context = (_single_task_data(source_root).get("evaluation_context") or {}) if (source_root / "task_data.json").is_file() else {}
            if context and field.endswith("_evidence_loss"):
                eligible = set(context["audit_eligible_states"])
                sources = {name for name in sources if int(re.search(r"(\d+)\.[^.]+$", name).group(1)) in eligible}
                counterpart_sources = {name for name in counterpart_sources if int(re.search(r"(\d+)\.[^.]+$", name).group(1)) in eligible}
            findings[field] = _validate_finding(
                raw.get(field), label=label, citation_modality=modality,
                allowed_sources=sources, source_root=source_root,
                counterpart_sources=counterpart_sources,
                counterpart_root=screenshot_root if modality == "dom_model" else dom_root,
            )
        except (ValueError, TypeError) as error:
            errors.append(f"criterion {index}, {field}: {error}")
    return findings


def validate_adjudication_response(
    value: dict[str, Any],
    *,
    criteria: list[dict[str, Any]],
    screenshot_sources: set[str],
    dom_sources: set[str],
    screenshot_root: Path,
    dom_root: Path,
) -> list[dict[str, Any]]:
    raw_rows = value.get("criteria")
    if not isinstance(raw_rows, list) or len(raw_rows) != len(criteria):
        raise ValueError("Adjudicator returned an incomplete criteria list")
    expected_row_keys = {
        "criterion_index", "screenshot_evidence_loss", "dom_model_evidence_loss",
        "screenshot_verifier_miss", "dom_model_verifier_miss", "explanation",
    }
    by_index: dict[int, dict[str, Any]] = {}
    errors: list[str] = []
    for raw in raw_rows:
        if not isinstance(raw, dict) or set(raw) != expected_row_keys:
            raise ValueError("Adjudicator criterion row has an invalid schema")
        index = raw.get("criterion_index")
        if isinstance(index, bool) or not isinstance(index, int) or index in by_index:
            raise ValueError("Adjudicator criterion indices must be unique integers")
        explanation = str(raw.get("explanation") or "").strip()
        if not explanation:
            raise ValueError("Adjudicator criterion explanation must be non-empty")
        findings = _adjudicated_findings(raw, index, errors, screenshot_sources, dom_sources, screenshot_root, dom_root)
        by_index[index] = {**findings, "explanation": explanation}
    if errors:
        raise ValueError("\n".join(errors))
    expected = list(range(len(criteria)))
    if sorted(by_index) != expected:
        raise ValueError(f"Adjudicator criterion indices differ: {sorted(by_index)} != {expected}")
    return [{"criterion_index": index, **by_index[index]} for index in expected]


def classification(
    screenshot: dict[str, Any],
    dom: dict[str, Any],
    screenshot_loss: bool,
    dom_loss: bool,
) -> str:
    if screenshot_loss and dom_loss:
        return "BOTH_EVIDENCE_INCOMPLETE"
    if screenshot_loss:
        return "SCREENSHOT_EVIDENCE_MISSING"
    if dom_loss:
        return "DOM_EVIDENCE_MISSING"
    if screenshot["verifier_caught"] and dom["verifier_caught"]:
        return "BOTH_CAUGHT"
    if not screenshot["verifier_caught"] and dom["verifier_caught"]:
        return "SCREENSHOT_MISSED_DOM_CAUGHT"
    if screenshot["verifier_caught"] and not dom["verifier_caught"]:
        return "DOM_MISSED_SCREENSHOT_CAUGHT"
    return "BOTH_MISSED"
