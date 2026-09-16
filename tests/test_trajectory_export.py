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
    def write_state(self, run_dir: Path, number: int, url: str) -> Path:
        state_dir = run_dir / "steps" / f"step_{number:03d}"
        state_dir.mkdir(parents=True)
        runner.write_json(
            state_dir / "dom.json",
            {"result": {"snapshot": {"url": url, "nodes": []}}},
        )
        return state_dir

    def write_action(self, state_dir: Path, number: int) -> dict[str, Any]:
        record: dict[str, Any] = {
            "step": number,
            "next_state": number + 1,
            "model_turn": number,
            "started_at": "2026-08-10T05:45:01.071Z",
            "completed_at": "2026-08-10T05:45:01.171Z",
            "action": {"action": "navigate", "url": "https://example.test/next"},
            "thought": "Open the public page.",
            "target": None,
            "coordinate_capture": None,
            "action_driver": "agent-browser",
            "action_result": {"success": True, "data": {}},
            "action_error": None,
            "action_succeeded": True,
        }
        runner.write_json(state_dir / "action.json", record)
        return record

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_export_uses_adjacent_states_without_duplicate_state_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            first = self.write_state(run_dir, 1, "https://example.test/start")
            self.write_state(run_dir, 2, "https://example.test/next")
            action = self.write_action(first, 1)
            manifest = {
                "task_id": "fixture",
                "status": "running",
                "states": [{"state": 1}, {"state": 2}],
                "steps": [action],
            }
            final, report = runner.finalize_recording_artifacts(
                run_dir,
                manifest,
                {"status": "success", "final_answer": "done", "model_turn": 2},
            )
            self.assertEqual(final["recorded_steps"], 1)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["captured_states"], 2)
            row = self.read_jsonl(run_dir / "trajectory.jsonl")[0]
            self.assertEqual(row["state_url"], "https://example.test/start")
            self.assertEqual(row["next_state_url"], "https://example.test/next")
            self.assertEqual(
                set(row),
                {
                    "schema_version", "task_id", "action_number", "step",
                    "source_step", "next_step", "timestamp", "thought",
                    "action", "arguments", "state_url", "next_state_url",
                    "execution_status",
                },
            )
            self.assertFalse((first / "before").exists())
            self.assertFalse((first / "after").exists())

    def test_error_before_first_action_writes_empty_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            manifest = {"task_id": "fixture", "status": "running", "states": [], "steps": []}
            final, report = runner.finalize_recording_artifacts(
                run_dir,
                manifest,
                {"status": "failure", "final_answer": "CDP connection failed", "model_turn": None},
                manifest_status="error",
                error="CDP connection failed",
            )
            self.assertEqual(final["recorded_steps"], 0)
            self.assertEqual(report["status"], "complete")
            self.assertEqual((run_dir / "trajectory.jsonl").read_text(), "")
            self.assertEqual((run_dir / "web_surfer.log").read_text(), "")


if __name__ == "__main__":
    unittest.main()
