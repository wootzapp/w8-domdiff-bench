from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dom_model.control import canonical_sha256


RUBRIC = {
    "items": [
        {
            "criterion": "The saved value is visible in the final state",
            "description": "The UI explicitly shows the value Saved.",
            "max_points": 7,
            "justification": "",
            "earned_points": "",
        },
        {
            "criterion": "No page error is shown",
            "description": "The final browser state has no explicit error.",
            "max_points": 3,
            "justification": "",
            "earned_points": "",
        },
    ]
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def pair_factory(tmp_path):
    def make(*, sidecars: bool = True, metrics: bool = True):
        staged = tmp_path / "staged"
        dom = staged / "data-new-dom-model" / "task1"
        dom.mkdir(parents=True)
        task = {
            "task_id": "internal-task-1",
            "confirmed_task": "Set the example value and save it.",
            "website": "https://example.test/start",
        }
        _write_json(dom / "task_data.json", task)
        dom_event = {
            "action": "left_click",
            "url": "https://example.test/done",
            "arguments": {
                "action": "left_click",
                "ref": "save-button",
                "target": {"role": "button", "name": "Save"},
                "thoughts": "Save the value",
            },
        }
        (dom / "web_surfer.log").write_text(json.dumps(dom_event) + "\n", encoding="utf-8")
        _write_json(
            dom / "final_answer.json",
            {"final_answer": "Saved", "is_aborted": False, "token_usage": {}},
        )
        (dom / "dom_model0.txt").write_text(
            "URL: https://example.test/start\n"
            "Title: Example\n"
            "Snapshot: returnedNodes=2 groups=1 truncated=false\n"
            "=== VISIBLE CONTENT ===\n"
            "[save-button] role=button name=Save value=Ready\n"
            "Dialog: none\n",
            encoding="utf-8",
        )
        (dom / "dom_model1.txt").write_text(
            "URL: https://example.test/done\n"
            "Title: Example Saved\n"
            "Snapshot: returnedNodes=3 groups=1 truncated=false\n"
            "=== VISIBLE CONTENT ===\n"
            "Status: Saved\n"
            "[save-button] role=button name=Save value=Saved\n"
            "Error: none\n",
            encoding="utf-8",
        )
        rubric_path = tmp_path / "experiment" / "rubrics" / "task1.json"
        _write_json(rubric_path, {"task_id": task["task_id"], "precomputed_rubric": RUBRIC})
        if sidecars:
            _write_json(dom / "task_data_with_canonical_rubric.json", {**task, "precomputed_rubric": RUBRIC})
        metrics_path = tmp_path / "experiment" / "rubrics" / "task1_generation_metrics.json"
        if metrics:
            _write_json(
                metrics_path,
                {
                    "phase": "A",
                    "origin": "validated_import",
                    "task_id": task["task_id"],
                    "frozen_rubric_sha256": canonical_sha256(RUBRIC),
                    "criterion_count": 2,
                    "criterion_denominator": 10.0,
                    "criteria": [item["criterion"] for item in RUBRIC["items"]],
                    "maximum_points": [7.0, 3.0],
                    "rubric_generation_calls": 0,
                    "token_usage": {"combined": {"total_tokens": 0}},
                },
            )
        config = tmp_path / "endpoints"
        _write_json(
            config / "gpt.json",
            {"CHAT_COMPLETION_PROVIDER": "openai", "CHAT_COMPLETION_KWARGS_JSON": {"model": "gpt-5.2"}},
        )
        _write_json(
            config / "o4.json",
            {"CHAT_COMPLETION_PROVIDER": "openai", "CHAT_COMPLETION_KWARGS_JSON": {"model": "o4-mini"}},
        )
        return {
            "staged": staged,
            "dom": dom,
            "rubric": rubric_path,
            "metrics": metrics_path,
            "config": config,
            "task": task,
        }

    return make


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in {".venv", "__pycache__", ".pytest_cache", ".git"} for part in path.parts):
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()

