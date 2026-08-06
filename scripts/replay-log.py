#!/usr/bin/env python3
"""Print a readable trajectory from a v3 task-recorder log.jsonl."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_lines(path: Path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            yield {"event": "invalid_json", "raw": raw}


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay task-recorder log.jsonl as a readable trajectory")
    parser.add_argument("task_dir", help="Path to tasks/<task-id> or a log.jsonl file")
    args = parser.parse_args()
    path = Path(args.task_dir)
    log_path = path if path.name == "log.jsonl" else path / "log.jsonl"
    if not log_path.exists():
        raise SystemExit(f"log not found: {log_path}")
    for item in load_lines(log_path):
        event = item.get("event")
        step = item.get("step")
        prefix = f"step {int(step):03d}: " if isinstance(step, int) else ""
        if event == "model_response":
            action = item.get("action", {})
            print(prefix + "model -> " + json.dumps(action, ensure_ascii=False))
        elif event == "action_performed":
            print(prefix + "performed -> " + json.dumps(item.get("action", {}), ensure_ascii=False))
        elif event == "action_error":
            print(prefix + "action error -> " + json.dumps(item.get("error", {}), ensure_ascii=False))
        elif event == "step_complete":
            outcome = item.get("outcome", {})
            print(prefix + f"complete status={item.get('status')} progress={outcome.get('made_visible_progress')}")
        elif event == "step_timeout":
            print(prefix + f"timeout after {item.get('timeout_seconds')}s")
        elif event == "run_finished":
            print(f"run finished status={item.get('status')} reason={item.get('reason','')} answer={item.get('final_answer','')}")
        elif event in {"chromiumrl_timeout", "chromiumrl_unavailable", "observation_fallback", "capture_degraded", "javascript_dialog_dismissed", "renderer_crashed", "warning", "target_switched", "session_rebound"}:
            print(prefix + event + " -> " + json.dumps({k:v for k,v in item.items() if k not in {'ts','event','step'}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
