"""Immutable records for parsed DOM-model states and alignment receipts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
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

    def model_text(self, *, action_count: int) -> str:
        if self.index == 0:
            phase = "initial browser state (before action 1)"
        elif self.index == action_count:
            phase = f"final browser state (after action {action_count})"
        else:
            phase = f"browser state after action {self.index}"
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
        value["path"] = str(self.path)
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

