from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_no_runtime_imports_from_related_verifiers() -> None:
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import fara" not in text
        assert "from fara" not in text
        assert "import webeval" not in text
        assert "from webeval" not in text


def test_pinned_reference_hashes_when_source_is_available() -> None:
    source = os.environ.get("UPSTREAM_VERIFIER_SOURCE")
    if not source:
        pytest.skip("Set UPSTREAM_VERIFIER_SOURCE to audit the read-only upstream checkout")
    lock = json.loads((ROOT / "UPSTREAM_VERIFIER.lock.json").read_text(encoding="utf-8"))
    root = Path(source)
    for relative, expected in lock["protected_files"].items():
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        assert digest == expected
