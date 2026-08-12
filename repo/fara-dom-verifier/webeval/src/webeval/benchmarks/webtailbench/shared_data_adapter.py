"""Convert fara ``Trajectory`` (web_surfer.log + screenshots + FinalAnswer)
into a :class:`DataPoint` consumable by :class:`MMRubricAgent`.

The main entry point is :func:`create_datapoint` which returns a DataPoint
whose ``solver_log.get_step_summaries()`` output is compatible with
``MMRubricAgent._extract_input_from_datapoint``.

Screenshot normalization
------------------------
``MMRubricAgent._load_screenshots`` uses the regex ``screenshot_(\\d+)`` to
extract the 1-based screenshot index and validates it against the action
id. Old fara/webeval trajectories sometimes use ``screenshot0.png`` (no
underscore, 0-based) or other conventions. The adapter creates
``screenshot_{1-based}.png`` symlinks when the naming convention differs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Literal

from webeval.rubric_agent.data_point import (
    Action,
    ComputerObservation,
    DataPoint,
    DataPointMetadata,
    Outcome,
    SolverLog,
    SolverStatus,
    Task,
)
from webeval.rubric_agent.dom_evidence import load_diff, load_snapshot
from webeval.trajectory import DOMEvidenceFrame, Trajectory


EvidenceMode = Literal["screenshot", "dom", "dual"]


def _screenshot_sort_key(s) -> int:
    """Trailing numeric index from a screenshot filename.

    Handles ``screenshot_1.png``, ``screenshot0.png``,
    ``screenshot_post_3.png`` etc.
    """
    stem = Path(s).stem if not isinstance(s, Path) else s.stem
    match = re.search(r"(\d+)$", stem)
    return int(match.group(1)) if match else 0


def _normalize_screenshots(candidate_path: Path, sorted_screenshots: list) -> list:
    """Ensure screenshots follow ``screenshot_{N}.png`` 1-based naming.

    Creates symlinks when originals use a different convention and returns
    the list of normalized filenames relative to ``candidate_path``.
    """
    normalized: list[str] = []
    for i, screenshot in enumerate(sorted_screenshots):
        canonical_name = f"screenshot_{i + 1}.png"
        canonical_path = candidate_path / canonical_name
        original = Path(screenshot)

        if original.name == canonical_name:
            normalized.append(canonical_name)
            continue

        if canonical_path.exists() or canonical_path.is_symlink():
            normalized.append(canonical_name)
            continue

        try:
            canonical_path.symlink_to(original.name)
        except OSError:
            rel = (
                str(original.relative_to(candidate_path))
                if original.is_absolute()
                else str(original)
            )
            normalized.append(rel)
            continue

        normalized.append(canonical_name)
    return normalized


def _validated_dom_frames(
    candidate: Trajectory, action_count: int
) -> list[DOMEvidenceFrame]:
    """Return complete, contiguous, on-disk DOM evidence for every action."""
    manifest = candidate.dom_manifest
    if manifest is None:
        return _validated_step_folder_dom_frames(candidate.path, action_count)

    frames = manifest.frames
    if len(frames) != action_count:
        raise ValueError(
            "DOM evidence/action count mismatch: "
            f"{len(frames)} frames for {action_count} actions"
        )

    expected_ordinals = list(range(1, action_count + 1))
    actual_ordinals = [frame.action_ordinal for frame in frames]
    if actual_ordinals != expected_ordinals:
        raise ValueError(
            "DOM evidence frames must be contiguous and action-aligned: "
            f"expected ordinals {expected_ordinals}, got {actual_ordinals}"
        )

    expected_before = manifest.initial_snapshot
    if expected_before is None:
        raise ValueError("DOM evidence manifest is missing initial_snapshot (S0)")
    previous_snapshot = load_snapshot(expected_before)

    for frame in frames:
        references = {
            "before_snapshot": frame.before_snapshot,
            "after_snapshot": frame.after_snapshot,
            "diff": frame.diff,
        }
        missing = [name for name, path in references.items() if path is None]
        if missing:
            raise ValueError(
                f"DOM evidence frame {frame.action_ordinal} is missing "
                f"{', '.join(missing)}"
            )
        if frame.before_snapshot != expected_before:
            raise ValueError(
                f"DOM evidence frame {frame.action_ordinal} has a broken snapshot "
                "chain"
            )
        absent = [name for name, path in references.items() if not path.is_file()]
        if absent:
            raise ValueError(
                f"DOM evidence frame {frame.action_ordinal} references missing "
                f"files: {', '.join(absent)}"
            )
        before_snapshot = load_snapshot(frame.before_snapshot)
        after_snapshot = load_snapshot(frame.after_snapshot)
        diff = load_diff(frame.diff)
        if (
            before_snapshot.snapshot_id != previous_snapshot.snapshot_id
            or before_snapshot.hash != previous_snapshot.hash
        ):
            raise ValueError(
                f"DOM evidence frame {frame.action_ordinal} before-snapshot "
                "does not match the previous state"
            )
        if (
            diff.from_snapshot_id != before_snapshot.snapshot_id
            or diff.from_hash != before_snapshot.hash
            or diff.to_snapshot_id != after_snapshot.snapshot_id
            or diff.to_hash != after_snapshot.hash
        ):
            raise ValueError(
                f"DOM evidence frame {frame.action_ordinal} has a hash-mismatched diff"
            )
        if frame.coverage_status != after_snapshot.coverage.status:
            raise ValueError(
                f"DOM evidence frame {frame.action_ordinal} coverage label "
                f"{frame.coverage_status!r} does not match "
                f"{after_snapshot.coverage.status!r}"
            )
        previous_snapshot = after_snapshot
        expected_before = frame.after_snapshot

    return frames


def _validated_step_folder_dom_frames(
    candidate_path: Path, action_count: int
) -> list[DOMEvidenceFrame]:
    """Return DOM frames from the manual ``step_XXX`` evidence layout.

    This supports the DOM-only dataset format:

    ``step_XXX/before/chromiumrl_dom.json``
    ``step_XXX/after/chromiumrl_dom.json``
    ``step_XXX/dom_diff.json``
    ``step_XXX/before/page_state.json``
    ``step_XXX/after/page_state.json``
    ``step_XXX/verifier_action.json``

    No screenshots, semantic-DOM manifest, raw CDP DOM, or agent observation
    files are required.
    """
    frames: list[DOMEvidenceFrame] = []
    missing: list[str] = []
    for ordinal in range(1, action_count + 1):
        step_dir = candidate_path / f"step_{ordinal:03d}"
        required = {
            "before_snapshot": step_dir / "before" / "chromiumrl_dom.json",
            "after_snapshot": step_dir / "after" / "chromiumrl_dom.json",
            "diff": step_dir / "dom_diff.json",
            "before_page_state": step_dir / "before" / "page_state.json",
            "after_page_state": step_dir / "after" / "page_state.json",
            "verifier_action": step_dir / "verifier_action.json",
        }
        absent = [name for name, path in required.items() if not path.is_file()]
        if absent:
            missing.append(
                f"step_{ordinal:03d}: " + ", ".join(absent)
            )
            continue
        frames.append(
            DOMEvidenceFrame(
                schema_version="chromiumrl-dom-step/v1",
                action_ordinal=ordinal,
                action_id=str(ordinal),
                before_snapshot=required["before_snapshot"].resolve(strict=False),
                after_snapshot=required["after_snapshot"].resolve(strict=False),
                diff=required["diff"].resolve(strict=False),
                before_page_state=required["before_page_state"].resolve(strict=False),
                after_page_state=required["after_page_state"].resolve(strict=False),
                verifier_action=required["verifier_action"].resolve(strict=False),
                capture_status="complete",
                coverage_status="chromiumrl_dom",
            )
        )
    if missing:
        raise ValueError(
            "DOM evidence requested but required step-folder files are missing: "
            + "; ".join(missing)
        )
    if len(frames) != action_count:
        raise ValueError(
            f"DOM evidence/action count mismatch: {len(frames)} frames for "
            f"{action_count} actions"
        )
    return frames


def create_datapoint(
    task_data: Dict[str, Any],
    candidate: Trajectory,
    evidence_mode: EvidenceMode = "screenshot",
) -> DataPoint:
    """Convert *task_data* + *candidate* Trajectory into a :class:`DataPoint`.

    Parameters
    ----------
    task_data : dict
        Must contain ``"question"`` at minimum; ``"init_url"`` is
        optional (defaults to empty string).
    candidate : Trajectory
        Loaded fara trajectory with ``events`` and ``answer.screenshots``.
    evidence_mode : {"screenshot", "dom", "dual"}
        Evidence attached to each action. DOM modes require exactly one
        contiguous manifest frame per action and never rename or truncate DOM
        artifacts.
    """
    if evidence_mode not in ("screenshot", "dom", "dual"):
        raise ValueError(f"Unsupported evidence_mode: {evidence_mode!r}")

    action_events = [evt for evt in candidate.events if evt.get("action")]

    normalized_screenshots: list[str] = []
    if evidence_mode in ("screenshot", "dual"):
        sorted_screenshots = sorted(
            candidate.answer.screenshots, key=_screenshot_sort_key
        )[: len(action_events)]
        normalized_screenshots = _normalize_screenshots(
            candidate.path, sorted_screenshots
        )

    dom_frames: list[DOMEvidenceFrame] = []
    if evidence_mode in ("dom", "dual"):
        dom_frames = _validated_dom_frames(candidate, len(action_events))

    # precomputed rubric (optional) — may live on task_data or on disk next
    # to the trajectory.
    precomputed_rubric = task_data.get("precomputed_rubric")
    if precomputed_rubric is None:
        task_data_path = candidate.path / "task_data.json"
        if task_data_path.exists():
            try:
                with open(task_data_path, "r") as f:
                    loaded = json.load(f)
                precomputed_rubric = loaded.get("precomputed_rubric")
            except Exception:
                pass

    task_metadata: Dict[str, Any] = {"evidence_mode": evidence_mode}
    if precomputed_rubric is not None:
        task_metadata["precomputed_rubric"] = precomputed_rubric

    task = Task(
        task_id=task_data.get("id", candidate.path.name),
        instruction=task_data.get("question", ""),
        environment_config={"init_url": task_data.get("init_url", "")},
        metadata=task_metadata,
    )

    events: list = []
    for i, evt in enumerate(action_events):
        args = evt.get("arguments") or {}
        action_name = args.get("action", evt.get("action", ""))
        if action_name in ("stop_and_answer_question", "stop_execution"):
            action_name = "terminate"
        action_args = {k: v for k, v in args.items() if k != "action"}
        action_id = str(i + 1)

        events.append(ComputerObservation(url=evt.get("url", "")))

        events.append(
            Action(
                id=action_id,
                action_name=action_name,
                content={"action": action_name, "arguments": action_args},
                action_nl_description=args.get("thoughts", "")
                or f"{args.get('state_description', '')} {args.get('reasoning', '')}".strip(),
            )
        )

        screenshot_path = (
            normalized_screenshots[i] if i < len(normalized_screenshots) else ""
        )
        dom_frame = dom_frames[i] if i < len(dom_frames) else None
        events.append(
            ComputerObservation(
                evidence_mode=evidence_mode,
                screenshot_path=screenshot_path,
                dom_evidence_schema_version=(
                    dom_frame.schema_version if dom_frame else ""
                ),
                dom_action_ordinal=(
                    dom_frame.action_ordinal if dom_frame else None
                ),
                dom_action_id=dom_frame.action_id if dom_frame else "",
                dom_before_snapshot_path=(
                    str(dom_frame.before_snapshot) if dom_frame else ""
                ),
                dom_after_snapshot_path=(
                    str(dom_frame.after_snapshot) if dom_frame else ""
                ),
                dom_diff_path=str(dom_frame.diff) if dom_frame else "",
                dom_before_page_state_path=(
                    str(dom_frame.before_page_state) if dom_frame else ""
                ),
                dom_after_page_state_path=(
                    str(dom_frame.after_page_state) if dom_frame else ""
                ),
                dom_verifier_action_path=(
                    str(dom_frame.verifier_action) if dom_frame else ""
                ),
                dom_capture_status=(
                    dom_frame.capture_status if dom_frame else ""
                ),
                dom_coverage_status=(
                    dom_frame.coverage_status if dom_frame else ""
                ),
                action_id=action_id,
            )
        )

    solver_log = SolverLog(
        events=events,
        status=SolverStatus.COMPLETE,
        outcome=Outcome(answer=candidate.answer.final_answer),
    )

    return DataPoint(
        task=task,
        solver_log=solver_log,
        metadata=DataPointMetadata(run_id=candidate.path.name),
    )
