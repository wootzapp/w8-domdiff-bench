from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


EvidenceStatus = Literal["supported", "contradicted", "partial", "unknown"]


@dataclass(frozen=True)
class AriaNode:
    raw_reference: str
    semantic_key: str
    depth: int
    role: str
    accessible_name: str
    text: str
    states: tuple[str, ...]
    parent_context: tuple[str, ...]
    source_line: str

    def searchable_text(self) -> str:
        return " ".join(
            part
            for part in (
                self.role,
                self.accessible_name,
                self.text,
                " ".join(self.states),
                " ".join(self.parent_context),
            )
            if part
        )


@dataclass(frozen=True)
class PageState:
    url: str
    title: str
    ready_state: str
    scroll_x: float
    scroll_y: float
    viewport_width: float
    viewport_height: float
    device_pixel_ratio: float
    body_text_preview: str


@dataclass(frozen=True)
class SemanticState:
    ordinal: int
    page: PageState
    nodes: tuple[AriaNode, ...]
    raw_unparsed_lines: tuple[str, ...] = ()
    capture_status: str = "complete"
    coverage: str = "stagehand_aria"
    synthetic: bool = False


@dataclass(frozen=True)
class ActionRecord:
    ordinal: int
    action_id: str
    name: str
    arguments: dict[str, Any]
    url: str
    tool_result: dict[str, Any]
    source_path: str


@dataclass(frozen=True)
class NodeChange:
    kind: Literal["added", "removed", "updated"]
    semantic_key: str
    raw_reference_before: str = ""
    raw_reference_after: str = ""
    before: str = ""
    after: str = ""


@dataclass(frozen=True)
class SemanticDiff:
    node_changes: tuple[NodeChange, ...]
    url_before: str
    url_after: str
    title_before: str
    title_after: str
    scroll_before: tuple[float, float]
    scroll_after: tuple[float, float]

    def has_changes(self) -> bool:
        return bool(
            self.node_changes
            or self.url_before != self.url_after
            or self.title_before != self.title_after
            or self.scroll_before != self.scroll_after
        )


@dataclass(frozen=True)
class TransitionFrame:
    action: ActionRecord
    before: SemanticState
    after: SemanticState
    diff: SemanticDiff


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    instruction: str
    init_url: str
    precomputed_rubric: dict[str, Any] | None = None


@dataclass(frozen=True)
class StagehandTrajectory:
    path: Path
    task: TaskDefinition
    final_answer: str
    is_aborted: bool
    solver_token_usage: dict[str, Any]
    actions: tuple[ActionRecord, ...]
    frames: tuple[TransitionFrame, ...]
    terminal_state: SemanticState
    manifest: dict[str, Any]


@dataclass(frozen=True)
class EvidenceLink:
    evidence_kind: Literal["transition", "terminal_state"]
    state_ordinal: int
    step: int | None
    action_id: str | None
    action_name: str | None
    before_url: str | None
    after_url: str
    node_identifiers: tuple[str, ...]
    source_paths: tuple[str, ...]


@dataclass(frozen=True)
class SelectedEvidence:
    criterion_index: int
    frame_index: int | None
    relevance_score: float
    projection: str
    link: EvidenceLink


@dataclass(frozen=True)
class DeterministicDecision:
    applicable: bool
    status: EvidenceStatus = "unknown"
    earned_points: float = 0.0
    explanation: str = ""
    links: tuple[EvidenceLink, ...] = ()


@dataclass
class UsageRecord:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class VerifierConfig:
    judge_model: str = "gpt-5.2"
    action_rubric_model: str = "o4-mini"
    rubric_threshold: float = 0.8
    max_evidence_per_criterion: int = 5
    min_relevance_score: float = 1.0
    frame_char_budget: int = 16_000
    criterion_context_char_budget: int = 48_000
    global_timeline_char_budget: int = 12_000
    majority_vote_instances: int = 1
    max_retries: int = 5
    timeout_seconds: float = 180.0
    success_criterion: Literal["process", "outcome", "both"] = "outcome"
    redo_eval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreflightResult:
    task_id: str
    action_count: int
    state_count: int
    transition_count: int
    terminal_state_present: bool
    synthetic_initial_state: bool
    alignment_complete: bool
    missing_artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

