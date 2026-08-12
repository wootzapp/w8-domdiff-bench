from __future__ import annotations

import json
from pathlib import Path

import pytest


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def stagehand_task(tmp_path: Path) -> Path:
    root = tmp_path / "sample-task"
    root.mkdir()
    write_json(
        root / "task.json",
        {
            "task_id": "sample-task",
            "task": "Open example.test and enable the Alpha option.",
            "start_url": "about:blank",
            "cdp_url": "ws://secret.invalid",
        },
    )
    write_json(
        root / "final_answer.json",
        {
            "type": "final_answer",
            "message": "Alpha was enabled.",
            "observation": {
                "url": "https://example.test/settings",
                "screenshot": "[Buffer secret]",
                "ariaTree": "duplicate",
            },
        },
    )
    states = [
        ("https://example.test/", "Example", "[1-1] RootWebArea: Example\n  [1-2] link: Settings\n"),
        ("https://example.test/settings", "Settings", "[1-1] RootWebArea: Settings\n  [1-3] checkbox: Alpha [checked]\n"),
        ("https://example.test/settings", "Settings", "[1-1] RootWebArea: Settings\n  [1-3] checkbox: Alpha [checked]\n"),
    ]
    actions = [
        {"action": "goto", "arguments": {"url": "https://example.test/"}},
        {"action": "act", "arguments": {"action": "Enable Alpha"}},
    ]
    for ordinal, (url, title, aria) in enumerate(states, start=1):
        step = root / f"step_{ordinal:03d}"
        step.mkdir()
        (step / "aria.txt").write_text(aria, encoding="utf-8")
        write_json(step / "page_state.json", {
            "url": url, "title": title, "readyState": "complete", "scrollX": 0,
            "scrollY": 0, "viewport": {"width": 1000, "height": 700, "devicePixelRatio": 1},
            "bodyTextPreview": title + " Alpha",
        })
        if ordinal <= len(actions):
            write_json(step / "action.json", actions[ordinal - 1])
            write_json(step / "tool_result.json", {
                "ok": True,
                "result": {"toolName": actions[ordinal - 1]["action"], "output": {
                    "screenshot": "[Buffer forbidden]", "value": "ok"
                }},
            })
    return root
