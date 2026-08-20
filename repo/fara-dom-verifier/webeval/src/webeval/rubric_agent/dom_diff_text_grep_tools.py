"""Read-only grep/range tools over immutable raw dom_diffN.txt files.

This module deliberately knows nothing about compact DOM projections. It
registers exact source files behind opaque IDs and returns only requested raw
ranges with FRAME/STEP/line provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RAW_DOM_DIFF_GREP_SCHEMA = "runner-dom-diff-text-grep/v1"
_DIFF_NAME_RE = re.compile(r"^dom_diff([1-9][0-9]*)\.txt$")


GREP_EVIDENCE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "grep_evidence",
        "description": (
            "Search exact raw DOM-diff text and return provenance-tagged "
            "matching ranges. Use literal mode unless a regex is necessary."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 300},
                "file_ids": {"type": "array", "items": {"type": "string"}},
                "mode": {"type": "string", "enum": ["literal", "regex"]},
                "case_sensitive": {"type": "boolean"},
                "context_before": {"type": "integer", "minimum": 0, "maximum": 5},
                "context_after": {"type": "integer", "minimum": 0, "maximum": 5},
                "match_offset": {"type": "integer", "minimum": 0},
                "max_matches": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": [
                "query",
                "file_ids",
                "mode",
                "case_sensitive",
                "context_before",
                "context_after",
                "match_offset",
                "max_matches",
            ],
            "additionalProperties": False,
        },
    },
}


READ_FILE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "Read an exact line range from one allowlisted raw DOM-diff file. "
            "Use continuation coordinates when a response is paginated."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
                "start_column": {"type": "integer", "minimum": 0},
            },
            "required": ["file_id", "start_line", "end_line", "start_column"],
            "additionalProperties": False,
        },
    },
}

TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (GREP_EVIDENCE_TOOL, READ_FILE_TOOL)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class RawDOMDiffFile:
    task_id: str
    frame_index: int
    action_ordinal: int
    action_id: str
    file_id: str
    path: Path
    filename: str
    source_sha256: str
    source_bytes: int
    line_count: int


@dataclass(frozen=True)
class RawDOMDiffFrame:
    """Metadata-only frame compatible with the shared DOM pipeline."""

    action_ordinal: int
    action_id: str
    file_id: str
    raw_text_path: str
    source_sha256: str
    source_bytes: int
    line_count: int
    diff: dict[str, Any]
    capture_status: str = "complete"
    coverage_status: str = "raw_text_tool_only"
    verifier_action: None = None
    before_page_state: None = None
    after_page_state: None = None
    before_snapshot: None = None
    snapshot: None = None


class RawEvidenceBundle:
    """Immutable registry mapping opaque IDs to exact raw source files."""

    def __init__(self, task_id: str, files: Sequence[RawDOMDiffFile]) -> None:
        if not files:
            raise ValueError("RawEvidenceBundle requires at least one file")
        self.task_id = str(task_id)
        self._files = tuple(files)
        self._by_id = {item.file_id: item for item in self._files}
        if len(self._by_id) != len(self._files):
            raise ValueError("Duplicate raw evidence file IDs")
        expected = list(range(len(self._files)))
        actual = [item.frame_index for item in self._files]
        if actual != expected:
            raise ValueError(f"FRAME indices must be contiguous: {actual}")

    @classmethod
    def from_dom_actions(
        cls, dom_actions: Sequence[Mapping[str, Any]], *, task_id: str | None = None
    ) -> "RawEvidenceBundle":
        files: list[RawDOMDiffFile] = []
        resolved_task_id = str(task_id or "")
        for frame_index, action in enumerate(dom_actions):
            ordinal = int(action.get("dom_action_ordinal") or action.get("id") or 0)
            expected_ordinal = frame_index + 1
            if ordinal != expected_ordinal:
                raise ValueError(
                    f"Raw DOM actions must be contiguous: expected STEP "
                    f"{expected_ordinal}, got {ordinal}"
                )
            path_text = str(action.get("dom_diff_text_path") or "")
            if not path_text:
                raise ValueError(f"STEP {ordinal} has no dom_diff_text_path")
            declared = Path(path_text)
            match = _DIFF_NAME_RE.fullmatch(declared.name)
            if match is None or int(match.group(1)) != ordinal:
                raise ValueError(
                    f"STEP {ordinal} must reference dom_diff{ordinal}.txt"
                )
            declared_parent = declared.parent.resolve(strict=True)
            path = declared.resolve(strict=True)
            if path.parent != declared_parent:
                raise ValueError(
                    f"Raw DOM evidence symlink escapes its task folder: {declared}"
                )
            if not path.is_file():
                raise ValueError(f"Raw DOM evidence is not a file: {path}")
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Raw DOM evidence must be UTF-8: {path}") from exc
            if not resolved_task_id:
                resolved_task_id = str(action.get("dom_task_id") or path.parent.name)
            lines = text.splitlines()
            line_count = len(lines) if lines else (1 if text else 0)
            files.append(
                RawDOMDiffFile(
                    task_id=resolved_task_id,
                    frame_index=frame_index,
                    action_ordinal=ordinal,
                    action_id=str(action.get("dom_action_id") or ordinal),
                    file_id=f"evidence_frame_{frame_index:04d}",
                    path=path,
                    filename=path.name,
                    source_sha256=_sha256(raw),
                    source_bytes=len(raw),
                    line_count=line_count,
                )
            )
        return cls(resolved_task_id, files)

    @property
    def files(self) -> tuple[RawDOMDiffFile, ...]:
        return self._files

    @property
    def file_ids(self) -> tuple[str, ...]:
        return tuple(item.file_id for item in self._files)

    def entry(self, file_id: str) -> RawDOMDiffFile:
        try:
            return self._by_id[str(file_id)]
        except KeyError as exc:
            raise ValueError(f"Unknown evidence file_id {file_id!r}") from exc

    def frames(self) -> list[RawDOMDiffFrame]:
        return [
            RawDOMDiffFrame(
                action_ordinal=item.action_ordinal,
                action_id=item.action_id,
                file_id=item.file_id,
                raw_text_path=str(item.path),
                source_sha256=item.source_sha256,
                source_bytes=item.source_bytes,
                line_count=item.line_count,
                diff={},
            )
            for item in self._files
        ]

    def manifest(self, file_ids: Iterable[str] | None = None) -> str:
        ids = self.file_ids if file_ids is None else tuple(file_ids)
        lines: list[str] = []
        for file_id in ids:
            item = self.entry(file_id)
            lines.append(
                f"FRAME {item.frame_index} | STEP {item.action_ordinal} | "
                f"file_id={item.file_id} | file={item.filename} | "
                f"lines={item.line_count}"
            )
        return "\n".join(lines)

    def audit_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "task_id": item.task_id,
                "frame_index": item.frame_index,
                "action_ordinal": item.action_ordinal,
                "action_id": item.action_id,
                "file_id": item.file_id,
                "filename": item.filename,
                "canonical_path": str(item.path),
                "source_sha256": item.source_sha256,
                "source_bytes": item.source_bytes,
                "line_count": item.line_count,
            }
            for item in self._files
        ]

    def read_verified(self, file_id: str) -> tuple[RawDOMDiffFile, str]:
        item = self.entry(file_id)
        raw = item.path.read_bytes()
        current_hash = _sha256(raw)
        if current_hash != item.source_sha256:
            raise RuntimeError(
                f"Raw evidence changed after registration: {item.filename}; "
                f"expected {item.source_sha256}, got {current_hash}"
            )
        try:
            return item, raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(
                f"Raw evidence stopped being valid UTF-8: {item.filename}"
            ) from exc


class GrepEvidenceExecutor:
    """Execute only the two approved tools within a stage-scoped allowlist."""

    def __init__(
        self,
        bundle: RawEvidenceBundle,
        *,
        allowed_file_ids: Iterable[str] | None = None,
        max_result_chars: int = 8000,
        max_matches: int = 100,
        regex_timeout_seconds: float = 2.0,
    ) -> None:
        self.bundle = bundle
        requested = (
            bundle.file_ids if allowed_file_ids is None else tuple(allowed_file_ids)
        )
        unknown = [file_id for file_id in requested if file_id not in bundle.file_ids]
        if unknown:
            raise ValueError(f"Unknown stage file IDs: {unknown}")
        self.allowed_file_ids = tuple(requested)
        self._allowed = set(self.allowed_file_ids)
        if max_result_chars <= 0 or max_matches <= 0 or regex_timeout_seconds <= 0:
            raise ValueError("Tool limits must be positive")
        self.max_result_chars = int(max_result_chars)
        self.max_matches = min(100, int(max_matches))
        self.regex_timeout_seconds = float(regex_timeout_seconds)
        self.frames_returned: set[int] = set()
        self.ranges_returned: list[dict[str, Any]] = []

    def _select_ids(self, requested: Sequence[str]) -> tuple[str, ...]:
        ids = (
            self.allowed_file_ids
            if not requested
            else tuple(str(value) for value in requested)
        )
        denied = [file_id for file_id in ids if file_id not in self._allowed]
        if denied:
            raise ValueError(
                f"file_ids are not allowed in this stage: {sorted(set(denied))}"
            )
        return ids

    @staticmethod
    def _lines(text: str) -> list[str]:
        lines = text.splitlines()
        return lines if lines else ([text] if text else [])

    def _matching_lines(
        self,
        item: RawDOMDiffFile,
        text: str,
        *,
        query: str,
        mode: str,
        case_sensitive: bool,
    ) -> list[int]:
        if mode == "literal":
            needle = query if case_sensitive else query.casefold()
            return [
                index
                for index, line in enumerate(self._lines(text), start=1)
                if needle in (line if case_sensitive else line.casefold())
            ]
        if mode != "regex":
            raise ValueError("mode must be literal or regex")
        flags = ["--json", "--line-number", "--max-columns", "0", "--regexp", query]
        if not case_sensitive:
            flags.insert(0, "--ignore-case")
        try:
            completed = subprocess.run(
                ["rg", *flags, "--", str(item.path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.regex_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("regex search exceeded the configured timeout") from exc
        if completed.returncode not in (0, 1):
            detail = (completed.stderr or "invalid regex").strip()
            raise ValueError(f"regex search failed: {detail[:300]}")
        matches: list[int] = []
        for line in completed.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "match":
                continue
            number = (event.get("data") or {}).get("line_number")
            if isinstance(number, int):
                matches.append(number)
        return matches

    def execute(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            if name == "grep_evidence":
                return self.grep_evidence(**dict(arguments))
            if name == "read_file":
                return self.read_file(**dict(arguments))
            raise ValueError(f"Unsupported evidence tool {name!r}")
        except Exception as exc:
            return {
                "ok": False,
                "tool": str(name),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "complete": False,
            }

    def grep_evidence(
        self,
        *,
        query: str,
        file_ids: Sequence[str],
        mode: str,
        case_sensitive: bool,
        context_before: int,
        context_after: int,
        match_offset: int,
        max_matches: int,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query or len(query) > 300:
            raise ValueError("query must contain 1..300 characters")
        if not 0 <= int(context_before) <= 5 or not 0 <= int(context_after) <= 5:
            raise ValueError("context_before/context_after must be in [0,5]")
        if int(match_offset) < 0:
            raise ValueError("match_offset must be non-negative")
        call_limit = min(self.max_matches, int(max_matches))
        if call_limit <= 0:
            raise ValueError("max_matches must be positive")
        ids = self._select_ids(file_ids)
        all_matches: list[tuple[RawDOMDiffFile, int, list[str]]] = []
        hashes: dict[str, str] = {}
        for file_id in ids:
            item, text = self.bundle.read_verified(file_id)
            hashes[file_id] = item.source_sha256
            lines = self._lines(text)
            for line_number in self._matching_lines(
                item,
                text,
                query=query,
                mode=str(mode),
                case_sensitive=bool(case_sensitive),
            ):
                start = max(1, line_number - int(context_before))
                end = min(len(lines), line_number + int(context_after))
                all_matches.append((item, line_number, lines[start - 1 : end]))
        total = len(all_matches)
        start_offset = int(match_offset)
        selected = all_matches[start_offset : start_offset + call_limit]
        rendered: list[dict[str, Any]] = []
        used_chars = 0
        budget_limited = False
        for item, matched_line, context_lines in selected:
            line_start = max(1, matched_line - int(context_before))
            line_end = line_start + len(context_lines) - 1
            text_value = "\n".join(context_lines)
            base: dict[str, Any] = {
                "file_id": item.file_id,
                "frame": item.frame_index,
                "step": item.action_ordinal,
                "file": item.filename,
                "matched_line": matched_line,
                "line_start": line_start,
                "line_end": line_end,
                "source_sha256": item.source_sha256,
            }
            allowance = self.max_result_chars - used_chars
            if allowance <= 0:
                budget_limited = True
                break
            if len(text_value) > allowance:
                if rendered:
                    budget_limited = True
                    break
                matched_text = self._lines(
                    self.bundle.read_verified(item.file_id)[1]
                )[matched_line - 1]
                text_value = matched_text[:allowance]
                line_start = line_end = matched_line
                base.update(
                    line_start=matched_line,
                    line_end=matched_line,
                    column_start=0,
                    column_end=len(text_value),
                    excerpt_complete=len(text_value) == len(matched_text),
                )
                budget_limited = len(text_value) < len(matched_text)
            else:
                base["excerpt_complete"] = True
            base["text"] = text_value
            rendered.append(base)
            used_chars += len(text_value)
            self.frames_returned.add(item.frame_index)
            self.ranges_returned.append(
                {
                    "frame": item.frame_index,
                    "step": item.action_ordinal,
                    "file_id": item.file_id,
                    "line_start": line_start,
                    "line_end": line_end,
                    "column_start": int(base.get("column_start", 0)),
                    "column_end": base.get("column_end"),
                    "tool": "grep_evidence",
                }
            )
            if budget_limited:
                break
        consumed = len(rendered)
        next_offset = start_offset + consumed
        complete = not budget_limited and next_offset >= total
        return {
            "ok": True,
            "tool": "grep_evidence",
            "query": query,
            "mode": mode,
            "case_sensitive": bool(case_sensitive),
            "searched_file_ids": list(ids),
            "source_hashes": hashes,
            "matches_total": total,
            "matches_returned": consumed,
            "match_offset": start_offset,
            "next_match_offset": None if complete else next_offset,
            "complete": complete,
            "omission_reason": (
                None
                if complete
                else "result_character_limit"
                if budget_limited
                else "match_page_limit"
            ),
            "matches": rendered,
        }

    def read_file(
        self,
        *,
        file_id: str,
        start_line: int,
        end_line: int,
        start_column: int,
    ) -> dict[str, Any]:
        if file_id not in self._allowed:
            raise ValueError(f"file_id is not allowed in this stage: {file_id!r}")
        start_line = int(start_line)
        end_line = int(end_line)
        start_column = int(start_column)
        if start_line < 1 or end_line < start_line:
            raise ValueError("Require 1 <= start_line <= end_line")
        if start_column < 0:
            raise ValueError("start_column must be non-negative")
        item, text = self.bundle.read_verified(file_id)
        lines = self._lines(text)
        if start_line > len(lines):
            raise ValueError(
                f"start_line {start_line} exceeds file line count {len(lines)}"
            )
        requested_end = min(end_line, len(lines))
        segments: list[dict[str, Any]] = []
        used = 0
        continuation: dict[str, int] | None = None
        for line_number in range(start_line, requested_end + 1):
            line = lines[line_number - 1]
            column = start_column if line_number == start_line else 0
            if column > len(line):
                raise ValueError(
                    f"start_column {column} exceeds line {line_number} length {len(line)}"
                )
            remaining = self.max_result_chars - used
            if remaining <= 0:
                continuation = {"start_line": line_number, "start_column": column}
                break
            available = line[column:]
            if len(available) > remaining:
                piece = available[:remaining]
                segments.append(
                    {
                        "line": line_number,
                        "column_start": column,
                        "column_end": column + len(piece),
                        "text": piece,
                        "complete_line": False,
                    }
                )
                used += len(piece)
                continuation = {
                    "start_line": line_number,
                    "start_column": column + len(piece),
                }
                break
            segments.append(
                {
                    "line": line_number,
                    "column_start": column,
                    "column_end": len(line),
                    "text": available,
                    "complete_line": True,
                }
            )
            used += len(available)
        complete = continuation is None
        if segments:
            self.frames_returned.add(item.frame_index)
            self.ranges_returned.append(
                {
                    "frame": item.frame_index,
                    "step": item.action_ordinal,
                    "file_id": item.file_id,
                    "line_start": segments[0]["line"],
                    "line_end": segments[-1]["line"],
                    "column_start": segments[0]["column_start"],
                    "column_end": segments[-1]["column_end"],
                    "tool": "read_file",
                }
            )
        return {
            "ok": True,
            "tool": "read_file",
            "file_id": item.file_id,
            "frame": item.frame_index,
            "step": item.action_ordinal,
            "file": item.filename,
            "source_sha256": item.source_sha256,
            "requested": {
                "start_line": start_line,
                "end_line": end_line,
                "start_column": start_column,
            },
            "line_count": len(lines),
            "segments": segments,
            "complete": complete,
            "eof": complete and requested_end == len(lines),
            "continuation": continuation,
            "omission_reason": None if complete else "result_character_limit",
        }

    def execute_json(self, name: str, arguments: Mapping[str, Any]) -> str:
        return _json_text(self.execute(name, arguments))

    def coverage_receipt(self) -> dict[str, Any]:
        return {
            "allowed_file_ids": list(self.allowed_file_ids),
            "frames_returned": sorted(self.frames_returned),
            "ranges_returned": list(self.ranges_returned),
        }


def assert_no_raw_evidence_in_initial_payload(
    payload: Any, bundle: RawEvidenceBundle, *, sentinels: Sequence[str] = ()
) -> None:
    """Fail if an initial API payload contains a file-input or raw sentinel."""

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    forbidden_markers = (
        '"type": "input_file"',
        '"file_data":',
        '"file_url":',
        "data:text/plain;base64,",
    )
    found = [marker for marker in forbidden_markers if marker in serialized]
    if found:
        raise AssertionError(f"Initial payload contains forbidden file input: {found}")
    for item in bundle.files:
        if str(item.path) in serialized:
            raise AssertionError(
                f"Initial payload exposes canonical evidence path: {item.path}"
            )
    for sentinel in sentinels:
        if sentinel and sentinel in serialized:
            raise AssertionError(
                f"Initial payload contains raw evidence sentinel: {sentinel!r}"
            )
