"""Dataset isolation and alignment checks for screenshot verifier tasks."""

from __future__ import annotations

import json
import re
from pathlib import Path


_SCREENSHOT_RE = re.compile(r"^screenshot_?(\d+)\.(?:png|jpe?g|webp)$", re.I)


def discover_screenshots(task_dir: str | Path) -> list[Path]:
    """Find original 0..N states, excluding verifier-created symlink aliases."""
    root = Path(task_dir).resolve(strict=True)
    indexed: dict[int, Path] = {}
    for path in root.iterdir():
        if not path.is_file() or path.is_symlink():
            continue
        match = _SCREENSHOT_RE.fullmatch(path.name)
        if match is None:
            continue
        index = int(match.group(1))
        if index in indexed:
            raise ValueError(f"Duplicate screenshot index {index} in {root}")
        indexed[index] = path
    indices = sorted(indexed)
    if not indices or indices != list(range(len(indices))):
        raise ValueError(f"Screenshots must be contiguous from 0, got {indices}")
    return [indexed[index] for index in indices]


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
    screenshots = discover_screenshots(root)
    if len(screenshots) != actions + 1:
        raise ValueError(
            f"Expected exactly N+1 screenshots for {actions} actions; "
            f"found {len(screenshots)}"
        )
    answers = list(root.glob("*_answer.json"))
    if len(answers) != 1:
        raise ValueError(f"Expected exactly one *_answer.json, found {len(answers)}")
    answer = json.loads(answers[0].read_text(encoding="utf-8"))
    if not isinstance(answer, dict) or not isinstance(answer.get("final_answer"), str):
        raise ValueError("Final answer must contain final_answer text")
    return {"actions": actions, "screenshots": len(screenshots)}
