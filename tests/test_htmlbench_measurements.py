from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.summarize_htmlbench_eval import collect_run, grouped_summary  # noqa: E402


class HTMLBenchMeasurementTests(unittest.TestCase):
    def test_collect_run_sums_every_model_call_and_unique_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "initial").mkdir()
            (run / "steps" / "step_001" / "after").mkdir(parents=True)
            manifest = {
                "task_id": "trial",
                "source_task_id": "logical-task",
                "task_name": "logical task",
                "status": "success",
                "created_at": "2026-08-26T12:00:00Z",
                "completed_at": "2026-08-26T12:00:10Z",
                "steps": [{}],
                "htmlbench_eval": {"profile": "baseline"},
            }
            (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            rows = [
                {"model_response": {"usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}},
                {"model_response": {"usage": {"input_tokens": 20, "output_tokens": 3, "total_tokens": 23}}},
            ]
            (run / "decisions.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            for state in (run / "initial", run / "steps" / "step_001" / "after"):
                (state / "dom_model.txt").write_text("abcd", encoding="utf-8")
                (state / "dom.json").write_text(
                    json.dumps({
                        "result": {"snapshot": {
                            "nodes": [{}, {}],
                            "stats": {"rawNodes": 3, "truncated": False},
                        }}
                    }),
                    encoding="utf-8",
                )
            (run / "steps" / "step_001" / "dom_diff.json").write_text(
                json.dumps({"change_count": 5}), encoding="utf-8"
            )
            measured = collect_run(run / "manifest.json")
            groups = grouped_summary([measured])

        self.assertEqual(measured["input_tokens"], 30)
        self.assertEqual(measured["total_tokens"], 35)
        self.assertEqual(measured["model_calls"], 2)
        self.assertEqual(measured["dom_model_bytes"], 8)
        self.assertEqual(measured["captured_nodes"], 4)
        self.assertEqual(measured["diff_changes"], 5)
        self.assertEqual(groups[0]["metrics"]["input_tokens"]["median"], 30.0)


if __name__ == "__main__":
    unittest.main()
