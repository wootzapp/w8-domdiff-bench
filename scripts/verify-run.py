#!/usr/bin/env python3
"""Audit one recorded run for DOM-diff and step-continuity regressions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


CONTINUITY_FILES = ("dom.json", "dom_full.txt", "dom_model.txt", "screenshot.png")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def top_cause(record: dict[str, Any]) -> str:
    compression = record.get("compression") if isinstance(record.get("compression"), dict) else {}
    totals = record.get("totals") if isinstance(record.get("totals"), dict) else {}
    scores = {
        "path_shift": int(compression.get("relocated_nodes_suppressed") or 0),
        "subtree_cascade": int(compression.get("subtree_text_changes_ignored") or 0),
        "no_collapse": max(
            0,
            int(totals.get("added") or 0)
            + int(totals.get("removed") or 0)
            - int(compression.get("collapsed_descendants") or 0),
        ),
        "repeated_group": int(compression.get("repeated_group_members_condensed") or 0),
    }
    cause, score = max(scores.items(), key=lambda item: item[1])
    return cause if score else "entry_payload"


def verify_run(run_dir: Path, byte_threshold: int) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    step_dirs = sorted(path for path in (run_dir / "steps").glob("step_*") if path.is_dir())
    issues: list[dict[str, Any]] = []
    known_gaps: list[dict[str, Any]] = []
    checked = 0
    previous_after: Path | None = None

    for step_dir in step_dirs:
        relative_step = str(step_dir.relative_to(run_dir))
        diff_path = step_dir / "dom_diff.json"
        if not diff_path.exists():
            issues.append({"kind": "missing_diff", "step": relative_step})
            previous_after = step_dir / "after"
            continue
        record = load_object(diff_path)
        checked += 1
        line_count = len(diff_path.read_text(encoding="utf-8").splitlines())
        byte_count = diff_path.stat().st_size
        if byte_count > byte_threshold:
            issues.append(
                {
                    "kind": "oversized_diff",
                    "step": relative_step,
                    "lines": line_count,
                    "bytes": byte_count,
                    "byte_threshold": byte_threshold,
                    "top_contributing_cause": top_cause(record),
                }
            )

        compression = record.get("compression") if isinstance(record.get("compression"), dict) else {}
        collapse_percent = float(compression.get("max_collapse_document_percent") or 0)
        if collapse_percent > 60:
            issues.append(
                {
                    "kind": "over_collapse",
                    "step": relative_step,
                    "document_percent": collapse_percent,
                    "collapse_roots": compression.get("collapse_roots", []),
                }
            )

        before_shot = step_dir / "before" / "screenshot.png"
        after_shot = step_dir / "after" / "screenshot.png"
        screenshots_differ = (
            before_shot.exists()
            and after_shot.exists()
            and digest(before_shot) != digest(after_shot)
        )
        action_type = str(record.get("action_type") or "").lower()
        action_path = step_dir / "action.json"
        action_record = load_object(action_path) if action_path.exists() else {}
        verification = (
            action_record.get("action_verification")
            if isinstance(action_record.get("action_verification"), dict)
            else {}
        )
        if (
            int(record.get("change_count") or 0) == 0
            and screenshots_differ
            and action_type != "scroll"
        ):
            finding = {
                "step": relative_step,
                "action_type": action_type or None,
            }
            if (
                action_type in {"fill", "type", "select"}
                and verification.get("status") == "verified"
            ):
                known_gaps.append(
                    {
                        "kind": "verified_live_control_state_outside_semantic_dom_diff",
                        **finding,
                    }
                )
            else:
                issues.append(
                    {
                        "kind": "visual_change_without_semantic_diff",
                        **finding,
                    }
                )

        if previous_after is not None:
            for name in CONTINUITY_FILES:
                previous_file = previous_after / name
                current_file = step_dir / "before" / name
                if not previous_file.exists() or not current_file.exists():
                    issues.append(
                        {
                            "kind": "continuity_file_missing",
                            "step": relative_step,
                            "file": name,
                        }
                    )
                elif digest(previous_file) != digest(current_file):
                    issues.append(
                        {
                            "kind": "step_continuity_mismatch",
                            "step": relative_step,
                            "file": name,
                        }
                    )
        previous_after = step_dir / "after"

    return {
        "run_directory": str(run_dir),
        "steps_found": len(step_dirs),
        "diffs_checked": checked,
        "byte_threshold": byte_threshold,
        "issue_count": len(issues),
        "issues": issues,
        "known_gap_count": len(known_gaps),
        "known_gaps": known_gaps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--byte-threshold", type=int, default=500 * 1024)
    parser.add_argument("--json", action="store_true", help="Emit the full report as JSON")
    args = parser.parse_args(argv)
    report = verify_run(args.run_directory, args.byte_threshold)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"checked={report['diffs_checked']} issues={report['issue_count']} "
            f"known_gaps={report['known_gap_count']} byte_threshold={report['byte_threshold']}"
        )
        for issue in report["issues"]:
            print(json.dumps(issue, ensure_ascii=False, sort_keys=True))
        for gap in report["known_gaps"]:
            print(json.dumps(gap, ensure_ascii=False, sort_keys=True))
    return 1 if report["issue_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
