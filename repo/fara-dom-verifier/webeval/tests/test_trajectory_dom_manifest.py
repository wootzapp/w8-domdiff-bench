from __future__ import annotations

import json
from pathlib import Path


def _write_answer(directory: Path, screenshots: list[str] | None = None) -> None:
    (directory / "_answer.json").write_text(
        json.dumps(
            {
                "final_answer": "done",
                "screenshots": screenshots or [],
                "is_rel_paths": True,
            }
        )
    )


def test_legacy_trajectory_loads_without_dom_manifest(tmp_path):
    from webeval.trajectory import Trajectory

    (tmp_path / "web_surfer.log").write_text("")
    (tmp_path / "screen.png").write_bytes(b"png")
    _write_answer(tmp_path, ["screen.png"])

    trajectory = Trajectory(tmp_path)

    assert trajectory.screenshots == [tmp_path / "screen.png"]
    assert trajectory.dom_manifest is None
    assert trajectory.dom_evidence_frames == []


def test_v2_manifest_loads_typed_resolved_references(tmp_path):
    from webeval.trajectory import DOMEvidenceFrame, DOMTrajectoryManifest, Trajectory

    (tmp_path / "web_surfer.log").write_text("")
    _write_answer(tmp_path)
    before = tmp_path / "evidence/step_0000/semantic_dom.json"
    after = tmp_path / "evidence/step_0001/semantic_dom.json"
    diff = tmp_path / "evidence/step_0001/dom_diff.json"
    for artifact in (before, after, diff):
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("{}")

    (tmp_path / "trajectory_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "dom-trajectory-manifest/v2",
                "evidence_format": "semantic-dom",
                "canonicalizer_version": "semantic-dom-canonicalizer/v1",
                "created_at": "2026-07-24T00:00:00Z",
                "browser": {"viewport_width": 1440},
                "initial_snapshot": "evidence/step_0000/semantic_dom.json",
                "frames": [
                    {
                        "schema_version": "dom-evidence-frame/v1",
                        "action_ordinal": 1,
                        "action_id": "action-0001",
                        "before_snapshot": "evidence/step_0000/semantic_dom.json",
                        "after_snapshot": "evidence/step_0001/semantic_dom.json",
                        "diff": "evidence/step_0001/dom_diff.json",
                        "capture_status": "complete",
                        "coverage_status": "complete",
                    }
                ],
                "capture_errors": [],
            }
        )
    )

    trajectory = Trajectory(tmp_path)

    assert isinstance(trajectory.dom_manifest, DOMTrajectoryManifest)
    assert trajectory.dom_manifest.initial_snapshot == before.resolve()
    assert len(trajectory.dom_evidence_frames) == 1
    frame = trajectory.dom_evidence_frames[0]
    assert isinstance(frame, DOMEvidenceFrame)
    assert frame.before_snapshot == before.resolve()
    assert frame.after_snapshot == after.resolve()
    assert frame.diff == diff.resolve()
