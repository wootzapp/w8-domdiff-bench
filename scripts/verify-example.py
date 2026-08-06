#!/usr/bin/env python3
"""Validate the v7 verifier artifact layout for one task directory."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path


def load_json(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path.read_text(encoding="utf-8"))


def require(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check v7 task-recorder verifier artifact layout")
    parser.add_argument("task_dir", type=Path)
    args = parser.parse_args()
    root = args.task_dir
    errors: list[str] = []
    for name in ("manifest.json", "log.jsonl", "agent_browser_final.json", "VERIFIER.md"):
        require(root / name, errors)
    final = root / "final_state"
    for name in ("dom_full.json.gz", "dom_state.json.gz", "page_state.json", "observation.json"):
        require(final / name, errors)
    steps = sorted(p for p in root.glob("step_*") if p.is_dir())
    if not steps:
        errors.append("missing: at least one step_NNN directory")
    for step in steps:
        for name in ("action.json", "page_state_before.json", "page_state_after.json", "dom_diff.json"):
            require(step / name, errors)
        for name in ("dom_state_before.json.gz", "dom_state_after.json.gz", "after.jpg"):
            require(step / "evidence" / name, errors)
        for name in ("observation_before.json.gz", "observation_after.json.gz", "observation_diff.json"):
            require(step / "agent" / name, errors)
    if (final / "dom_full.json.gz").exists():
        try:
            raw = load_json(final / "dom_full.json.gz")
            nodes = raw.get("nodes", []) if isinstance(raw, dict) else []
            if not isinstance(nodes, list) or not nodes:
                errors.append("final_state/dom_full.json.gz is not a raw saveDOMState object with nodes")
            elif not any(isinstance(n, dict) and isinstance(n.get("keyStyles"), dict) and len(n.get("keyStyles") or {}) >= 10 for n in nodes):
                errors.append("final_state/dom_full.json.gz does not show raw keyStyles objects")
        except Exception as exc:
            errors.append(f"cannot read final_state/dom_full.json.gz: {exc}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {root} has v7 verifier artifacts ({len(steps)} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
