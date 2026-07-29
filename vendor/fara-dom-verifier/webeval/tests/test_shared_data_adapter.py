"""Tests for ``webtailbench.shared_data_adapter.create_datapoint``.

Builds a minimal fara ``Trajectory`` on disk (action log + fake
screenshots + FinalAnswer JSON) and verifies the DataPoint it produces
matches what ``MMRubricAgent._extract_input_from_datapoint`` expects.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _dom_snapshot(ordinal: int) -> dict:
    value = {
        "schema_version": "semantic-dom-snapshot/v1",
        "canonicalizer_version": "semantic-dom-canonicalizer/v1",
        "snapshot_id": f"snapshot-{ordinal:04d}",
        "ordinal": ordinal,
        "url": f"https://example.test/step/{ordinal}",
        "title": f"Step {ordinal}",
        "captured_at": "2026-07-24T00:00:00Z",
        "hash": "",
        "nodes": [],
        "coverage": {
            "status": "complete",
            "rendered_dom": True,
            "nodes_seen": 0,
            "nodes_captured": 0,
            "node_limit": 5000,
            "text_limit": 1000,
            "truncated": False,
            "same_origin_frames": 1,
            "open_shadow_roots": 0,
            "cross_origin_frames": [],
            "canvas_count": 0,
            "image_without_alt_count": 0,
            "unsupported": [
                "closed-shadow-roots",
                "canvas-pixels",
                "image-pixels",
                "visual-style-and-layout",
            ],
            "errors": [],
        },
    }
    payload = {
        key: item
        for key, item in value.items()
        if key not in {"snapshot_id", "ordinal", "captured_at", "hash"}
    }
    value["hash"] = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def _make_trajectory_dir(root: Path, n_actions: int = 2) -> Path:
    d = root / "sample_traj"
    d.mkdir(parents=True, exist_ok=True)

    # web_surfer.log: one action per line, fara's format (dict with action/arguments/url).
    log = d / "web_surfer.log"
    events = []
    for i in range(n_actions):
        events.append(
            {
                # ``gpt_solver=True`` in ``Trajectory`` filters on source==WebSurfer.
                "source": "WebSurfer",
                "action": "click" if i < n_actions - 1 else "stop_execution",
                "url": f"https://example.com/step_{i}",
                "arguments": {
                    "action": "click" if i < n_actions - 1 else "stop_execution",
                    "thoughts": f"thinking at step {i}",
                    "screen_description": f"screen at step {i}",
                    "target": f"button_{i}" if i < n_actions - 1 else None,
                },
            }
        )
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    # Fake screenshots on disk — content not validated by the adapter.
    screenshots = []
    for i in range(n_actions):
        p = d / f"screenshot_{i}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG signature, harmless for tests
        screenshots.append(p.name)

    # FinalAnswer JSON — follows fara's FinalAnswer schema.
    answer = {
        "final_answer": "done",
        "env_state_json": "{}",
        "env_state_raw": "",
        "screenshots": screenshots,
        "is_aborted": False,
        "is_rel_paths": True,
        "token_usage": {},
    }
    (d / "_answer.json").write_text(json.dumps(answer))
    return d


def _write_dom_manifest(
    trajectory_dir: Path,
    n_actions: int,
    *,
    ordinals: list[int] | None = None,
    omit_diff_for: int | None = None,
) -> None:
    ordinals = ordinals or list(range(1, n_actions + 1))
    initial = trajectory_dir / "evidence/step_0000/semantic_dom.json"
    initial.parent.mkdir(parents=True, exist_ok=True)
    snapshots = {0: _dom_snapshot(0)}
    initial.write_text(json.dumps(snapshots[0]))
    frames = []
    for ordinal in ordinals:
        step_dir = trajectory_dir / f"evidence/step_{ordinal:04d}"
        step_dir.mkdir(parents=True, exist_ok=True)
        snapshots[ordinal] = _dom_snapshot(ordinal)
        (step_dir / "semantic_dom.json").write_text(json.dumps(snapshots[ordinal]))
        if ordinal != omit_diff_for:
            before = snapshots.get(ordinal - 1, _dom_snapshot(ordinal - 1))
            (step_dir / "dom_diff.json").write_text(
                json.dumps(
                    {
                        "schema_version": "semantic-dom-diff/v1",
                        "canonicalizer_version": "semantic-dom-canonicalizer/v1",
                        "diff_id": f"diff-{ordinal:04d}",
                        "from_snapshot_id": before["snapshot_id"],
                        "to_snapshot_id": snapshots[ordinal]["snapshot_id"],
                        "from_hash": before["hash"],
                        "to_hash": snapshots[ordinal]["hash"],
                        "added": [],
                        "removed": [],
                        "updated": [],
                        "unchanged_count": 0,
                    }
                )
            )
        frames.append(
            {
                "schema_version": "dom-evidence-frame/v1",
                "action_ordinal": ordinal,
                "action_id": f"action-{ordinal:04d}",
                "before_snapshot": (
                    f"evidence/step_{ordinal - 1:04d}/semantic_dom.json"
                ),
                "after_snapshot": f"evidence/step_{ordinal:04d}/semantic_dom.json",
                "diff": f"evidence/step_{ordinal:04d}/dom_diff.json",
                "capture_status": "complete",
                "coverage_status": "complete",
            }
        )
    (trajectory_dir / "trajectory_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "dom-trajectory-manifest/v2",
                "evidence_format": "semantic-dom",
                "canonicalizer_version": "semantic-dom-canonicalizer/v1",
                "created_at": "2026-07-24T00:00:00Z",
                "browser": {},
                "initial_snapshot": "evidence/step_0000/semantic_dom.json",
                "frames": frames,
                "capture_errors": [],
            }
        )
    )


def test_create_datapoint_normalizes_screenshots_and_actions(tmp_path):
    from webeval.benchmarks.webtailbench.shared_data_adapter import create_datapoint
    from webeval.trajectory import Trajectory

    traj_dir = _make_trajectory_dir(tmp_path, n_actions=3)
    traj = Trajectory(traj_dir, gpt_solver=True)

    task_data = {
        "id": "sample_traj",
        "question": "pretend to click buttons",
        "init_url": "https://example.com",
    }
    dp = create_datapoint(task_data, traj)

    assert dp.task.task_id == "sample_traj"
    assert dp.task.instruction == "pretend to click buttons"
    assert dp.task.environment_config["init_url"] == "https://example.com"

    summaries = dp.solver_log.get_step_summaries()
    assert len(summaries) == 3
    # Last action must have been normalized stop_execution → terminate.
    assert summaries[-1].action_name == "terminate"
    # Screenshot indices must be 1-based and match action index.
    for i, s in enumerate(summaries, start=1):
        assert s.index == i
        assert s.screenshot_path.endswith(f"screenshot_{i}.png")


def test_create_datapoint_handles_missing_init_url(tmp_path):
    """Task_data without ``init_url`` should default to an empty string
    rather than crashing — WebTailBench TSV does not ship init_url."""
    from webeval.benchmarks.webtailbench.shared_data_adapter import create_datapoint
    from webeval.trajectory import Trajectory

    traj_dir = _make_trajectory_dir(tmp_path, n_actions=1)
    traj = Trajectory(traj_dir, gpt_solver=True)

    dp = create_datapoint({"id": "x", "question": "noop"}, traj)
    assert dp.task.environment_config["init_url"] == ""


@pytest.mark.parametrize("evidence_mode", ["dom", "dual"])
def test_create_datapoint_aligns_one_dom_frame_per_action(
    tmp_path, evidence_mode
):
    from webeval.benchmarks.webtailbench.shared_data_adapter import create_datapoint
    from webeval.trajectory import Trajectory

    traj_dir = _make_trajectory_dir(tmp_path, n_actions=3)
    _write_dom_manifest(traj_dir, n_actions=3)
    traj = Trajectory(traj_dir, gpt_solver=True)

    dp = create_datapoint(
        {"id": "dom", "question": "use DOM evidence"},
        traj,
        evidence_mode=evidence_mode,
    )
    summaries = dp.solver_log.get_step_summaries()

    assert len(summaries) == 3
    for ordinal, summary in enumerate(summaries, start=1):
        assert summary.evidence_mode == evidence_mode
        assert summary.dom_action_ordinal == ordinal
        assert summary.dom_action_id == f"action-{ordinal:04d}"
        assert summary.dom_before_snapshot_path.endswith(
            f"step_{ordinal - 1:04d}/semantic_dom.json"
        )
        assert summary.dom_after_snapshot_path.endswith(
            f"step_{ordinal:04d}/semantic_dom.json"
        )
        assert summary.dom_diff_path.endswith(
            f"step_{ordinal:04d}/dom_diff.json"
        )
        assert summary.screenshot_path == (
            "" if evidence_mode == "dom" else f"screenshot_{ordinal}.png"
        )


def test_create_datapoint_rejects_gapped_dom_frames(tmp_path):
    from webeval.benchmarks.webtailbench.shared_data_adapter import create_datapoint
    from webeval.trajectory import Trajectory

    traj_dir = _make_trajectory_dir(tmp_path, n_actions=2)
    _write_dom_manifest(traj_dir, n_actions=2, ordinals=[1, 3])
    traj = Trajectory(traj_dir, gpt_solver=True)

    with pytest.raises(ValueError, match="contiguous and action-aligned"):
        create_datapoint({}, traj, evidence_mode="dom")


def test_create_datapoint_rejects_missing_dom_artifact(tmp_path):
    from webeval.benchmarks.webtailbench.shared_data_adapter import create_datapoint
    from webeval.trajectory import Trajectory

    traj_dir = _make_trajectory_dir(tmp_path, n_actions=2)
    _write_dom_manifest(traj_dir, n_actions=2, omit_diff_for=2)
    traj = Trajectory(traj_dir, gpt_solver=True)

    with pytest.raises(ValueError, match="references missing files: diff"):
        create_datapoint({}, traj, evidence_mode="dom")


def test_create_datapoint_rejects_malformed_dom_artifact(tmp_path):
    from webeval.benchmarks.webtailbench.shared_data_adapter import create_datapoint
    from webeval.trajectory import Trajectory

    traj_dir = _make_trajectory_dir(tmp_path, n_actions=1)
    _write_dom_manifest(traj_dir, n_actions=1)
    (traj_dir / "evidence/step_0001/semantic_dom.json").write_text("{broken")
    traj = Trajectory(traj_dir, gpt_solver=True)

    with pytest.raises(json.JSONDecodeError):
        create_datapoint({}, traj, evidence_mode="dom")


def test_create_datapoint_rejects_hash_mismatched_dom_artifact(tmp_path):
    from webeval.benchmarks.webtailbench.shared_data_adapter import create_datapoint
    from webeval.trajectory import Trajectory

    traj_dir = _make_trajectory_dir(tmp_path, n_actions=1)
    _write_dom_manifest(traj_dir, n_actions=1)
    path = traj_dir / "evidence/step_0001/semantic_dom.json"
    value = json.loads(path.read_text())
    value["title"] = "tampered"
    path.write_text(json.dumps(value))
    traj = Trajectory(traj_dir, gpt_solver=True)

    with pytest.raises(Exception, match="snapshot hash mismatch"):
        create_datapoint({}, traj, evidence_mode="dom")
