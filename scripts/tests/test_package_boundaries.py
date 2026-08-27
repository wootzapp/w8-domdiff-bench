from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

from scripts.package_manifests import require_local_packages


ROOT = Path(__file__).resolve().parents[2]


def _top_level_imports(path: Path) -> set[str]:
    found: set[str] = set()
    for source in path.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".", 1)[0])
    return found


def test_both_local_packages_match_fixed_manifests():
    receipt = require_local_packages()
    assert set(receipt) == {"microsoft_verifier", "dom_model"}
    assert all(item["file_count"] > 0 for item in receipt.values())


def test_packages_do_not_import_each_other_or_shared_or_protected_runtime():
    microsoft = _top_level_imports(ROOT / "microsoft_verifier/src")
    dom_model = _top_level_imports(ROOT / "dom_model/src")
    forbidden_common = {"scripts", "benchmarks", "ms_paper_execution"}
    assert not microsoft.intersection(forbidden_common | {"dom_model"})
    assert not dom_model.intersection(
        forbidden_common | {"microsoft_verifier", "dom_diff_text"}
    )


def test_packages_have_no_symlinks():
    for package in (ROOT / "microsoft_verifier", ROOT / "dom_model"):
        assert not [path for path in package.rglob("*") if path.is_symlink()]


def test_each_runner_imports_with_only_its_own_source_path(tmp_path):
    for source, module in (
        (ROOT / "microsoft_verifier/src", "microsoft_verifier.runner"),
        (ROOT / "dom_model/src", "dom_model.runner"),
    ):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(source)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=tmp_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
