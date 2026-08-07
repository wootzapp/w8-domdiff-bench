#!/usr/bin/env python3
"""Smoke-test the public dom_diff_schema.py contract against real artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dom_diff_schema import iter_evidence_entries, validate  # noqa: E402


def load(path: str) -> dict:
    candidate = ROOT / path
    if not candidate.exists():
        raise SystemExit(f"missing test fixture: {candidate}")
    return json.loads(candidate.read_text(encoding="utf-8"))


def assert_kind(entries: list[dict], kind: str) -> None:
    if not any(entry.get("kind") == kind for entry in entries):
        raise SystemExit(f"expected evidence kind {kind!r}; got {sorted({entry.get('kind') for entry in entries})}")


def main() -> None:
    same = load("tasks/tests/t1-spa-counter-gpt51-retry-001/step_005/dom_diff.json")
    cross = load("tasks/tests/t2-books-scifi-gpt51-retry-001/step_003/dom_diff.json")
    validate(same)
    validate(cross)
    same_entries = list(iter_evidence_entries(same))
    cross_entries = list(iter_evidence_entries(cross))
    assert_kind(same_entries, "element_changed")
    assert_kind(same_entries, "collapse_root")
    assert_kind(cross_entries, "text_added")
    assert_kind(cross_entries, "text_removed")
    assert_kind(cross_entries, "element_added")
    print("dom_diff_schema fixtures ok")


if __name__ == "__main__":
    main()
