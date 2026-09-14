"""Dataset isolation and alignment checks for screenshot verifier tasks."""

from __future__ import annotations

import json
import re
from pathlib import Path


_SCREENSHOT_RE = re.compile(r"^screenshot_?(\d+)\.png$")


def preflight_screenshot_task(task_dir: str | Path) -> dict[str, int]:
    root = Path(task_dir).resolve(strict=True)
    logs = [path for path in (root / "web_surfer.log", root / "websurfer.log") if path.is_file()]
    if len(logs) != 1:
        raise ValueError(f"Expected exactly one web surfer log, found {len(logs)}")
    actions = 0
    for line in logs[0].read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if isinstance(event, dict) and event.get("action") is not None:
            actions += 1
    screenshots = sorted(
        path for path in root.iterdir() if path.is_file() and _SCREENSHOT_RE.match(path.name)
    )
    if len(screenshots) not in {actions, actions + 1}:
        raise ValueError(
            f"Expected N or intentional N+1 screenshots for {actions} actions; "
            f"found {len(screenshots)}"
        )
    answers = list(root.glob("*_answer.json"))
    if len(answers) != 1:
        raise ValueError(f"Expected exactly one *_answer.json, found {len(answers)}")
    return {"actions": actions, "screenshots": len(screenshots)}
