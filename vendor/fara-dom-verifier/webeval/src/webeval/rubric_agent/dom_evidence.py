"""Typed semantic-DOM evidence loading and deterministic text projection."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DOMCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["complete", "partial", "truncated", "failed"]
    rendered_dom: bool
    nodes_seen: int = Field(ge=0)
    nodes_captured: int = Field(ge=0)
    node_limit: int = Field(ge=1)
    text_limit: int = Field(ge=1)
    truncated: bool
    same_origin_frames: int = Field(ge=0)
    open_shadow_roots: int = Field(ge=0)
    cross_origin_frames: list[str]
    canvas_count: int = Field(ge=0)
    image_without_alt_count: int = Field(ge=0)
    unsupported: list[str]
    errors: list[str]


class SemanticDOMNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    parent_key: str | None
    frame_path: str
    role: str
    name: str
    text: str
    value: str
    tag: str
    states: dict[str, Any]


class SemanticDOMSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["semantic-dom-snapshot/v1"]
    canonicalizer_version: str
    snapshot_id: str
    ordinal: int = Field(ge=0)
    url: str
    title: str
    captured_at: str
    hash: str
    nodes: list[SemanticDOMNode]
    coverage: DOMCoverage

    @model_validator(mode="after")
    def _validate_hash(self) -> "SemanticDOMSnapshot":
        payload = self.model_dump(
            exclude={"snapshot_id", "ordinal", "captured_at", "hash"}
        )
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if self.hash != expected:
            raise ValueError(
                f"snapshot hash mismatch: declared {self.hash!r}, computed {expected!r}"
            )
        return self


class DOMUpdatedNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    changes: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _validate_changes(self) -> "DOMUpdatedNode":
        for field, change in self.changes.items():
            if set(change) != {"before", "after"}:
                raise ValueError(
                    f"updated field {field!r} must contain only before and after"
                )
        return self


class SemanticDOMDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["semantic-dom-diff/v1"]
    canonicalizer_version: str
    diff_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    from_hash: str
    to_hash: str
    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    updated: list[DOMUpdatedNode]
    unchanged_count: int = Field(ge=0)


class DOMEvidenceFrame(BaseModel):
    """One action-aligned semantic evidence frame."""

    action_ordinal: int = Field(ge=0)
    action_id: str = ""
    before_snapshot_path: str = ""
    after_snapshot_path: str
    diff_path: str = ""
    before_page_state_path: str = ""
    after_page_state_path: str = ""
    verifier_action_path: str = ""
    capture_status: str = ""
    coverage_status: str = ""
    before_snapshot: SemanticDOMSnapshot | dict[str, Any] | None = None
    snapshot: SemanticDOMSnapshot | dict[str, Any]
    diff: SemanticDOMDiff | dict[str, Any] | None = None
    before_page_state: dict[str, Any] | None = None
    after_page_state: dict[str, Any] | None = None
    verifier_action: dict[str, Any] | None = None


def _load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"DOM evidence file not found: {resolved}")
    with resolved.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"DOM evidence must be a JSON object: {resolved}")
    return value


def load_snapshot(path: str | Path) -> SemanticDOMSnapshot:
    return SemanticDOMSnapshot.model_validate(_load_json(path))


def load_diff(path: str | Path) -> SemanticDOMDiff:
    return SemanticDOMDiff.model_validate(_load_json(path))


def load_dom_frames(actions: Iterable[dict[str, Any]]) -> list[DOMEvidenceFrame]:
    """Load and validate action-aligned frames in deterministic ordinal order."""
    frames: list[DOMEvidenceFrame] = []
    for action in actions:
        before_path = str(action.get("dom_before_snapshot_path") or "")
        after_path = str(action.get("dom_after_snapshot_path") or "")
        if not after_path:
            raise ValueError(
                f"Action {action.get('id')} has no DOM after-snapshot path"
            )
        diff_path = str(action.get("dom_diff_path") or "")
        before_page_state_path = str(action.get("dom_before_page_state_path") or "")
        after_page_state_path = str(action.get("dom_after_page_state_path") or "")
        verifier_action_path = str(action.get("dom_verifier_action_path") or "")
        ordinal = int(action.get("dom_action_ordinal") or action.get("id") or 0)
        before_snapshot = _load_snapshot_auto(before_path) if before_path else None
        after_snapshot = _load_snapshot_auto(after_path)
        diff = _load_diff_auto(diff_path) if diff_path else None
        frame = DOMEvidenceFrame(
            action_ordinal=ordinal,
            action_id=str(action.get("dom_action_id") or ""),
            before_snapshot_path=before_path,
            after_snapshot_path=after_path,
            diff_path=diff_path,
            before_page_state_path=before_page_state_path,
            after_page_state_path=after_page_state_path,
            verifier_action_path=verifier_action_path,
            capture_status=str(action.get("dom_capture_status") or ""),
            coverage_status=str(action.get("dom_coverage_status") or ""),
            before_snapshot=before_snapshot,
            snapshot=after_snapshot,
            diff=diff,
            before_page_state=(
                _load_json(before_page_state_path) if before_page_state_path else None
            ),
            after_page_state=(
                _load_json(after_page_state_path) if after_page_state_path else None
            ),
            verifier_action=(
                _load_json(verifier_action_path) if verifier_action_path else None
            ),
        )
        if isinstance(frame.snapshot, SemanticDOMSnapshot) and frame.snapshot.ordinal != ordinal:
            raise ValueError(
                f"DOM ordinal mismatch: action {ordinal}, snapshot "
                f"{frame.snapshot.ordinal} ({after_path})"
            )
        if (
            isinstance(frame.diff, SemanticDOMDiff)
            and isinstance(frame.snapshot, SemanticDOMSnapshot)
            and frame.diff.to_snapshot_id != frame.snapshot.snapshot_id
        ):
            raise ValueError(
                f"DOM diff target {frame.diff.to_snapshot_id!r} does not match "
                f"snapshot {frame.snapshot.snapshot_id!r}"
            )
        if (
            isinstance(frame.diff, SemanticDOMDiff)
            and isinstance(frame.snapshot, SemanticDOMSnapshot)
            and frame.diff.to_hash != frame.snapshot.hash
        ):
            raise ValueError(
                f"DOM diff target hash does not match snapshot {frame.snapshot.snapshot_id!r}"
            )
        if (
            isinstance(frame.diff, SemanticDOMDiff)
            and isinstance(frame.before_snapshot, SemanticDOMSnapshot)
        ):
            if (
                frame.diff.from_snapshot_id
                != frame.before_snapshot.snapshot_id
                or frame.diff.from_hash != frame.before_snapshot.hash
            ):
                raise ValueError(
                    f"DOM diff source does not match before-snapshot for action {ordinal}"
                )
        frames.append(frame)
    frames.sort(key=lambda frame: (frame.action_ordinal, frame.action_id))
    ordinals = [frame.action_ordinal for frame in frames]
    if len(ordinals) != len(set(ordinals)):
        raise ValueError(f"Duplicate DOM action ordinals: {ordinals}")
    return frames


def _load_snapshot_auto(path: str | Path) -> SemanticDOMSnapshot | dict[str, Any]:
    payload = _load_json(path)
    if payload.get("schema_version") == "semantic-dom-snapshot/v1":
        return SemanticDOMSnapshot.model_validate(payload)
    return payload


def _load_diff_auto(path: str | Path) -> SemanticDOMDiff | dict[str, Any]:
    payload = _load_json(path)
    if payload.get("schema_version") == "semantic-dom-diff/v1":
        return SemanticDOMDiff.model_validate(payload)
    return payload


def _compact(value: Any, limit: int = 240) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


_STOPWORDS = {
    "able",
    "about",
    "after",
    "agent",
    "also",
    "and",
    "any",
    "are",
    "asked",
    "been",
    "because",
    "before",
    "being",
    "book",
    "browser",
    "can",
    "click",
    "could",
    "did",
    "does",
    "done",
    "every",
    "find",
    "for",
    "from",
    "give",
    "has",
    "have",
    "how",
    "identifies",
    "identify",
    "implements",
    "into",
    "its",
    "latest",
    "look",
    "manual",
    "not",
    "of",
    "on",
    "or",
    "page",
    "provide",
    "scroll",
    "should",
    "source",
    "step",
    "task",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "to",
    "use",
    "used",
    "using",
    "was",
    "what",
    "when",
    "where",
    "whether",
    "which",
    "with",
    "would",
}

def build_dom_retrieval_terms(
    *,
    task: str = "",
    rubric_items: list[dict[str, Any]] | None = None,
    predicted_output: str = "",
    evidence_context: Iterable[Any] | None = None,
) -> list[str]:
    """Build deterministic search terms for DOM evidence retrieval.

    The first DOM pipeline passed chronological DOM slices to the judge. That
    loses high-value page facts when large pages bury the relevant nodes deep in
    a diff. Terms are generated at inference time from the current task, rubric,
    final-answer claims, action metadata, URLs, titles, and generic web/control
    state vocabulary. There are intentionally no task-specific hardcoded terms.
    """
    source_parts = [task, predicted_output]
    for item in rubric_items or []:
        source_parts.append(str(item.get("criterion") or ""))
        source_parts.append(str(item.get("description") or ""))
        source_parts.append(str(item.get("condition") or ""))
    for context in evidence_context or []:
        source_parts.append(_context_to_search_text(context))
    joined = "\n".join(source_parts)

    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+/#‑–-]{1,}", joined):
        normalized = _normalize_term(token)
        if len(normalized) >= 2 and normalized not in _STOPWORDS:
            terms.add(normalized)

    # Preserve useful multi-token claims and task-specific phrases.
    phrase_patterns = [
        r"['\"]([^'\"]{3,80})['\"]",
        r"\$\s?\d+(?:,\d{3})*(?:\.\d{2})?",
        r"\b\d+(?:\.\d+)?\s*(?:GB|TB|MB|inch|inches|hours?|lbs?|kg|cm|mm)\b",
        r"\b(?:US|UK|EU)\s+Size\s*[=:]?\s*\d+(?:\.\d+)?\b",
        r"\bsize\s*[=:]?\s*\d+(?:\.\d+)?\b",
        r"\b[A-Za-z0-9][A-Za-z0-9.+/#‑–-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.+/#‑–-]*){1,5}\b",
    ]
    for pattern in phrase_patterns:
        for match in re.findall(pattern, joined, flags=re.IGNORECASE):
            if isinstance(match, tuple):
                match = " ".join(part for part in match if part)
            normalized = _normalize_term(match)
            if len(normalized) >= 3 and not _phrase_is_mostly_stopwords(normalized):
                terms.add(normalized)

    return sorted(terms, key=lambda item: (-len(item), item))


def _context_to_search_text(context: Any) -> str:
    if isinstance(context, (dict, list)):
        try:
            return json.dumps(context, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(context)
    return str(context or "")


def _phrase_is_mostly_stopwords(phrase: str) -> bool:
    tokens = [
        _normalize_term(token)
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+/#‑–-]{1,}", phrase)
    ]
    if not tokens:
        return True
    return sum(token in _STOPWORDS for token in tokens) >= max(1, len(tokens) - 1)


def _normalize_term(value: str) -> str:
    return (
        " ".join(str(value).replace("‑", "-").replace("–", "-").split())
        .strip()
        .lower()
    )


def _normalize_evidence_text(value: str) -> str:
    return " ".join(str(value).replace("‑", "-").replace("–", "-").split())


def _line_relevance(line: str, terms: list[str]) -> int:
    lower = _normalize_term(line)
    score = 0
    for term in terms:
        if term and term in lower:
            score += 3 + min(len(term), 30) // 6
    if _looks_noisy_dom_text(line):
        score -= 20
    return score


def _looks_noisy_dom_text(text: str) -> bool:
    value = str(text).strip()
    if not value:
        return True
    if len(value) > 900 and value.count(" ") < 8:
        return True
    # SVG path payloads dominate ChromiumRL captures and look like "M117.8,58..."
    if len(value) > 180 and re.search(r"\b[MLCQHVZST]\d+(?:\.\d+)?,", value):
        return True
    if value.count("srcset=") > 1:
        return True
    return False


def _dedupe_ranked(lines: list[tuple[int, str]], *, max_lines: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for _, line in sorted(lines, key=lambda item: (-item[0], item[1])):
        compacted = _normalize_evidence_text(line)
        key = compacted.lower()
        if not compacted or key in seen:
            continue
        seen.add(key)
        output.append(compacted)
        if len(output) >= max_lines:
            break
    return output


def _node_line(node: SemanticDOMNode | dict[str, Any], prefix: str = "") -> str:
    data = node.model_dump() if isinstance(node, SemanticDOMNode) else node
    fields = [
        f"key={_compact(data.get('key'))}",
        f"frame={_compact(data.get('frame_path') or 'main')}",
        f"role={_compact(data.get('role'))}",
        f"name={_compact(data.get('name'))}",
        f"text={_compact(data.get('text'))}",
        f"value={_compact(data.get('value'))}",
    ]
    states = data.get("states")
    if states:
        fields.append(f"states={_compact(states)}")
    return prefix + " ".join(fields)


def coverage_text(coverage: DOMCoverage) -> str:
    limitations: list[str] = []
    if coverage.truncated:
        limitations.append("node/text capture truncated")
    if coverage.cross_origin_frames:
        limitations.append(
            f"{len(coverage.cross_origin_frames)} cross-origin frame(s) excluded"
        )
    if coverage.canvas_count:
        limitations.append(f"{coverage.canvas_count} canvas surface(s) not captured")
    if coverage.image_without_alt_count:
        limitations.append(
            f"{coverage.image_without_alt_count} image(s) without alt text"
        )
    limitations.extend(coverage.unsupported)
    limitations.extend(coverage.errors)
    suffix = "; ".join(dict.fromkeys(limitations)) or "none declared"
    return (
        f"coverage={coverage.status}; rendered_dom={coverage.rendered_dom}; "
        f"nodes={coverage.nodes_captured}/{coverage.nodes_seen}; "
        f"same_origin_frames={coverage.same_origin_frames}; limitations={suffix}"
    )


def project_snapshot(
    snapshot: SemanticDOMSnapshot | dict[str, Any], *, char_budget: int = 12000
) -> str:
    """Project a snapshot to stable text, respecting a strict character budget."""
    if isinstance(snapshot, dict):
        return project_chromiumrl_snapshot(snapshot, char_budget=char_budget)
    header = (
        f"STATE snapshot={snapshot.snapshot_id} ordinal={snapshot.ordinal}\n"
        f"url={_compact(snapshot.url, 500)}\n"
        f"title={_compact(snapshot.title, 500)}\n"
        f"{coverage_text(snapshot.coverage)}\nNODES:\n"
    )
    lines = [_node_line(node) for node in sorted(snapshot.nodes, key=lambda n: n.key)]
    return _budget(header, lines, char_budget)


def project_chromiumrl_snapshot(
    snapshot: dict[str, Any], *, char_budget: int = 12000
) -> str:
    """Project a ChromiumRL DOM snapshot into compact text evidence."""
    nodes = snapshot.get("nodes") or []
    header = (
        "STATE schema=chromiumrl_dom\n"
        f"url={_compact(snapshot.get('url'), 500)}\n"
        f"title={_compact(snapshot.get('title'), 500)}\n"
        f"viewport={_compact(snapshot.get('viewport'), 500)}\n"
        f"nodes={len(nodes)}\nNODES:\n"
    )
    candidates: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        text = _node_text(node)
        attrs_text = _attributes_text(node)
        useful = bool(text or attrs_text)
        visible = bool(node.get("isVisible") or node.get("isInViewport"))
        interactive = _is_interactive_node(node)
        if useful and (visible or interactive):
            candidates.append(node)
    # Prefer in-viewport and interactive evidence first, then stable order.
    candidates.sort(
        key=lambda n: (
            not bool(n.get("isInViewport")),
            not _is_interactive_node(n),
            int(n.get("nodeId") or 0),
        )
    )
    lines = [_chromiumrl_node_line(node) for node in candidates]
    return _budget(header, lines, char_budget)


def _node_text(node: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("textContent", "innerText", "ariaLabel", "accessibleName"):
        value = node.get(key)
        if value:
            parts.append(" ".join(str(value).split()))
    return " ".join(parts).strip()


def _attributes_text(node: dict[str, Any]) -> str:
    attrs = node.get("attributes") or []
    if isinstance(attrs, dict):
        items = attrs.items()
    elif isinstance(attrs, list):
        pairs = []
        for item in attrs:
            if isinstance(item, dict):
                pairs.extend(item.items())
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                pairs.append((item[0], item[1]))
        items = pairs
    else:
        items = []
    keep = {}
    for key, value in items:
        if str(key).lower() in {
            "aria-label",
            "title",
            "alt",
            "href",
            "value",
            "placeholder",
            "role",
            "checked",
            "selected",
        }:
            keep[str(key)] = value
    return _compact(keep, 500) if keep else ""


def _is_interactive_node(node: dict[str, Any]) -> bool:
    tag = str(node.get("tagName") or node.get("tag") or "").lower()
    role = str(node.get("role") or "").lower()
    attrs = str(node.get("attributes") or "").lower()
    return (
        tag in {"a", "button", "input", "select", "textarea", "option"}
        or role
        in {
            "button",
            "link",
            "textbox",
            "combobox",
            "checkbox",
            "radio",
            "tab",
            "menuitem",
            "option",
        }
        or "href" in attrs
        or "onclick" in attrs
    )


def _chromiumrl_node_line(node: dict[str, Any]) -> str:
    fields = [
        f"nodeId={_compact(node.get('nodeId'))}",
        f"tag={_compact(node.get('tagName') or node.get('tag'))}",
        f"role={_compact(node.get('role'))}",
        f"visible={bool(node.get('isVisible'))}",
        f"inViewport={bool(node.get('isInViewport'))}",
        f"text={_compact(_node_text(node), 700)}",
    ]
    attrs = _attributes_text(node)
    if attrs:
        fields.append(f"attrs={attrs}")
    bounds = node.get("bounds")
    if bounds:
        fields.append(f"bounds={_compact(bounds, 240)}")
    selector = node.get("cssSelector") or node.get("selector")
    if selector:
        fields.append(f"selector={_compact(selector, 300)}")
    return " ".join(fields)


def project_diff(
    diff: SemanticDOMDiff | dict[str, Any] | None, *, char_budget: int = 6000
) -> str:
    if diff is None:
        return "DIFF unavailable"
    if isinstance(diff, dict):
        return project_chromiumrl_diff(diff, char_budget=char_budget)
    header = (
        f"DIFF {diff.from_snapshot_id}->{diff.to_snapshot_id}; "
        f"added={len(diff.added)} removed={len(diff.removed)} "
        f"updated={len(diff.updated)} unchanged={diff.unchanged_count}\n"
    )
    lines: list[str] = []
    lines.extend(_node_line(node, "+ ") for node in sorted(diff.added, key=lambda n: str(n.get("key", ""))))
    lines.extend(_node_line(node, "- ") for node in sorted(diff.removed, key=lambda n: str(n.get("key", ""))))
    for update in sorted(diff.updated, key=lambda item: item.key):
        changes = ", ".join(
            f"{field}:{_compact(change['before'])}->{_compact(change['after'])}"
            for field, change in sorted(update.changes.items())
        )
        lines.append(f"~ key={update.key} {changes}")
    return _budget(header, lines, char_budget)


def project_chromiumrl_diff(diff: dict[str, Any], *, char_budget: int = 6000) -> str:
    result = diff.get("chromiumrl_result") or diff.get("chromiumrl_response") or {}
    patch = diff.get("local_patch") or diff.get("local_outer_html_diff") or ""
    header = (
        "DIFF schema=chromiumrl_compare\n"
        f"method={_compact(diff.get('method'))}; "
        f"reference={_compact(diff.get('reference'))}; "
        f"current={_compact(diff.get('current'))}; "
        f"timing={_compact(diff.get('timing'), 300)}\n"
    )
    lines: list[str] = []
    if isinstance(result, dict):
        for key, value in sorted(result.items()):
            lines.append(f"{key}={_compact(value, 900)}")
    if patch:
        lines.append("patch=" + _compact(patch, 2400))
    return _budget(header, lines, char_budget)


def project_frame_retrieved(
    frame: DOMEvidenceFrame,
    *,
    terms: list[str],
    frame_char_budget: int = 16000,
    before_state_char_budget: int = 2500,
    state_char_budget: int = 6000,
    diff_char_budget: int = 6500,
) -> str:
    """Project one frame using task/rubric/final-answer-aware retrieval.

    This is the first quality-improvement pass for DOM-only verification. It
    keeps the same action-aligned files, but ranks DOM/diff records by relevance
    before budgeting so important evidence is less likely to be truncated out.
    """
    before_page = _page_state_summary(frame.before_page_state)
    after_page = _page_state_summary(frame.after_page_state)
    header = (
        f"FRAME {frame.action_ordinal} action_id={frame.action_id or 'N/A'} "
        f"capture={frame.capture_status or 'unknown'} "
        f"declared_coverage={frame.coverage_status or _snapshot_coverage_status(frame.snapshot)}\n"
        f"verifier_action={_compact(frame.verifier_action, 900)}\n"
        f"before_page={before_page}\n"
        f"after_page={after_page}\n"
        f"retrieval_terms={_compact(terms[:80], 1400)}\n"
    )
    remaining = max(0, frame_char_budget - len(header))
    diff = project_retrieved_diff(
        frame.diff, terms=terms, char_budget=min(diff_char_budget, remaining)
    )
    remaining = max(0, remaining - len(diff) - 1)
    before_state = (
        project_retrieved_snapshot(
            frame.before_snapshot,
            terms=terms,
            char_budget=min(before_state_char_budget, remaining),
            label="BEFORE STATE",
        )
        if frame.before_snapshot is not None and remaining > 0
        else "BEFORE STATE unavailable"
    )
    remaining = max(0, remaining - len(before_state) - 1)
    after_state = project_retrieved_snapshot(
        frame.snapshot,
        terms=terms,
        char_budget=min(state_char_budget, remaining),
        label="AFTER STATE",
    )
    return (
        header
        + "RETRIEVED DIFF EVIDENCE:\n"
        + diff
        + "\n"
        + before_state
        + "\n"
        + after_state
    )[:frame_char_budget]


def _page_state_summary(page_state: dict[str, Any] | None) -> str:
    if not page_state:
        return "unavailable"
    viewport = page_state.get("viewport") or {}
    summary = {
        "url": page_state.get("url"),
        "title": page_state.get("title"),
        "readyState": page_state.get("readyState"),
        "viewport": {
            "innerWidth": viewport.get("innerWidth"),
            "innerHeight": viewport.get("innerHeight"),
            "scrollX": viewport.get("scrollX"),
            "scrollY": viewport.get("scrollY"),
            "scrollHeight": viewport.get("scrollHeight"),
        },
    }
    return _compact(summary, 900)


def project_retrieved_snapshot(
    snapshot: SemanticDOMSnapshot | dict[str, Any] | None,
    *,
    terms: list[str],
    char_budget: int = 6000,
    label: str = "STATE",
) -> str:
    if snapshot is None:
        return f"{label} unavailable"
    if isinstance(snapshot, SemanticDOMSnapshot):
        header = (
            f"{label} snapshot={snapshot.snapshot_id} ordinal={snapshot.ordinal}\n"
            f"url={_compact(snapshot.url, 500)}\n"
            f"title={_compact(snapshot.title, 500)}\n"
            f"{coverage_text(snapshot.coverage)}\n"
        )
        lines = [
            _node_line(node)
            for node in sorted(snapshot.nodes, key=lambda item: item.key)
        ]
        ranked = [
            (_line_relevance(line, terms), line)
            for line in lines
            if _line_relevance(line, terms) > 0
        ]
        return _budget(header + "RETRIEVED NODES:\n", _dedupe_ranked(ranked, max_lines=80), char_budget)

    return project_retrieved_chromiumrl_snapshot(
        snapshot, terms=terms, char_budget=char_budget, label=label
    )


def project_retrieved_chromiumrl_snapshot(
    snapshot: dict[str, Any],
    *,
    terms: list[str],
    char_budget: int = 6000,
    label: str = "STATE",
) -> str:
    nodes = snapshot.get("nodes") or []
    header = (
        f"{label} schema=chromiumrl_dom\n"
        f"url={_compact(snapshot.get('url'), 500)}\n"
        f"title={_compact(snapshot.get('title'), 500)}\n"
        f"viewport={_compact(snapshot.get('viewport'), 500)}\n"
        f"nodes={len(nodes)}\nRETRIEVED NODES:\n"
    )
    ranked: list[tuple[int, str]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        text = _node_text(node)
        attrs_text = _attributes_text(node)
        if _looks_noisy_dom_text(text) and not attrs_text:
            continue
        line = _chromiumrl_node_line(node)
        score = _line_relevance(line, terms)
        if bool(node.get("isInViewport")):
            score += 3
        if bool(node.get("isVisible")):
            score += 2
        if _is_interactive_node(node):
            score += 2
        if score > 0:
            ranked.append((score, line))
    return _budget(header, _dedupe_ranked(ranked, max_lines=100), char_budget)


def project_retrieved_diff(
    diff: SemanticDOMDiff | dict[str, Any] | None,
    *,
    terms: list[str],
    char_budget: int = 6500,
) -> str:
    if diff is None:
        return "DIFF unavailable"
    if isinstance(diff, SemanticDOMDiff):
        header = (
            f"DIFF {diff.from_snapshot_id}->{diff.to_snapshot_id}; "
            f"added={len(diff.added)} removed={len(diff.removed)} "
            f"updated={len(diff.updated)} unchanged={diff.unchanged_count}\n"
        )
        lines: list[str] = []
        lines.extend(_node_line(node, "+ ") for node in sorted(diff.added, key=lambda n: str(n.get("key", ""))))
        lines.extend(_node_line(node, "- ") for node in sorted(diff.removed, key=lambda n: str(n.get("key", ""))))
        for update in sorted(diff.updated, key=lambda item: item.key):
            changes = ", ".join(
                f"{field}:{_compact(change['before'])}->{_compact(change['after'])}"
                for field, change in sorted(update.changes.items())
            )
            lines.append(f"~ key={update.key} {changes}")
        ranked = [
            (_line_relevance(line, terms), line)
            for line in lines
            if _line_relevance(line, terms) > 0
        ]
        return _budget(header, _dedupe_ranked(ranked, max_lines=100), char_budget)

    return project_retrieved_chromiumrl_diff(
        diff, terms=terms, char_budget=char_budget
    )


def project_retrieved_chromiumrl_diff(
    diff: dict[str, Any], *, terms: list[str], char_budget: int = 6500
) -> str:
    result = diff.get("chromiumrl_result") or diff.get("chromiumrl_response") or {}
    header = (
        "DIFF schema=chromiumrl_compare retrieved=true\n"
        f"method={_compact(diff.get('method'))}; "
        f"reference={_compact(diff.get('reference'))}; "
        f"current={_compact(diff.get('current'))}; "
        f"summary={_compact(result.get('summary') if isinstance(result, dict) else None, 700)}; "
        f"timing={_compact(diff.get('timing'), 300)}\n"
    )
    ranked: list[tuple[int, str]] = []
    if isinstance(result, dict):
        for section in (
            "textChanges",
            "insertions",
            "attributeChanges",
            "deletions",
            "moves",
            "typeChanges",
            "layoutChanges",
            "styleChanges",
        ):
            entries = result.get(section)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                line = _diff_entry_line(section, entry)
                score = _line_relevance(line, terms)
                if section in {"textChanges", "insertions", "attributeChanges"}:
                    score += 2
                if score > 0:
                    ranked.append((score, line))
    patch = diff.get("local_patch") or diff.get("local_outer_html_diff") or ""
    if patch and not _looks_noisy_dom_text(patch):
        score = _line_relevance(str(patch), terms)
        if score > 0:
            ranked.append((score, "patch=" + _compact(patch, 1600)))
    return _budget(header, _dedupe_ranked(ranked, max_lines=120), char_budget)


def _diff_entry_line(section: str, entry: Any) -> str:
    if not isinstance(entry, dict):
        return f"{section}: {_compact(entry, 900)}"
    node_details = entry.get("nodeDetails") if isinstance(entry.get("nodeDetails"), dict) else {}
    text_values: list[str] = []
    for source in (entry, node_details):
        for key in (
            "textContent",
            "innerText",
            "ariaLabel",
            "accessibleName",
            "oldValue",
            "newValue",
            "fingerprint",
        ):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                text_values.append(value)
        attrs = source.get("attributes")
        if attrs:
            text_values.append(_attributes_text({"attributes": attrs}))
    text = " | ".join(
        value for value in (_compact(v, 700) for v in text_values) if value
    )
    return (
        f"{section}: nodeId={_compact(entry.get('nodeId'))} "
        f"tag={_compact(entry.get('tagName'))} "
        f"selector={_compact(entry.get('cssSelector') or entry.get('stablePath'), 350)} "
        f"text={text}"
    )


def project_frame(
    frame: DOMEvidenceFrame,
    *,
    frame_char_budget: int = 16000,
    before_state_char_budget: int = 4000,
    state_char_budget: int = 6000,
    diff_char_budget: int = 5000,
) -> str:
    header = (
        f"FRAME {frame.action_ordinal} action_id={frame.action_id or 'N/A'} "
        f"capture={frame.capture_status or 'unknown'} "
        f"declared_coverage={frame.coverage_status or _snapshot_coverage_status(frame.snapshot)}\n"
        f"verifier_action={_compact(frame.verifier_action, 600)}\n"
        f"before_page={_compact(frame.before_page_state, 700)}\n"
        f"after_page={_compact(frame.after_page_state, 700)}\n"
    )
    remaining = max(0, frame_char_budget - len(header))
    diff = project_diff(frame.diff, char_budget=min(diff_char_budget, remaining))
    remaining = max(0, remaining - len(diff) - 1)
    before_state = (
        project_snapshot(
            frame.before_snapshot,
            char_budget=min(before_state_char_budget, remaining),
        )
        if frame.before_snapshot is not None and remaining > 0
        else "BEFORE STATE unavailable"
    )
    remaining = max(0, remaining - len(before_state) - 1)
    after_state = project_snapshot(
        frame.snapshot, char_budget=min(state_char_budget, remaining)
    )
    return (
        header
        + diff
        + "\nBEFORE STATE:\n"
        + before_state
        + "\nAFTER STATE:\n"
        + after_state
    )[:frame_char_budget]


def _snapshot_coverage_status(snapshot: SemanticDOMSnapshot | dict[str, Any]) -> str:
    if isinstance(snapshot, SemanticDOMSnapshot):
        return snapshot.coverage.status
    return "chromiumrl_dom"


def project_frames(
    frames: Iterable[DOMEvidenceFrame],
    *,
    context_char_budget: int = 48000,
    frame_char_budget: int = 16000,
    top_k: int | None = None,
) -> list[str]:
    """Project chronological frames within per-frame and total context budgets."""
    ordered = sorted(frames, key=lambda frame: (frame.action_ordinal, frame.action_id))
    if top_k is not None:
        if top_k < 0:
            raise ValueError("top_k must be non-negative")
        ordered = ordered[:top_k]
    result: list[str] = []
    remaining = context_char_budget
    for frame in ordered:
        if remaining <= 0:
            break
        text = project_frame(
            frame, frame_char_budget=min(frame_char_budget, remaining)
        )
        result.append(text)
        remaining -= len(text)
    return result


def _budget(header: str, lines: list[str], char_budget: int) -> str:
    if char_budget <= 0:
        return ""
    if len(header) >= char_budget:
        return header[:char_budget]
    output = header
    omitted = 0
    for index, line in enumerate(lines):
        candidate = line + "\n"
        if len(output) + len(candidate) > char_budget:
            omitted = len(lines) - index
            break
        output += candidate
    if omitted:
        marker = f"… {omitted} record(s) omitted by projection budget"
        output = output[: max(0, char_budget - len(marker))] + marker
    return output[:char_budget]
