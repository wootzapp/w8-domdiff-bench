#!/usr/bin/env python3
"""Export a verifier bundle from an existing v8 task folder."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def collect(task_dir: Path) -> list[Path]:
    include: list[Path] = []
    for name in ("manifest.json", "log.jsonl", "agent_browser_final.json", "VERIFIER.md"):
        p = task_dir / name
        if p.exists():
            include.append(p)
    final = task_dir / "final_state"
    if final.exists():
        include.extend(sorted(p for p in final.rglob("*") if p.is_file()))
    for step in sorted(p for p in task_dir.glob("step_*") if p.is_dir()):
        for name in ("action.json", "after.jpg", "before.jpg", "dom_after.json.gz", "dom_before.json.gz", "dom_diff.json", "page_state.json", "observation_before.json.gz", "observation_after.json.gz", "observation_diff.json"):
            p = step / name
            if p.exists():
                include.append(p)
    return include


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a verifier bundle zip for a v8 task-recorder run")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    task_dir = args.task_dir
    output = args.output or (task_dir / f"{task_dir.name}_verifier_bundle.zip")
    files = collect(task_dir)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, p.relative_to(task_dir).as_posix())
    print(f"wrote {output} ({output.stat().st_size} bytes, {len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
