from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import runner  # noqa: E402


class TrajectoryExportTests(unittest.TestCase):
    def make_step(
        self,
        run_dir: Path,
        number: int,
        *,
        action: dict[str, Any],
        thought: str | None,
        target: dict[str, str] | None = None,
        success: bool = True,
    ) -> Path:
        step_dir = run_dir / "steps" / f"step_{number:03d}"
        step_dir.mkdir(parents=True)
        action_record: dict[str, Any] = {
            "step": number,
            "model_turn": number,
            "started_at": f"2026-08-10T05:45:0{number}.071Z",
            "completed_at": f"2026-08-10T05:45:0{number}.171Z",
            "action": action,
            "thought": thought,
            "target": target,
            "coordinate_capture": (
                {
                    "status": "resolved",
                    "source": "ChromiumRL.getAgentObservation",
                    "match_method": "exact_role_name",
                    "candidate_count": 1,
                    "coordinate": [1073, 50],
                }
                if target is not None else None
            ),
            "action_driver": "agent-browser",
            "action_result": {"success": success, "data": {}},
            "action_error": None if success else "action failed",
            "action_succeeded": success,
            "task_memory": "must not be exported",
            "action_context": {"must_not": "be verifier evidence"},
        }
        runner.write_json(step_dir / "action.json", action_record)
        runner.write_json(
            step_dir / "dom_diff.json",
            {
                "source": "runner_snapshot_diff",
                "before": {"url": f"https://example.test/before/{number}"},
                "after": {"url": f"https://example.test/after/{number}"},
                "status": "changed",
                "change_count": 1,
                "diff": {"changed": [{"path": "html/body/button[1]"}]},
            },
        )
        runner.write_text(step_dir / "dom_diff.txt", "status: changed\n")
        return step_dir

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_export_is_self_contained_and_preserves_verbatim_thought(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            runner.write_json(run_dir / "manifest.json", {"task_id": "fixture"})
            thought = "Click the visible “Search” button exactly once."
            target = {"ref": "e29", "role": "button", "name": "Search"}
            click_step = self.make_step(
                run_dir,
                1,
                action={"action": "click", "id": "e29"},
                thought=thought,
                target=target,
            )
            self.make_step(
                run_dir,
                2,
                action=dict(
                    action="navigate",
                    url="https://example.test/result",
                ),
                thought="Open the verified result page.",
            )
            runner.write_text(
                run_dir / "decisions.jsonl",
                json.dumps(
                    {
                        "decision": {
                            "action": "terminate",
                            "thought": "REJECTED THOUGHT MUST NOT APPEAR",
                        },
                        "rejection_reason": "premature",
                    }
                )
                + "\n",
            )

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "complete")
            self.assertFalse(report["requires_action_json_after_export"])
            trajectory = self.read_jsonl(run_dir / "trajectory.jsonl")
            websurfer = self.read_jsonl(run_dir / "web_surfer.log")
            self.assertEqual(len(trajectory), 2)
            self.assertEqual(len(websurfer), 2)
            self.assertEqual(trajectory[0]["thought"], thought)
            self.assertEqual(trajectory[0]["arguments"]["ref"], "e29")
            self.assertEqual(trajectory[0]["arguments"]["target"], target)
            self.assertEqual(trajectory[0]["arguments"]["coordinate"], [1073, 50])
            self.assertEqual(websurfer[0]["arguments"]["ref"], "e29")
            self.assertEqual(websurfer[0]["arguments"]["target"], target)
            self.assertEqual(websurfer[0]["arguments"]["coordinate"], [1073, 50])
            self.assertEqual(websurfer[0]["arguments"]["thoughts"], thought)
            self.assertIn(f"Thought #1: {thought}", websurfer[0]["message"])
            self.assertNotIn(
                "REJECTED THOUGHT MUST NOT APPEAR",
                (run_dir / "web_surfer.log").read_text(encoding="utf-8"),
            )
            self.assertNotIn("task_memory", trajectory[0])
            self.assertNotIn("action_context", trajectory[0])

            # The exported row retains ref and semantics after action.json is gone.
            (click_step / "action.json").unlink()
            preserved = self.read_jsonl(run_dir / "web_surfer.log")[0]
            self.assertEqual(
                preserved["arguments"]["target"],
                {"ref": "e29", "role": "button", "name": "Search"},
            )

    def test_missing_thought_invalidates_the_whole_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            self.make_step(
                run_dir,
                1,
                action={"action": "click", "id": "e1"},
                thought=None,
                target={"ref": "e1", "role": "button", "name": "Continue"},
            )

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "invalid")
            self.assertFalse((run_dir / "trajectory.jsonl").exists())
            self.assertFalse((run_dir / "web_surfer.log").exists())

    def test_failed_action_is_exported_with_explicit_failure_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            self.make_step(
                run_dir,
                1,
                action={"action": "click", "id": "e1"},
                thought="Click Continue.",
                target={"ref": "e1", "role": "button", "name": "Continue"},
            )
            self.make_step(
                run_dir,
                2,
                action={"action": "click", "id": "e2"},
                thought="Click Search.",
                target={"ref": "e2", "role": "button", "name": "Search"},
                success=False,
            )

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["exported_actions"], 2)
            trajectory = self.read_jsonl(run_dir / "trajectory.jsonl")
            websurfer = self.read_jsonl(run_dir / "web_surfer.log")
            self.assertEqual(trajectory[0]["execution_status"], "success")
            self.assertEqual(trajectory[1]["execution_status"], "failure")
            self.assertEqual(trajectory[1]["execution_error"], "action failed")
            self.assertEqual(websurfer[1]["execution_status"], "failure")
            self.assertEqual(websurfer[1]["execution_error"], "action failed")

    def test_human_intervention_step_is_skipped_without_hiding_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            self.make_step(
                run_dir,
                1,
                action={"action": "click", "id": "e1"},
                thought="Open the public results.",
                target={"ref": "e1", "role": "button", "name": "Continue"},
            )
            self.make_step(
                run_dir,
                2,
                action={"action": "request_human"},
                thought="Ask the operator to resolve the visible challenge.",
                success=False,
            )
            self.make_step(
                run_dir,
                3,
                action={"action": "navigate", "url": "https://example.test/result"},
                thought="Open the verified result page.",
            )

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["exported_actions"], 2)
            self.assertEqual(
                report["skipped"],
                [{
                    "step": "step_002",
                    "reason": "human intervention step is not an executed browser action",
                }],
            )
            trajectory = self.read_jsonl(run_dir / "trajectory.jsonl")
            self.assertEqual([row["action_number"] for row in trajectory], [1, 2])
            self.assertEqual(
                [row["source_step"] for row in trajectory],
                ["step_001", "step_003"],
            )

    def test_invalid_regeneration_removes_stale_derived_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            step_dir = self.make_step(
                run_dir,
                1,
                action={"action": "click", "id": "e1"},
                thought="Click Continue.",
                target={"ref": "e1", "role": "button", "name": "Continue"},
            )
            self.assertEqual(
                runner.generate_trajectory_artifacts(run_dir)["status"],
                "complete",
            )
            action_record = json.loads(
                (step_dir / "action.json").read_text(encoding="utf-8")
            )
            action_record["thought"] = None
            runner.write_json(step_dir / "action.json", action_record)

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "invalid")
            self.assertFalse((run_dir / "trajectory.jsonl").exists())
            self.assertFalse((run_dir / "web_surfer.log").exists())

    def test_step_sequence_must_be_contiguous(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            self.make_step(
                run_dir,
                2,
                action=dict(action="navigate", url="https://example.test"),
                thought="Open the page.",
            )

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "invalid")
            self.assertIn("not contiguous", report["errors"][0]["error"])

    def test_unresolved_click_omits_coordinate_but_keeps_semantic_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            step_dir = self.make_step(
                run_dir,
                1,
                action={"action": "click", "id": "e29"},
                thought="Click the visible Search button.",
                target={"ref": "e29", "role": "button", "name": "Search"},
            )
            action_record = json.loads(
                (step_dir / "action.json").read_text(encoding="utf-8")
            )
            action_record["coordinate_capture"] = {
                "status": "ambiguous",
                "source": "ChromiumRL.getAgentObservation",
                "coordinate_source": "get_agent_observation",
                "candidate_count": 2,
            }
            runner.write_json(step_dir / "action.json", action_record)

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "complete")
            trajectory = self.read_jsonl(run_dir / "trajectory.jsonl")
            websurfer = self.read_jsonl(run_dir / "web_surfer.log")
            self.assertEqual(trajectory[0]["coordinate_status"], "ambiguous")
            self.assertNotIn("coordinate", trajectory[0]["arguments"])
            self.assertNotIn("coordinate_status", trajectory[0]["arguments"])
            self.assertEqual(
                trajectory[0]["arguments"]["target"],
                {"ref": "e29", "role": "button", "name": "Search"},
            )
            self.assertNotIn("coordinate", websurfer[0]["arguments"])
            self.assertNotIn("coordinate_status", websurfer[0]["arguments"])

    def test_clamped_wait_exports_executed_value_without_extra_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            step_dir = self.make_step(
                run_dir,
                1,
                action={"action": "wait", "seconds": 60},
                thought="Wait for the page to settle.",
            )
            action_record = json.loads(
                (step_dir / "action.json").read_text(encoding="utf-8")
            )
            action_record["action_result"]["normalized_parameters"] = {
                "seconds": 10.0
            }
            runner.write_json(step_dir / "action.json", action_record)

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "complete")
            trajectory = self.read_jsonl(run_dir / "trajectory.jsonl")
            self.assertEqual(
                set(trajectory[0]["arguments"]),
                {"action", "seconds", "thoughts"},
            )
            self.assertEqual(trajectory[0]["arguments"]["seconds"], 10.0)

    def test_select_and_wait_preserve_exact_executed_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            self.make_step(
                run_dir,
                1,
                action={"action": "select", "id": "e3", "text": "Newest"},
                thought="Select the Newest option.",
                target={"ref": "e3", "role": "combobox", "name": "Sort"},
            )
            self.make_step(
                run_dir,
                2,
                action={"action": "wait", "seconds": 1.5},
                thought="Wait for the results to load.",
            )

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "complete")
            trajectory = self.read_jsonl(run_dir / "trajectory.jsonl")
            self.assertEqual(trajectory[0]["action"], "select")
            self.assertEqual(trajectory[0]["arguments"]["text"], "Newest")
            self.assertEqual(trajectory[0]["arguments"]["target"]["ref"], "e3")
            self.assertEqual(trajectory[1]["arguments"]["seconds"], 1.5)

    def test_back_is_exported_as_standard_browser_history_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            self.make_step(
                run_dir,
                1,
                action={"action": "back"},
                thought="Return to the previous page.",
            )

            report = runner.generate_trajectory_artifacts(run_dir)

            self.assertEqual(report["status"], "complete")
            trajectory = self.read_jsonl(run_dir / "trajectory.jsonl")
            websurfer = self.read_jsonl(run_dir / "web_surfer.log")
            self.assertEqual(trajectory[0]["action"], "key")
            self.assertEqual(trajectory[0]["arguments"]["key"], "ALT+LEFT")
            self.assertEqual(websurfer[0]["action"], "key")
            self.assertEqual(websurfer[0]["arguments"]["key"], "ALT+LEFT")

    def test_action_schema_requires_distinct_thought(self) -> None:
        self.assertIn("thought", runner.ACTION_SCHEMA["required"])
        self.assertIn("memory", runner.ACTION_SCHEMA["required"])
        self.assertNotEqual(
            runner.ACTION_SCHEMA["properties"]["thought"],
            runner.ACTION_SCHEMA["properties"]["memory"],
        )


if __name__ == "__main__":
    unittest.main()
