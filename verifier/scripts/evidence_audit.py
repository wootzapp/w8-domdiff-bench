"""Automated, post-verification evidence audit for screenshot and DOM runs.

The audit is deliberately outside both verifier packages.  It does not change
rubrics, evidence selection, scoring, retries, or verifier prompts.  It asks a
separate judge to inspect every source state and the corresponding verifier
analysis, then calculates evidence-loss and recovery metrics deterministically.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

from .common import load_canonical_rubric, load_json, write_json
from .validate_inputs import SCREENSHOT_RE


SCHEMA_VERSION = "automated-evidence-audit/v3"
PROMPT_VERSION = "shared-trajectory-pairwise-adjudication/v3"
DEFAULT_AUDIT_MODEL = "gpt-5.6-sol"
DOM_RE = re.compile(r"^dom_model(0|[1-9]\d*)\.txt$")
LINE_RANGE_RE = re.compile(r"^L0*(\d+)(?:-L0*(\d+))?$")


class AuditValidationError(ValueError):
    """A model response remained structurally invalid after bounded retries."""

    def __init__(self, stage: str, attempts: list[dict[str, Any]], last_error: Exception):
        self.stage = stage
        self.attempts = attempts
        self.last_error = str(last_error)
        super().__init__(
            f"{stage} remained invalid after {len(attempts)} attempts: {last_error}"
        )

    def receipt(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "attempt_count": len(self.attempts),
            "last_validation_error": self.last_error,
            "attempts": self.attempts,
        }

SYSTEM_PROMPT = """You are the evidence-inventory stage of a pairwise audit.
For every rubric criterion, compare all supplied screenshot states with all
supplied DOM states, the shared trajectory, and each verifier's output.

For each modality, report whether the criterion-required evidence is COMPLETE,
PARTIAL, or ABSENT. Partial evidence is not complete. Preserve relationships:
labels must remain associated with their values, table cells with their row and
column, ordered events with their chronology, controls with selected state, and
URLs with the page/state they identify. A visible failure or blocker can itself
be criterion evidence. Do not infer hidden information.

Set screenshot_evidence_loss true only when criterion-required information is
missing or disconnected in screenshots but is available in DOM. Set
dom_model_evidence_loss by the exact reverse rule. Shared absence is not a
modality loss. Both flags may be true only when the modalities omit different
required information that the other preserves.

verifier_caught means the existing verifier accurately described both the
available evidence and any material evidence limitation in that modality. It is
not a judgment about whether you agree with the points awarded. Screenshot
claims may use only visible pixels; DOM claims may use only supplied DOM text.
The normalized action history is shared evidence for both modalities and may
prove process, navigation, stopping, and constraint compliance. The final
answer is a shared claim, not proof of page content. Consider the full ordered
trajectory: evidence from an earlier state remains available unless a later
state or action contradicts it. Action intent explains the attempted target but
is not proof of page content or success without execution/state evidence. An
action-history URL may prove an attempted or observed transition for process
evaluation, but it does not replace URL evidence in either modality when the
audit is comparing representation loss. Cite
every positive modality claim. Return JSON only. Your loss flags are proposals
that a separate adjudicator will review.
"""

ADJUDICATION_SYSTEM_PROMPT = """You are the final evidence-loss adjudicator.
Audit every criterion independently using the raw ordered screenshots, raw
ordered DOM states, normalized shared action history, final-answer claim,
verifier outputs, and the preliminary inventory.

Confirm screenshot evidence loss only when shared evidence plus DOM contains
explicit, cited, decision-essential evidence and shared evidence plus all
screenshots cannot establish the same criterion conclusion or score. Confirm
DOM evidence loss by the exact reverse rule. More explicit, redundant, or
convenient evidence is not loss. However, when a criterion requires proving the
website or page identity, an exact URL present in DOM but absent from screenshots
is screenshot evidence loss; branding is not a substitute for URL evidence. Do
not infer a site's omission from absent text unless the source explicitly states
the omission (such as "not listed", "none", or "TBD"). Shared ambiguity is not
loss.

Use temporal continuity across ordered states and the shared actions. An
earlier selected control or state remains evidence when no later action changes
it and the final state is consistent. Shared actions may prove process,
navigation, stopping, and prohibited-action constraints for both modalities.
Action intent identifies an attempted target but needs execution/state evidence
to prove success. An action-history URL may prove an attempted or observed
transition for process evaluation, but it does not replace URL evidence in
either modality when the audit is comparing representation loss. The final
answer is a claim, not proof of page content.

Confirm a verifier miss only when the corresponding shared-plus-modality input
contains sufficient decisive evidence and that verifier fails to identify it,
misreads it, contradicts it, or materially misuses it. Correct use of shared
action history is not a miss. Each confirmed finding needs a citation from the
modality containing the decisive or missed evidence. Return JSON only.
"""


def _criterion_value(container: object, index: int, default: object) -> object:
    if isinstance(container, dict):
        return container.get(str(index), container.get(index, default))
    if isinstance(container, list) and index < len(container):
        return container[index]
    return default


def extract_verifier_context(result: dict[str, Any], criterion_count: int) -> list[dict[str, Any]]:
    """Extract only existing evidence-analysis and score fields for the auditor."""

    intermediate = result.get("intermediate_mm_rubric_steps") or {}
    analyses = intermediate.get("step4_evidence_by_criterion") or {}
    rescoring = intermediate.get("step6_rescoring_summary") or []
    if not isinstance(rescoring, list) or len(rescoring) != criterion_count:
        raise ValueError("Verifier result lacks complete criterion rescoring rows")
    rows: list[dict[str, Any]] = []
    for index in range(criterion_count):
        raw_analysis = _criterion_value(analyses, index, [])
        if not isinstance(raw_analysis, list):
            raw_analysis = []
        score = rescoring[index]
        if not isinstance(score, dict):
            raise ValueError(f"Verifier criterion row {index} is not an object")
        rows.append(
            {
                "criterion_index": index,
                "evidence_analysis": raw_analysis,
                "applicable_evidence": score.get("applicable_evidence", ""),
                "action_only_points": score.get("earned_points"),
                "final_points": score.get(
                    "post_dom_earned_points",
                    score.get("post_image_earned_points", score.get("earned_points")),
                ),
                "max_points": score.get("max_points"),
                "final_justification": score.get(
                    "post_dom_justification",
                    score.get("post_image_justification", score.get("justification", "")),
                ),
            }
        )
    return rows


def _criteria_payload(rubric: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "criterion_index": index,
            "criterion": item["criterion"],
            "description": item["description"],
            "max_points": item["max_points"],
        }
        for index, item in enumerate(rubric["items"])
    ]


def _single_task_data(root: Path) -> dict[str, Any]:
    value = load_json(root / "task_data.json")
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise ValueError(f"Expected one task record in {root / 'task_data.json'}")
        return value[0]
    if not isinstance(value, dict):
        raise ValueError(f"Task data must be an object or one-item list in {root}")
    return value


def _trajectory_events(root: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        (root / "web_surfer.log").read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Trajectory line {line_number} in {root} is not an object")
        arguments = value.get("arguments") if isinstance(value.get("arguments"), dict) else {}
        events.append(
            {
                "action_index": len(events) + 1,
                "action": value.get("action") or arguments.get("action"),
                "text": arguments.get("text"),
                "intent": arguments.get("thoughts"),
                "url": value.get("url"),
                "execution_status": value.get("execution_status"),
            }
        )
    return events


def shared_trajectory_payload(screenshot_root: Path, dom_root: Path) -> dict[str, Any]:
    """Build representation-neutral evidence shared by both verifier inputs."""

    screenshot_task = _single_task_data(screenshot_root)
    dom_task = _single_task_data(dom_root)
    task_keys = ("task_id", "confirmed_task", "website")
    if any(screenshot_task.get(key) != dom_task.get(key) for key in task_keys):
        raise ValueError("Screenshot and DOM task metadata differ")
    screenshot_events = _trajectory_events(screenshot_root)
    dom_events = _trajectory_events(dom_root)
    if screenshot_events != dom_events:
        raise ValueError("Screenshot and DOM normalized action histories differ")
    screenshot_answer = load_json(screenshot_root / "final_answer.json")
    dom_answer = load_json(dom_root / "final_answer.json")
    if not isinstance(screenshot_answer, dict) or not isinstance(dom_answer, dict):
        raise ValueError("Final-answer sidecars must be objects")
    final_answer = screenshot_answer.get("final_answer")
    if final_answer != dom_answer.get("final_answer"):
        raise ValueError("Screenshot and DOM final answers differ")
    return {
        "task_id": screenshot_task.get("task_id"),
        "task_instruction": screenshot_task.get("confirmed_task"),
        "initial_url": screenshot_task.get("website"),
        "actions": screenshot_events,
        "final_answer_claim": final_answer,
    }


def _audit_request_text(
    *,
    criteria: list[dict[str, Any]],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
) -> str:
    return (
        "RUBRIC CRITERIA:\n"
        + json.dumps(criteria, ensure_ascii=False, indent=2)
        + "\n\nSHARED REPRESENTATION-NEUTRAL TRAJECTORY:\n"
        + json.dumps(shared_trajectory, ensure_ascii=False, indent=2)
        + "\n\nEXISTING SCREENSHOT VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(screenshot_context, ensure_ascii=False, indent=2)
        + "\n\nEXISTING DOM VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(dom_context, ensure_ascii=False, indent=2)
        + "\n\nReturn this exact shape:\n"
        '{"criteria":[{"criterion_index":0,"required_evidence":"what must be observable",'
        '"screenshot":{"coverage":"COMPLETE","available_evidence":["fact"],'
        '"missing_required_evidence":[],"verifier_caught":true,"citations":'
        '[{"source":"screenshot0.png","location":"visible location","quote":"visible text"}]},'
        '"dom_model":{"coverage":"PARTIAL","available_evidence":["fact"],'
        '"missing_required_evidence":["missing relationship"],"verifier_caught":true,'
        '"citations":[{"source":"dom_model0.txt","location":"L1-L2","quote":"exact text"}]},'
        '"screenshot_evidence_loss":false,"dom_model_evidence_loss":true,'
        '"explanation":"brief pairwise, evidence-grounded explanation"}]}\n'
        "Return exactly one row for every criterion index and no additional keys."
    )


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _source_instructions(screenshot_dir: Path, dom_dir: Path) -> str:
    screenshots = [path.name for path in ordered_audit_screenshots(screenshot_dir)]
    dom_states = [path.name for path in ordered_dom_states(dom_dir)]
    return (
        "CITATION SOURCE RULE: use one of these exact filenames.\n"
        f"Screenshot sources: {json.dumps(screenshots)}\n"
        f"DOM sources: {json.dumps(dom_states)}\n"
    )


def ordered_audit_screenshots(root: Path) -> list[Path]:
    """Return original screenshot states, ignoring verifier-created aliases."""

    indexed: dict[int, Path] = {}
    for path in root.iterdir():
        if not path.is_file() or path.is_symlink():
            continue
        match = SCREENSHOT_RE.fullmatch(path.name)
        if not match:
            continue
        index = int(match.group(1))
        if index in indexed:
            raise ValueError(f"Duplicate original screenshot index {index} in {root}")
        indexed[index] = path
    actual = sorted(indexed)
    if not actual or actual != list(range(len(actual))):
        raise ValueError(f"Original screenshots must be contiguous from 0, got {actual}")
    return [indexed[index] for index in actual]


def pairwise_messages(
    *,
    screenshot_dir: Path,
    dom_dir: Path,
    criteria: list[dict[str, Any]],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": _source_instructions(screenshot_dir, dom_dir) + "\n" + _audit_request_text(
            criteria=criteria,
            screenshot_context=screenshot_context,
            dom_context=dom_context,
            shared_trajectory=shared_trajectory,
        ),
    }]
    for path in ordered_dom_states(dom_dir):
        numbered = "\n".join(
            f"L{number:04d}: {line}"
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        )
        content.append({"type": "text", "text": f"DOM SOURCE FILE: {path.name}\n{numbered}"})
    screenshots = ordered_audit_screenshots(screenshot_dir)
    if not screenshots:
        raise ValueError("Screenshot audit requires at least one screenshot state")
    for path in screenshots:
        content.append({"type": "text", "text": f"SCREENSHOT SOURCE FILE: {path.name}"})
        content.append(
            {"type": "image_url", "image_url": {"url": _data_url(path), "detail": "high"}}
        )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def ordered_dom_states(dom_dir: Path) -> list[Path]:
    indexed: dict[int, Path] = {}
    for path in dom_dir.iterdir():
        if not path.is_file():
            continue
        match = DOM_RE.fullmatch(path.name)
        if match:
            index = int(match.group(1))
            if index in indexed:
                raise ValueError(f"Duplicate DOM state index {index}")
            indexed[index] = path
    actual = sorted(indexed)
    if not actual or actual != list(range(len(actual))):
        raise ValueError(f"DOM states must be contiguous from 0, got {actual}")
    return [indexed[index] for index in actual]


def _adjudication_request_text(
    *,
    criteria: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    preliminary: list[dict[str, Any]],
) -> str:
    finding = (
        '{"confirmed":false,"decisive_evidence":"",'
        '"citations":[],"explanation":"why this is or is not confirmed"}'
    )
    return (
        "RUBRIC CRITERIA:\n" + json.dumps(criteria, ensure_ascii=False, indent=2)
        + "\n\nSHARED REPRESENTATION-NEUTRAL TRAJECTORY:\n"
        + json.dumps(shared_trajectory, ensure_ascii=False, indent=2)
        + "\n\nSCREENSHOT VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(screenshot_context, ensure_ascii=False, indent=2)
        + "\n\nDOM VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(dom_context, ensure_ascii=False, indent=2)
        + "\n\nPRELIMINARY EVIDENCE INVENTORY (not ground truth):\n"
        + json.dumps(preliminary, ensure_ascii=False, indent=2)
        + "\n\nReturn exactly this shape with one row per criterion and no extra keys:\n"
        + '{"criteria":[{"criterion_index":0,'
        + '"screenshot_evidence_loss":' + finding + ','
        + '"dom_model_evidence_loss":' + finding + ','
        + '"screenshot_verifier_miss":' + finding + ','
        + '"dom_model_verifier_miss":' + finding + ','
        + '"explanation":"final criterion-level rationale"}]}\n'
        + "For a false finding, decisive_evidence must be an empty string and citations empty. "
        + "For a true finding, both must be non-empty."
    )


def adjudication_messages(
    *,
    screenshot_dir: Path,
    dom_dir: Path,
    criteria: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    preliminary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": _source_instructions(screenshot_dir, dom_dir) + "\n" + _adjudication_request_text(
            criteria=criteria,
            shared_trajectory=shared_trajectory,
            screenshot_context=screenshot_context,
            dom_context=dom_context,
            preliminary=preliminary,
        ),
    }]
    for path in ordered_dom_states(dom_dir):
        numbered = "\n".join(
            f"L{number:04d}: {line}"
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        )
        content.append({"type": "text", "text": f"DOM SOURCE FILE: {path.name}\n{numbered}"})
    for path in ordered_audit_screenshots(screenshot_dir):
        content.append({"type": "text", "text": f"SCREENSHOT SOURCE FILE: {path.name}"})
        content.append(
            {"type": "image_url", "image_url": {"url": _data_url(path), "detail": "high"}}
        )
    return [
        {"role": "system", "content": ADJUDICATION_SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _completion(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    response = OpenAI().chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Evidence auditor returned an empty response")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Evidence auditor response must be a JSON object")
    return value


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
    for raw in raw_rows:
        expected_keys = {
            "criterion_index", "required_evidence", "screenshot", "dom_model",
            "screenshot_evidence_loss", "dom_model_evidence_loss", "explanation",
        }
        if not isinstance(raw, dict):
            raise ValueError("Evidence auditor criterion row has an invalid schema")
        actual_keys = set(raw)
        # Older model responses sometimes volunteer a classification label even
        # though the prompt no longer requests one. Ignore that non-authoritative
        # field; Python derives the canonical classification below.
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
        screen = _validate_modality_decision(
            raw.get("screenshot"),
            modality="screenshot",
            allowed_sources=screenshot_sources,
            source_root=screenshot_root,
        )
        dom = _validate_modality_decision(
            raw.get("dom_model"),
            modality="dom_model",
            allowed_sources=dom_sources,
            source_root=dom_root,
        )
        screenshot_loss = raw.get("screenshot_evidence_loss")
        dom_loss = raw.get("dom_model_evidence_loss")
        if not isinstance(screenshot_loss, bool) or not isinstance(dom_loss, bool):
            raise ValueError("Evidence-loss decisions must be booleans")
        if screenshot_loss and (screen["coverage"] == "COMPLETE" or dom["coverage"] == "ABSENT"):
            raise ValueError("Screenshot loss conflicts with the reported pairwise coverage")
        if dom_loss and (dom["coverage"] == "COMPLETE" or screen["coverage"] == "ABSENT"):
            raise ValueError("DOM loss conflicts with the reported pairwise coverage")
        derived_classification = classification(screen, dom, screenshot_loss, dom_loss)
        explanation = str(raw.get("explanation") or "").strip()
        if not explanation:
            raise ValueError("Evidence auditor explanation must be non-empty")
        by_index[index] = {
            "required_evidence": required,
            "screenshot": screen,
            "dom_model": dom,
            "screenshot_evidence_loss": screenshot_loss,
            "dom_model_evidence_loss": dom_loss,
            "classification": derived_classification,
            "explanation": explanation,
        }
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
    allowed = ", ".join(sorted(allowed_sources))
    raise ValueError(
        f"Unknown {modality} citation source {raw!r}; allowed sources are: {allowed}"
    )


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
    if coverage == "COMPLETE" and (not available or missing or not citations):
        raise ValueError(f"{modality} COMPLETE coverage has inconsistent detail")
    if coverage == "PARTIAL" and (not available or not missing or not citations):
        raise ValueError(f"{modality} PARTIAL coverage has inconsistent detail")
    if coverage == "ABSENT" and (available or not missing or citations):
        raise ValueError(f"{modality} ABSENT coverage has inconsistent detail")
    clean_citations: list[dict[str, str]] = []
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {"source", "location", "quote"}:
            raise ValueError("Evidence citation has an invalid schema")
        source = _resolve_source_name(citation["source"], allowed_sources, modality)
        location = str(citation["location"]).strip()
        quote = str(citation["quote"]).strip()
        if not location:
            raise ValueError(f"Evidence citation location is empty for {source}")
        if not quote:
            raise ValueError(f"Evidence citation quote is empty for {source}")
        if modality == "dom_model":
            match = LINE_RANGE_RE.fullmatch(location)
            if match is None:
                raise ValueError("DOM citation location must be Lx or Lx-Ly")
            start = int(match.group(1))
            end = int(match.group(2) or start)
            lines = (source_root / source).read_text(encoding="utf-8").splitlines()
            if start < 1 or end < start or end > len(lines):
                raise ValueError("DOM citation line range is outside its source file")
            cited_text = "\n".join(lines[start - 1:end])
            if " ".join(quote.split()) not in " ".join(cited_text.split()):
                raise ValueError("DOM citation quote is not present in the cited line range")
        clean_citations.append({"source": source, "location": location, "quote": quote})
    return {
        "coverage": coverage,
        "available_evidence": available,
        "missing_required_evidence": missing,
        "verifier_caught": caught,
        "citations": clean_citations,
    }


def _validate_finding(
    value: object,
    *,
    label: str,
    citation_modality: str,
    allowed_sources: set[str],
    source_root: Path,
) -> dict[str, Any]:
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
    checked = _validate_modality_decision(
        {
            "coverage": "COMPLETE",
            "available_evidence": [evidence],
            "missing_required_evidence": [],
            "verifier_caught": True,
            "citations": citations,
        },
        modality=citation_modality,
        allowed_sources=allowed_sources,
        source_root=source_root,
    )
    return {
        "confirmed": True,
        "decisive_evidence": evidence,
        "citations": checked["citations"],
        "explanation": explanation,
    }


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
    for raw in raw_rows:
        if not isinstance(raw, dict) or set(raw) != expected_row_keys:
            raise ValueError("Adjudicator criterion row has an invalid schema")
        index = raw.get("criterion_index")
        if isinstance(index, bool) or not isinstance(index, int) or index in by_index:
            raise ValueError("Adjudicator criterion indices must be unique integers")
        explanation = str(raw.get("explanation") or "").strip()
        if not explanation:
            raise ValueError("Adjudicator criterion explanation must be non-empty")
        by_index[index] = {
            "screenshot_evidence_loss": _validate_finding(
                raw.get("screenshot_evidence_loss"),
                label="screenshot evidence loss",
                citation_modality="dom_model",
                allowed_sources=dom_sources,
                source_root=dom_root,
            ),
            "dom_model_evidence_loss": _validate_finding(
                raw.get("dom_model_evidence_loss"),
                label="DOM evidence loss",
                citation_modality="screenshot",
                allowed_sources=screenshot_sources,
                source_root=screenshot_root,
            ),
            "screenshot_verifier_miss": _validate_finding(
                raw.get("screenshot_verifier_miss"),
                label="screenshot verifier miss",
                citation_modality="screenshot",
                allowed_sources=screenshot_sources,
                source_root=screenshot_root,
            ),
            "dom_model_verifier_miss": _validate_finding(
                raw.get("dom_model_verifier_miss"),
                label="DOM verifier miss",
                citation_modality="dom_model",
                allowed_sources=dom_sources,
                source_root=dom_root,
            ),
            "explanation": explanation,
        }
    expected = list(range(len(criteria)))
    if sorted(by_index) != expected:
        raise ValueError(f"Adjudicator criterion indices differ: {sorted(by_index)} != {expected}")
    return [{"criterion_index": index, **by_index[index]} for index in expected]


def _request_validated_audit(
    *,
    model: str,
    messages: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    screenshot_sources: set[str],
    dom_sources: set[str],
    screenshot_root: Path,
    dom_root: Path,
    complete: Callable[[str, list[dict[str, Any]]], dict[str, Any]],
    max_attempts: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    current_messages = list(messages)
    last_error: Exception | None = None
    invalid_attempts: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        raw = complete(model, current_messages)
        try:
            decisions = validate_audit_response(
                raw,
                criteria=criteria,
                screenshot_sources=screenshot_sources,
                dom_sources=dom_sources,
                screenshot_root=screenshot_root,
                dom_root=dom_root,
            )
            return decisions, raw, attempt
        except (TypeError, ValueError) as exc:
            last_error = exc
            invalid_attempts.append(
                {"attempt": attempt, "validation_error": str(exc), "raw_response": raw}
            )
            if attempt < max_attempts:
                current_messages = current_messages + [
                    {"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)},
                    {
                        "role": "user",
                        "content": (
                            f"Your JSON failed validation: {exc}. Return a corrected complete JSON "
                            "object using the required schema and the same supplied evidence."
                        ),
                    },
                ]
    raise AuditValidationError(
        "primary evidence inventory",
        invalid_attempts,
        last_error or ValueError("unknown validation error"),
    )


def _request_validated_adjudication(
    *,
    model: str,
    messages: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    screenshot_sources: set[str],
    dom_sources: set[str],
    screenshot_root: Path,
    dom_root: Path,
    complete: Callable[[str, list[dict[str, Any]]], dict[str, Any]],
    max_attempts: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    current_messages = list(messages)
    last_error: Exception | None = None
    invalid_attempts: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        raw = complete(model, current_messages)
        try:
            decisions = validate_adjudication_response(
                raw,
                criteria=criteria,
                screenshot_sources=screenshot_sources,
                dom_sources=dom_sources,
                screenshot_root=screenshot_root,
                dom_root=dom_root,
            )
            return decisions, raw, attempt
        except (TypeError, ValueError) as exc:
            last_error = exc
            invalid_attempts.append(
                {"attempt": attempt, "validation_error": str(exc), "raw_response": raw}
            )
            if attempt < max_attempts:
                current_messages = current_messages + [
                    {"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)},
                    {
                        "role": "user",
                        "content": (
                            f"Your adjudication JSON failed validation: {exc}. Return a corrected "
                            "complete JSON object using the required schema and same evidence."
                        ),
                    },
                ]
    raise AuditValidationError(
        "final evidence adjudication",
        invalid_attempts,
        last_error or ValueError("unknown validation error"),
    )


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


def calculate_metrics(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(criteria)
    if total == 0:
        raise ValueError("Cannot calculate evidence loss with zero criteria")
    screenshot_loss = sum(bool(row["screenshot_evidence_loss"]) for row in criteria)
    dom_loss = sum(bool(row["dom_model_evidence_loss"]) for row in criteria)
    screenshot_misses = sum(not row["screenshot"]["verifier_caught"] for row in criteria)
    dom_misses = sum(not row["dom_model"]["verifier_caught"] for row in criteria)
    screenshot_recovered = sum(
        not row["screenshot"]["verifier_caught"]
        and row["dom_model"]["verifier_caught"]
        and not row["screenshot_evidence_loss"]
        and not row["dom_model_evidence_loss"]
        for row in criteria
    )
    dom_recovered = sum(
        not row["dom_model"]["verifier_caught"]
        and row["screenshot"]["verifier_caught"]
        and not row["screenshot_evidence_loss"]
        and not row["dom_model_evidence_loss"]
        for row in criteria
    )

    def rate(count: int, denominator: int) -> float | None:
        return count / denominator if denominator else None

    return {
        "total_criteria": total,
        "screenshot_evidence_loss": {
            "count": screenshot_loss, "denominator": total, "rate": rate(screenshot_loss, total)
        },
        "dom_model_evidence_loss": {
            "count": dom_loss, "denominator": total, "rate": rate(dom_loss, total)
        },
        "screenshot_verifier_misses": {
            "count": screenshot_misses, "denominator": total, "rate": rate(screenshot_misses, total)
        },
        "dom_model_verifier_misses": {
            "count": dom_misses, "denominator": total, "rate": rate(dom_misses, total)
        },
        "screenshot_misses_recovered_by_dom": {
            "count": screenshot_recovered,
            "denominator": screenshot_misses,
            "rate": rate(screenshot_recovered, screenshot_misses),
        },
        "dom_misses_recovered_by_screenshot": {
            "count": dom_recovered,
            "denominator": dom_misses,
            "rate": rate(dom_recovered, dom_misses),
        },
    }


def run_evidence_audit(
    *,
    screenshot_dir: str | Path,
    dom_dir: str | Path,
    rubric_file: str | Path,
    screenshot_result: str | Path,
    dom_result: str | Path,
    task_alias: str | None = None,
    model: str = DEFAULT_AUDIT_MODEL,
    complete: Callable[[str, list[dict[str, Any]]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    frozen = load_canonical_rubric(rubric_file)
    criteria = _criteria_payload(frozen.rubric)
    screenshot_raw = load_json(screenshot_result)
    dom_raw = load_json(dom_result)
    if screenshot_raw.get("task_id") != frozen.task_id or dom_raw.get("task_id") != frozen.task_id:
        raise ValueError("Evidence audit result task IDs differ from the frozen rubric")
    if screenshot_raw.get("rubric_sha256") != frozen.sha256 or dom_raw.get("rubric_sha256") != frozen.sha256:
        raise ValueError("Evidence audit result rubric hashes differ from the frozen rubric")
    screenshot_context = extract_verifier_context(screenshot_raw, len(criteria))
    dom_context = extract_verifier_context(dom_raw, len(criteria))
    screenshot_root = Path(screenshot_dir).resolve(strict=True)
    dom_root = Path(dom_dir).resolve(strict=True)
    shared_trajectory = shared_trajectory_payload(screenshot_root, dom_root)
    screen_sources = {path.name for path in ordered_audit_screenshots(screenshot_root)}
    dom_sources = {path.name for path in ordered_dom_states(dom_root)}
    call = complete or (lambda selected_model, messages: _completion(selected_model, messages))
    decisions, raw_audit, attempts = _request_validated_audit(
        model=model,
        messages=pairwise_messages(
            screenshot_dir=screenshot_root,
            dom_dir=dom_root,
            criteria=criteria,
            screenshot_context=screenshot_context,
            dom_context=dom_context,
            shared_trajectory=shared_trajectory,
        ),
        criteria=criteria,
        screenshot_sources=screen_sources,
        dom_sources=dom_sources,
        screenshot_root=screenshot_root,
        dom_root=dom_root,
        complete=call,
    )
    adjudications, raw_adjudication, adjudication_attempts = _request_validated_adjudication(
        model=model,
        messages=adjudication_messages(
            screenshot_dir=screenshot_root,
            dom_dir=dom_root,
            criteria=criteria,
            shared_trajectory=shared_trajectory,
            screenshot_context=screenshot_context,
            dom_context=dom_context,
            preliminary=decisions,
        ),
        criteria=criteria,
        screenshot_sources=screen_sources,
        dom_sources=dom_sources,
        screenshot_root=screenshot_root,
        dom_root=dom_root,
        complete=call,
    )
    rows: list[dict[str, Any]] = []
    for criterion, decision, adjudication, screen_context, dom_verifier_context in zip(
        criteria, decisions, adjudications, screenshot_context, dom_context
    ):
        screenshot_loss = adjudication["screenshot_evidence_loss"]["confirmed"]
        dom_loss = adjudication["dom_model_evidence_loss"]["confirmed"]
        screenshot_caught = not adjudication["screenshot_verifier_miss"]["confirmed"]
        dom_caught = not adjudication["dom_model_verifier_miss"]["confirmed"]
        screenshot_decision = {
            **decision["screenshot"],
            "verifier_caught": screenshot_caught,
            "verifier_output": screen_context,
        }
        dom_decision = {
            **decision["dom_model"],
            "verifier_caught": dom_caught,
            "verifier_output": dom_verifier_context,
        }
        rows.append(
            {
                **criterion,
                "required_evidence": decision["required_evidence"],
                "screenshot": screenshot_decision,
                "dom_model": dom_decision,
                "screenshot_evidence_loss": screenshot_loss,
                "dom_model_evidence_loss": dom_loss,
                "classification": classification(
                    screenshot_decision, dom_decision, screenshot_loss, dom_loss
                ),
                "explanation": adjudication["explanation"],
                "adjudication": adjudication,
                "preliminary_inventory": decision,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "audit_method": "automated_llm",
        "audit_model": model,
        "task_id": frozen.task_id,
        "task_alias": task_alias,
        "frozen_rubric_sha256": frozen.sha256,
        "shared_trajectory": shared_trajectory,
        "primary_auditor_output": {"attempts": attempts, "raw": raw_audit},
        "adjudicator_output": {
            "attempts": adjudication_attempts,
            "raw": raw_adjudication,
        },
        "criteria": rows,
        "metrics": calculate_metrics(rows),
    }


def aggregate_audits(audits: list[dict[str, Any]], failures: list[dict[str, str]] | None = None) -> dict[str, Any]:
    all_rows = [row for audit in audits for row in audit.get("criteria", [])]
    if not all_rows:
        raise ValueError("No completed evidence audits to aggregate")
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_method": "automated_llm",
        "completed_tasks": len(audits),
        "failed_tasks": failures or [],
        "per_task": [
            {
                "task_alias": audit.get("task_alias"),
                "task_id": audit["task_id"],
                "metrics": audit["metrics"],
            }
            for audit in audits
        ],
        "metrics": calculate_metrics(all_rows),
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_markdown(audit: dict[str, Any]) -> str:
    metrics = audit["metrics"]
    lines = [
        f"# Evidence audit: {audit['task_id']}", "",
        "| Criterion | Screenshot coverage/caught | DOM coverage/caught | Classification |",
        "|---|:---:|:---:|---|",
    ]
    for row in audit["criteria"]:
        screen = row["screenshot"]
        dom = row["dom_model"]
        lines.append(
            f"| {row['criterion']} | {screen['coverage']}/{screen['verifier_caught']} | "
            f"{dom['coverage']}/{dom['verifier_caught']} | {row['classification']} |"
        )
    lines.extend(["", "## Evidence-loss summary", ""])
    for label, key in (
        ("Screenshot", "screenshot_evidence_loss"),
        ("DOM-model", "dom_model_evidence_loss"),
    ):
        item = metrics[key]
        lines.append(
            f"- {label}: {item['count']}/{item['denominator']} ({_pct(item['rate'])})"
        )
    lines.append("")
    return "\n".join(lines)


def render_aggregate_markdown(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    lines = [
        "# Aggregate automated evidence audit", "",
        f"Completed tasks: {summary['completed_tasks']}",
        f"Failed tasks: {len(summary.get('failed_tasks', []))}", "",
        "| Modality | Missing evidence | Rate |",
        "|---|---:|---:|",
    ]
    for label, key in (
        ("Screenshot", "screenshot_evidence_loss"),
        ("DOM-model", "dom_model_evidence_loss"),
    ):
        item = metrics[key]
        lines.append(
            f"| {label} | {item['count']}/{item['denominator']} | {_pct(item['rate'])} |"
        )
    if summary.get("failed_tasks"):
        lines.extend(["", "## Failed tasks", ""])
        for failure in summary["failed_tasks"]:
            lines.append(f"- `{failure['task']}`: {failure['error']}")
    lines.append("")
    return "\n".join(lines)


def append_audit_to_comparison(
    *, comparison_json: Path, comparison_markdown: Path, audit: dict[str, Any]
) -> None:
    comparison = load_json(comparison_json)
    comparison["evidence_audit"] = audit["metrics"]
    write_json(comparison_json, comparison)
    existing = comparison_markdown.read_text(encoding="utf-8").rstrip()
    comparison_markdown.write_text(
        existing + "\n\n## Automated evidence audit\n\n"
        + "| Modality | Missing evidence | Rate |\n|---|---:|---:|\n"
        + "| Screenshot | {}/{} | {} |\n".format(
            audit["metrics"]["screenshot_evidence_loss"]["count"],
            audit["metrics"]["screenshot_evidence_loss"]["denominator"],
            _pct(audit["metrics"]["screenshot_evidence_loss"]["rate"]),
        )
        + "| DOM-model | {}/{} | {} |\n".format(
            audit["metrics"]["dom_model_evidence_loss"]["count"],
            audit["metrics"]["dom_model_evidence_loss"]["denominator"],
            _pct(audit["metrics"]["dom_model_evidence_loss"]["rate"]),
        ),
        encoding="utf-8",
    )
