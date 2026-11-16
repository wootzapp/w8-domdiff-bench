"""Task events, verification results and agent configuration."""

from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)
from datetime import datetime
from enum import Enum
import json
import os
import uuid
from pydantic import BaseModel, ConfigDict, Field, model_validator
from abc import ABC


class Component(BaseModel):
    """Base class providing serialization/deserialization via pydantic."""

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="python")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Component":
        return cls.model_validate(data)

    def save(self, path: os.PathLike) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: os.PathLike) -> "Component":
        with open(path, "r") as f:
            return cls.from_dict(json.load(f))


class SolverStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    ABORTED = "aborted"
    WAITING_FOR_USER = "waiting_for_user"


class LLMUsage(Component):
    """Token usage from an LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0


class LLMMessage(Component):
    """A single LLM call: request/response pair."""

    raw_response: str = ""
    reasoning: str = ""
    finish_reason: str = ""
    usage: LLMUsage = Field(default_factory=LLMUsage)


class LLMConversation(Component):
    """A sequence of LLM calls."""

    messages: List[LLMMessage] = Field(default_factory=list)

    @property
    def usage(self) -> LLMUsage:
        return LLMUsage(
            prompt_tokens=sum(m.usage.prompt_tokens for m in self.messages),
            completion_tokens=sum(m.usage.completion_tokens for m in self.messages),
            reasoning_tokens=sum(m.usage.reasoning_tokens for m in self.messages),
        )


class Outcome(Component):
    """Result of solving a task."""

    answer: str = ""


class Observation(Component):
    """Base class for things the agent observes."""

    type: Literal["observation"] = "observation"
    id: Optional[str] = None
    observation_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None
    action_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _set_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("id") is None:
                data["id"] = uuid.uuid4().hex
            if data.get("timestamp") is None:
                data["timestamp"] = datetime.now().isoformat()
        return data


class ToolOutput(Observation):
    """Output from a tool/environment action."""

    observation_type: Literal["tool_output"] = "tool_output"
    output: str = ""
    error: str = ""


class UserMessageType(str, Enum):
    """Type of user message."""

    TASK = "task"
    FOLLOWUP_TASK = "followup_task"
    CRITICAL_POINT_RESPONSE = "critical_point_response"


class UserMessage(Observation):
    """A user message observation."""

    observation_type: Literal["user_message"] = "user_message"
    content: str = ""
    message_type: UserMessageType = UserMessageType.TASK


class AgentState(Component):
    """Snapshot of agent's internal state at decision time."""

    agent: str = ""
    tools_available: List[str] = Field(default_factory=list)
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)


class Action(Component):
    """The agent's decision and action."""

    type: Literal["action"] = "action"
    id: Optional[str] = None
    timestamp: Optional[str] = None

    action_name: str = ""
    agent_state: AgentState = Field(default_factory=AgentState)
    llm_conversation: LLMConversation = Field(default_factory=LLMConversation)

    content: Dict[str, Any] = Field(default_factory=dict)
    action_nl_description: str = ""

    grounding: Optional[LLMConversation] = None

    @model_validator(mode="before")
    @classmethod
    def _set_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("id") is None:
                data["id"] = uuid.uuid4().hex
            if data.get("timestamp") is None:
                data["timestamp"] = datetime.now().isoformat()
        return data


_O = TypeVar("_O", bound=Observation)


def get_observations(events: Iterable[Observation | Action], observation_type: Type[_O]) -> List[_O]:
    """Return observations of a specific type from an event stream."""
    return [event for event in events if isinstance(event, observation_type)]


def latest(observations: Sequence[_O]) -> Optional[_O]:
    """Return the last observation, or None if empty."""
    for obs in reversed(observations):
        return obs
    return None


def earliest(observations: Sequence[_O]) -> Optional[_O]:
    """Return the first observation, or None if empty."""
    for obs in observations:
        return obs
    return None


class ObservationsPre(BaseModel):
    """Observations before an action."""

    main: List[Observation] = Field(default_factory=list)
    previous_post: List[Observation] = Field(default_factory=list)
    late: Dict[str, List[Observation]] = Field(default_factory=dict)


class ObservationsPost(BaseModel):
    """Observations after an action."""

    main: List[Observation] = Field(default_factory=list)
    late: Dict[str, List[Observation]] = Field(default_factory=dict)
    next_pre: ObservationsPre = Field(default_factory=ObservationsPre)


class Step(BaseModel):
    """A single step: observations grouped around an action. Computed, never serialized."""

    observations_pre: ObservationsPre = Field(default_factory=ObservationsPre)
    action: Optional[Action] = None
    observations_post: ObservationsPost = Field(default_factory=ObservationsPost)


class SolverConfig(Component):
    """Configuration for the solver."""

    hints: Optional[str] = None


class VerifierConfig(Component):
    """Configuration for task verification."""

    hints: Optional[str] = None
    config: List[Dict[str, Any]] = Field(default_factory=list)


class VerificationResult(Component):
    """Result from a verifier."""

    result_type: Literal["base"] = "base"
    score: Optional[float] = None
    reasoning: Optional[str] = None
    verifier_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_correct(self) -> Optional[bool]:
        if self.score is None:
            return None
        return self.score >= 0.5


class MajorityVoteMetadata(BaseModel):
    """Metadata from majority voting in rubric scoring."""

    n_instances: int = 0
    median_instance_idx: int = 0
    all_scores: List[float] = Field(default_factory=list)
    median_score: float = 0.0
    outcome_votes: List[Optional[bool]] = Field(default_factory=list)
    majority_output_success: Optional[bool] = None


class MMRubricResult(VerificationResult):
    """Result from the multimodal rubric verification pipeline."""

    result_type: Literal["mm_rubric"] = "mm_rubric"
    total_max_points: float = 0
    total_earned_points: float = 0
    rubric_is_success: bool = False
    intermediate_mm_rubric_steps: Dict[str, Any] = Field(default_factory=dict)
    majority_vote_metadata: MajorityVoteMetadata = Field(
        default_factory=MajorityVoteMetadata
    )
    all_rubric_dicts: List[Dict[str, Any]] = Field(default_factory=list)
    all_scores_list: List[float] = Field(default_factory=list)


class MMRubricOutcomeResult(VerificationResult):
    """Binary outcome verification from the rubric pipeline."""

    result_type: Literal["mm_rubric_outcome"] = "mm_rubric_outcome"
    output_success: Optional[bool] = None
    primary_intent: str = ""


class TrajectoryDiagnosticsResult(VerificationResult):
    """Structured result from trajectory diagnostics verification."""

    result_type: Literal["trajectory_diagnostics"] = "trajectory_diagnostics"
    # Efficiency
    loops: List[Dict[str, Any]] = Field(default_factory=list)
    unnecessary_actions: List[Dict[str, Any]] = Field(default_factory=list)
    efficiency_rating: Optional[int] = None
    efficiency_reasoning: str = ""
    # Success
    solver_self_judgement_of_success: Optional[bool] = None
    solver_self_judgement_reasoning: str = ""
    proxy_verifier_judgement_of_success: Optional[bool] = None
    proxy_verifier_judgement_reasoning: str = ""
    # Optimal plan
    optimal_plan: List[str] = Field(default_factory=list)
    optimal_plan_reasoning: str = ""
    # Critical point (via CriticalPointComplianceAgent)
    task_has_critical_point: Optional[bool] = None
    critical_point_type: Optional[str] = None
    critical_point_classification_reasoning: str = ""
    critical_point_expected_behavior: List[str] = Field(default_factory=list)
    agent_navigated_successfully: Optional[bool] = None
    critical_point_reasoning: str = ""
    # Critical point (via direct LLM call — backup)
    critical_point_llm: Dict[str, Any] = Field(default_factory=dict)


class TaskAgentResult(VerificationResult):
    """Result from the unified task verification classification (Step 10).

    Classifies a task along two axes before execution:
      - Task Ambiguity   (Category 7) — populated by :func:`classify_task`
      - Invalid Task     (Category 8) — populated by :func:`classify_task`
        classification step; fields default to empty/``None``
    """

    result_type: Literal["task_verification"] = "task_verification"
    # Axis 1: Ambiguity
    reasoning_is_ambiguous: str = ""
    is_ambiguous: Optional[bool] = None
    ambiguity_codes: List[str] = Field(default_factory=list)
    # Axis 2: Invalid task
    reasoning_is_invalid: str = ""
    is_invalid: Optional[bool] = None
    invalid_task_codes: List[str] = Field(default_factory=list)


class DataPointMetadata(Component):
    """Metadata about a data generation run."""

    stats: Dict[str, Any] = Field(default_factory=dict)
    run_id: Optional[str] = None
    created_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _set_created_at(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("created_at") is None:
            data["created_at"] = datetime.now().isoformat()
        return data


class SolverLogBase(Component):
    """Solver output containing the sequence of observation-action steps."""

    events: List[Any] = Field(default_factory=list)
    status: SolverStatus = SolverStatus.RUNNING
    outcome: Optional[Outcome] = None

    _observation_type: ClassVar[type]
    _summary_type: ClassVar[type]
    _evidence_field: ClassVar[str]

    @staticmethod
    def _action_steps(
        events: Iterable[Observation | Action], with_tail_observations: bool,
    ) -> Tuple[List[Step], List[Tuple[Observation, int]]]:
        steps = []
        pending = []
        before = []
        for event in events:
            if isinstance(event, Action):
                steps.append(Step(
                    observations_pre=ObservationsPre(main=before), action=event,
                ))
                before = []
            elif event.action_id is None:
                before.append(event)
            else:
                pending.append((event, len(steps)))
        if with_tail_observations and before:
            steps.append(Step(observations_pre=ObservationsPre(main=before)))
        return steps, pending

    @staticmethod
    def _attach_observations(
        steps: List[Step], pending: List[Tuple[Observation, int]],
    ) -> None:
        owners = {
            step.action.id: index for index, step in enumerate(steps)
            if step.action is not None and step.action.id is not None
        }
        for observation, next_index in pending:
            if observation.action_id not in owners:
                raise RuntimeError(
                    f"Observations reference action_id '{observation.action_id}' but no such action exists"
                )
            owner = owners[observation.action_id]
            post = steps[owner].observations_post
            post.main.append(observation)
            if next_index > owner + 1:
                post.late.setdefault(observation.action_id, []).append(observation)
                if next_index < len(steps):
                    steps[next_index].observations_pre.late.setdefault(
                        observation.action_id, []).append(observation)

    def steps(self, with_tail_observations: bool = True) -> List[Step]:
        """Group events by action_id, with an optional trailing observation step."""
        steps, pending = self._action_steps(self.events, with_tail_observations)
        self._attach_observations(steps, pending)
        for index in range(1, len(steps)):
            steps[index].observations_pre.previous_post = steps[index - 1].observations_post.main
        for index in range(len(steps) - 1):
            steps[index].observations_post.next_pre = steps[index + 1].observations_pre
        return steps

    def _get_evidence_and_user_msgs(
        self,
        step: Step,
    ) -> Tuple[str, List[Tuple[UserMessageType, str]]]:
        """Shared helper for evidence lookup and user-message collection."""
        user_msgs: List[Tuple[UserMessageType, str]] = [
            (msg.message_type, msg.content)
            for msg in get_observations(step.observations_pre.main, UserMessage)
        ]

        post_obs = step.observations_post.main + step.observations_post.next_pre.main
        evidence_obs = earliest(
            [
                obs
                for obs in get_observations(post_obs, self._observation_type)
                if getattr(obs, self._evidence_field)
            ]
        )
        evidence_path = getattr(evidence_obs, self._evidence_field) if evidence_obs else ""

        return evidence_path, user_msgs

    def _step_summary(self, step: Step, index: int) -> BaseModel:
        content = step.action.content
        arguments = content.get("arguments", {})
        action_args = {
            key: value for key, value in arguments.items()
            if key not in ("screen_description", "reasoning")
        }
        evidence_path, user_messages = self._get_evidence_and_user_msgs(step)
        before = step.observations_pre.previous_post + step.observations_pre.main
        url_observation = latest([
            observation for observation in get_observations(before, self._observation_type)
            if observation.url
        ])
        return self._summary_type(
            index=index,
            action_name=step.action.action_name,
            action_args=action_args,
            action_nl_description=step.action.action_nl_description,
            action_content=content,
            url=url_observation.url if url_observation else "",
            state_description=arguments.get("screen_description", ""),
            previous_error=content.get("other_state", {}).get("previous_error", ""),
            **{self._evidence_field: evidence_path},
            user_messages_before=user_messages,
        )

    def get_step_summaries(self) -> List[BaseModel]:
        """Extract action, evidence, URL and user context for each action step."""
        return [
            self._step_summary(step, index)
            for index, step in enumerate(self.steps(with_tail_observations=False), start=1)
        ]


class AgentConfig(BaseModel):
    """Base configuration for agents."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    name: str = "agent"
    client: Any = None
    metadata: dict[str, Any] = {}


class Agent(ABC):
    """Configuration and client access for an agent."""

    def __init__(
        self, config: AgentConfig | dict[str, Any] | None = None, **kwargs: Any
    ):
        if config is None:
            config = self._get_config_class().model_validate(kwargs)
        elif isinstance(config, dict):
            config = self._get_config_class().model_validate(config)
        self.config = config

    @classmethod
    def _get_config_class(cls) -> type[AgentConfig]:
        return AgentConfig

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def client(self) -> Any:
        return self.config.client


class VerifierAgent(Agent):
    """Marker base for verification agents."""


class RunContext:  # noqa: D401 — stub for type-hint compatibility
    """Inputs for programmatic agent calls."""

    data_point: Any = None
    output_dir: Any = None
