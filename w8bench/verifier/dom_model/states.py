"""DOM state records, lossless loading, and record-boundary context packing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any



@dataclass(frozen=True)
class StateSection:
    heading: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class DomModelState:
    index: int
    path: Path
    raw_text: str
    sha256: str
    byte_count: int
    line_count: int
    estimated_tokens: int
    url: str = ""
    title: str = ""
    source_truncated: bool = False
    sections: tuple[StateSection, ...] = ()
    control_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def provenance(self) -> str:
        return f"m{self.index}:L1-L{self.line_count}"

    def model_text(self, *, action_count: int, initial_state_index: int = 0) -> str:
        ordinal = self.index - initial_state_index
        if ordinal == 0:
            phase = "initial browser state (before action 1)"
        elif ordinal == action_count:
            phase = f"final browser state (after action {action_count})"
        else:
            phase = f"browser state after action {ordinal}"
        return (
            f"DOM_MODEL_STATE_INDEX: {self.index}\n"
            f"DOM_MODEL_PHASE: {phase}\n"
            f"DOM_MODEL_PROVENANCE: {self.provenance}\n"
            f"DOM_MODEL_SHA256: {self.sha256}\n"
            "DOM_MODEL_LIMITATION: This is structured textual browser evidence, not pixels. "
            "Do not infer pixel-only appearance. Missing content is unproven, especially when "
            "the source declares truncation.\n\n"
            f"{self.raw_text}"
        )

    def audit_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("raw_text")
        value["path"] = os.path.relpath(self.path, Path(__file__).resolve().parents[3])
        value["sections"] = [asdict(section) for section in self.sections]
        value["provenance"] = self.provenance
        return value


@dataclass(frozen=True)
class AlignmentWarning:
    code: str
    message: str
    action_ordinal: int | None = None
    state_index: int | None = None


@dataclass(frozen=True)
class AlignmentReceipt:
    task_id: str
    action_count: int
    state_count: int
    initial_state: int
    final_state: int
    actions: tuple[dict[str, Any], ...]
    transitions: tuple[dict[str, Any], ...]
    warnings: tuple[AlignmentWarning, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DOM_MODEL_RE = re.compile(r"^dom_model(0|[1-9]\d*)\.txt$")


HEADING_RE = re.compile(r"^===\s*(.*?)\s*===$")


REF_RE = re.compile(r"(?:\bref\s*[=:]\s*|\[)([A-Za-z0-9_.:-]+)(?:\]|\b)", re.I)


def _header(lines: list[str], name: str) -> str:
    prefix = f"{name}:"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _sections(lines: list[str]) -> tuple[StateSection, ...]:
    starts: list[tuple[str, int]] = []
    for line_number, line in enumerate(lines, start=1):
        match = HEADING_RE.fullmatch(line.strip())
        if match:
            starts.append((match.group(1), line_number))
    sections: list[StateSection] = []
    for pos, (heading, start) in enumerate(starts):
        end = starts[pos + 1][1] - 1 if pos + 1 < len(starts) else len(lines)
        sections.append(StateSection(heading=heading, start_line=start, end_line=end))
    return tuple(sections)


def _read_state_text(path: Path) -> tuple[bytes, str]:
    if path.is_symlink():
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(path.parent.resolve(strict=True))
        except ValueError as exc:
            raise ValueError(f"DOM-model symlink escapes task root: {path}") from exc
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"DOM-model state is empty: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"DOM-model state is not UTF-8: {path}: {exc}") from exc
    if not text.strip():
        raise ValueError(f"DOM-model state has no non-whitespace content: {path}")
    return raw, text


def _parse_state(path: Path, index: int) -> DomModelState:
    raw, text = _read_state_text(path)
    lines = text.splitlines()
    url = _header(lines, "URL")
    title = _header(lines, "Title")
    snapshot = _header(lines, "Snapshot").casefold()
    source_truncated = bool(re.search(r"\btruncated\s*[=:]\s*(true|1|yes)\b", snapshot))
    refs = tuple(dict.fromkeys(match.group(1) for match in REF_RE.finditer(text)))
    warnings: list[str] = []
    if not url:
        warnings.append("missing_url")
    if not title:
        warnings.append("missing_title")
    if source_truncated:
        warnings.append("source_declares_truncation")
    return DomModelState(
        index=index,
        path=path.resolve(strict=True),
        raw_text=text,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_count=len(raw),
        line_count=len(lines),
        estimated_tokens=(len(text) + 3) // 4,
        url=url,
        title=title,
        source_truncated=source_truncated,
        sections=_sections(lines),
        control_refs=refs,
        warnings=tuple(warnings),
    )


def _evaluation_context(task_path: Path) -> dict[str, Any]:
    context = {}
    if task_path.is_file():
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task = task[0] if isinstance(task, list) else task
        context = task.get("evaluation_context") or {}
    return context


def _indexed_state_files(task_root: Path) -> dict[int, Path]:
    indexed: dict[int, Path] = {}
    malformed: list[str] = []
    for child in task_root.iterdir():
        if not child.name.startswith("dom_model"):
            continue
        if not child.is_file():
            malformed.append(child.name)
            continue
        match = DOM_MODEL_RE.fullmatch(child.name)
        if match is None:
            malformed.append(child.name)
            continue
        index = int(match.group(1))
        if index in indexed:
            raise ValueError(f"Duplicate DOM-model state index {index}: {task_root}")
        indexed[index] = child
    if malformed:
        raise ValueError(f"Malformed DOM-model filenames: {sorted(malformed)}")
    return indexed


def discover_dom_model_files(root: str | Path) -> list[Path]:
    task_root = Path(root).resolve(strict=True)
    if not task_root.is_dir():
        raise ValueError(f"DOM-model task is not a directory: {task_root}")
    indexed = _indexed_state_files(task_root)
    actual = sorted(indexed)
    context = _evaluation_context(task_root / "task_data.json")
    expected = list(range(len(actual)))
    if context:
        expected_ids = context["expected_state_ids"]
        gaps = context.get("format_gaps", {}).get("dom_model", [])
        if len(expected_ids) != len(set(expected_ids)) or not set(gaps) <= set(expected_ids):
            raise ValueError("Invalid DOM-model state identity/gap receipt")
        expected = [index for index in expected_ids if index not in gaps]
    if not actual and not context:
        raise ValueError(f"No dom_modelN.txt states found: {task_root}")
    if actual != expected:
        raise ValueError(f"DOM-model states must be contiguous from 0: expected {expected}, got {actual}")
    return [indexed[index] for index in actual]


def load_dom_model_states(root: str | Path, *, action_count: int | None = None) -> list[DomModelState]:
    paths = discover_dom_model_files(root)
    context = _evaluation_context(Path(root) / "task_data.json")
    count = len(context["expected_state_ids"]) if context else len(paths)
    if action_count is not None and count != action_count + 1:
        raise ValueError(
            "N actions require exactly N+1 DOM-model states: "
            f"actions={action_count}, states={len(paths)}"
        )
    return [_parse_state(path, int(DOM_MODEL_RE.fullmatch(path.name).group(1))) for path in paths]


MANDATORY = re.compile(
    r"^(?:URL|Title|Snapshot):|\b(?:dialog|alert|error|validation|truncat(?:ed|ion))\b",
    re.I | re.M,
)


def _state_records(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines(keepends=True)
    blocks: list[tuple[int, int, str]] = []
    current_start = 1
    current: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        begins_record = bool(line.strip()) and (
            not line[:1].isspace() or line.lstrip().startswith(("- ", "* ", "|"))
        )
        if begins_record and current:
            blocks.append((current_start, line_number - 1, "".join(current)))
            current = []
            current_start = line_number
        current.append(line)
    if current:
        blocks.append((current_start, len(lines), "".join(current)))

    return blocks


def _select_state_records(
    blocks: list[tuple[int, int, str]], *, prefix_chars: int, max_chars: int
) -> set[int]:
    selected = {
        index for index, (_, _, block) in enumerate(blocks) if MANDATORY.search(block)
    }
    used = prefix_chars + sum(len(blocks[index][2]) for index in selected)
    for index, (_, _, block) in enumerate(blocks):
        if index not in selected and used + len(block) <= max_chars:
            selected.add(index)
            used += len(block)
    return selected


def pack_state(
    state: DomModelState, *, action_count: int, max_chars: int, initial_state_index: int = 0
) -> tuple[str, list[dict[str, Any]]]:
    """Pack source-ordered records, never silently dropping a partial record."""
    complete = state.model_text(action_count=action_count, initial_state_index=initial_state_index)
    if max_chars <= 0 or len(complete) <= max_chars:
        return complete, []
    prefix, _ = complete.split("\n\n", 1)
    prefix += "\n\n"
    blocks = _state_records(state.raw_text)
    selected = _select_state_records(blocks, prefix_chars=len(prefix), max_chars=max_chars)
    omissions = [
        {
            "state_index": state.index,
            "start_line": start,
            "end_line": end,
            "provenance": f"m{state.index}:L{start}-L{end}",
            "char_count": len(block),
            "estimated_tokens": (len(block) + 3) // 4,
            "reason": "state_exceeds_context_budget",
        }
        for index, (start, end, block) in enumerate(blocks)
        if index not in selected
    ]
    rendered = prefix + "".join(
        block for index, (_, _, block) in enumerate(blocks) if index in selected
    )
    rendered += (
        "\nDOM_MODEL_CONTEXT_OMISSIONS: "
        + json.dumps(omissions, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )
    return rendered, omissions
