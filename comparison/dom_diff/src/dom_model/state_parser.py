"""Strict, lossless loader for root-level ``dom_model0..N.txt`` states."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .schemas import DomModelState, StateSection


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


def _parse_state(path: Path, index: int) -> DomModelState:
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


def discover_dom_model_files(root: str | Path) -> list[Path]:
    task_root = Path(root).resolve(strict=True)
    if not task_root.is_dir():
        raise ValueError(f"DOM-model task is not a directory: {task_root}")
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
    actual = sorted(indexed)
    expected = list(range(len(actual)))
    if not actual:
        raise ValueError(f"No dom_modelN.txt states found: {task_root}")
    if actual != expected:
        raise ValueError(f"DOM-model states must be contiguous from 0: expected {expected}, got {actual}")
    return [indexed[index] for index in actual]


def load_dom_model_states(root: str | Path, *, action_count: int | None = None) -> list[DomModelState]:
    paths = discover_dom_model_files(root)
    if action_count is not None and len(paths) != action_count + 1:
        raise ValueError(
            "N actions require exactly N+1 DOM-model states: "
            f"actions={action_count}, states={len(paths)}"
        )
    return [_parse_state(path, index) for index, path in enumerate(paths)]

