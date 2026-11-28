"""DOM task, solver event and trajectory records."""

import os
from dataclasses import dataclass, field
from typing import Annotated, Any, ClassVar, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field

from ..trajectory import (
    FinalAnswer as _FinalAnswer,
    Trajectory as _Trajectory,
    load_final_answer,
)

from ..models import (
    Action,
    AgentState,
    Component,
    DataPointMetadata,
    LLMConversation,
    LLMMessage,
    LLMUsage,
    MMRubricOutcomeResult,
    MMRubricResult,
    MajorityVoteMetadata,
    Observation,
    ObservationsPost,
    ObservationsPre,
    Outcome,
    SolverConfig,
    SolverLogBase,
    SolverStatus,
    Step,
    TaskAgentResult,
    ToolOutput,
    TrajectoryDiagnosticsResult,
    UserMessage,
    UserMessageType,
    VerificationResult,
    VerifierConfig,
    earliest,
    get_observations,
    latest,
)

class ComputerObservation(Observation):
    """Observation from the browser environment."""

    observation_type: Literal["environment"] = "environment"
    evidence_path: str = ""
    url: str = ""
    page_info: str = ""


ObservationEvent = Annotated[
    Union[ComputerObservation, ToolOutput, UserMessage],
    Field(discriminator="observation_type"),
]


Event = Annotated[
    Union[ObservationEvent, Action],
    Field(discriminator="type"),
]


class StepSummary(BaseModel):
    """Per-step structured data extracted from SolverLog.steps."""

    index: int
    action_name: str = ""
    action_args: Dict[str, Any] = Field(default_factory=dict)
    action_nl_description: str = ""
    action_content: Dict[str, Any] = Field(default_factory=dict)
    url: str = ""
    state_description: str = ""
    previous_error: str = ""
    evidence_path: str = ""
    user_messages_before: List[Tuple[UserMessageType, str]] = Field(
        default_factory=list
    )


class Task(Component):
    """Defines a task for the agent to solve."""

    task_id: str
    instruction: str
    environment_config: Dict[str, Any] = Field(default_factory=dict)
    solver: SolverConfig = Field(default_factory=SolverConfig)
    verifier: VerifierConfig = Field(default_factory=VerifierConfig)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SolverLog(SolverLogBase):
    """Solver output containing the sequence of observation-action steps."""

    events: List[Event] = Field(default_factory=list)
    _observation_type: ClassVar[type] = ComputerObservation
    _summary_type: ClassVar[type] = StepSummary
    _evidence_field: ClassVar[str] = 'evidence_path'


VerificationResultEvent = Annotated[
    Union[
        MMRubricResult,
        MMRubricOutcomeResult,
        TrajectoryDiagnosticsResult,
        TaskAgentResult,
        VerificationResult,
    ],
    Field(discriminator="result_type"),
]


class DataPoint(Component):
    """A single data generation run output."""

    task: Task
    solver_log: SolverLog = Field(default_factory=SolverLog)
    verification: Dict[str, VerificationResultEvent] = Field(default_factory=dict)
    metadata: DataPointMetadata = Field(default_factory=DataPointMetadata)


@dataclass
class FinalAnswer(_FinalAnswer):
    __module__ = __package__ + '.trajectory'
    final_answer: str = '<no_answer>'
    env_state_json: str = '<no_answer>'
    env_state_raw: str = '<no_answer>'
    is_aborted: bool = False
    is_rel_paths: bool = True
    token_usage: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @staticmethod
    def load(path: os.PathLike):
        return load_final_answer(path, FinalAnswer)


class Trajectory(_Trajectory):
    __module__ = __package__ + '.trajectory'
    _answer_type = FinalAnswer
    _has_screenshots = False

    @staticmethod
    def from_folder(path, skip_web_surfer_log=False):
        try:
            return Trajectory(path, skip_web_surfer_log=skip_web_surfer_log)
        except Exception:
            return None

    def __repr__(self):
        return f'Trajectory("{self.path.name}: {len(self.actions)} actions")'
