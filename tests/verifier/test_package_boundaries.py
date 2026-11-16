from __future__ import annotations

import ast
from importlib.util import resolve_name
import subprocess
import sys
from pathlib import Path

import pytest

from w8bench.verifier.package_manifests import require_local_packages


ROOT = Path(__file__).resolve().parents[2]


def _module_imports(path: Path, package_name: str) -> set[str]:
    found: set[str] = set()
    sources = [path] if path.is_file() else path.rglob("*.py")
    for source in sources:
        relative_parent = source.relative_to(path).parent.parts
        package = ".".join((package_name, *relative_parent))
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = (
                    resolve_name("." * node.level + (node.module or ""), package)
                    if node.level else node.module
                )
                if module:
                    found.add(module)
                    found.update(f"{module}.{alias.name}" for alias in node.names if alias.name != "*")
    return found


def _forbidden_imports(imports: set[str], prefixes: set[str]) -> set[str]:
    return {name for name in imports
        if any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)}


def test_both_local_packages_match_fixed_manifests():
    receipt = require_local_packages()
    assert set(receipt) == {"screenshot_verifier", "dom_model"}
    assert all(item["file_count"] > 0 for item in receipt.values())


def test_packages_do_not_import_each_other_or_protected_runtime():
    forbidden_common = {
        "benchmarks", "dom_diff_text", "fara", "ms_paper_execution", "scripts", "webeval",
    }
    for package, counterpart, alternate in (
        ("screenshot_verifier", "dom_model", "dom_model"),
        ("dom_model", "screenshot_verifier", "dom_diff"),
    ):
        imports = _module_imports(ROOT / "w8bench/verifier" / package, f"w8bench.verifier.{package}")
        assert not _forbidden_imports(imports, forbidden_common | {
            counterpart, alternate, f"w8bench.verifier.{counterpart}",
        })
    for path, package in (
        (ROOT / "w8bench/verifier/clients", "w8bench.verifier.clients"),
        (ROOT / "w8bench/verifier/models.py", "w8bench.verifier"),
        (ROOT / "w8bench/verifier/rubric_agent.py", "w8bench.verifier"),
        (ROOT / "w8bench/verifier/rubric_scoring.py", "w8bench.verifier"),
        (ROOT / "w8bench/verifier/trajectory.py", "w8bench.verifier"),
        (ROOT / "w8bench/verifier/validity.py", "w8bench.verifier"),
        (ROOT / "w8bench/verifier/error_taxonomy.py", "w8bench.verifier"),
    ):
        imports = _module_imports(path, package)
        assert not _forbidden_imports(imports, forbidden_common | {
            "w8bench.verifier.dom_model", "w8bench.verifier.screenshot_verifier",
        })


@pytest.mark.parametrize("statement,expected", [
    ("import w8bench.verifier.dom_model.models", "w8bench.verifier.dom_model.models"),
    ("from w8bench.verifier.dom_model import models", "w8bench.verifier.dom_model"),
    ("from w8bench.verifier import dom_model", "w8bench.verifier.dom_model"),
    ("from ..dom_model import models", "w8bench.verifier.dom_model"),
    ("from .. import dom_model", "w8bench.verifier.dom_model"),
    ("import benchmarks.runner", "benchmarks.runner"),
])
def test_import_scan_detects_absolute_and_relative_dependencies(tmp_path, statement, expected):
    (tmp_path / "probe.py").write_text(statement)
    imports = _module_imports(tmp_path, "w8bench.verifier.screenshot_verifier")
    assert expected in imports
    assert expected in _forbidden_imports(imports, {"w8bench.verifier.dom_model", "benchmarks"})


def test_import_scan_allows_nested_dependencies_within_the_package(tmp_path):
    package = tmp_path / "nested"
    package.mkdir()
    (package / "__init__.py").write_text("from . import messages\nfrom ..models import Task\n")
    imports = _module_imports(tmp_path, "w8bench.verifier.screenshot_verifier")
    assert "w8bench.verifier.screenshot_verifier.nested.messages" in imports
    assert "w8bench.verifier.screenshot_verifier.models" in imports
    assert _forbidden_imports(imports, {"w8bench.verifier.dom_model", "benchmarks"}) == set()


def test_packages_have_no_symlinks():
    for package in (ROOT / "w8bench/verifier/screenshot_verifier", ROOT / "w8bench/verifier/dom_model",
                    ROOT / "w8bench/verifier/clients"):
        assert not [path for path in package.rglob("*") if path.is_symlink()]


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
