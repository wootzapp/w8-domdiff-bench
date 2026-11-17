from __future__ import annotations

import subprocess
import sys
from pathlib import Path


from w8bench.verifier.package_manifests import require_local_packages


ROOT = Path(__file__).resolve().parents[2]


def test_both_local_packages_match_fixed_manifests():
    receipt = require_local_packages()
    assert set(receipt) == {"screenshot_verifier", "dom_model"}
    assert all(item["file_count"] > 0 for item in receipt.values())


def test_each_runner_imports_from_the_installed_package(tmp_path):
    for module in (
        "w8bench.verifier.screenshot_verifier.runner",
        "w8bench.verifier.dom_model.runner",
    ):
        completed = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
