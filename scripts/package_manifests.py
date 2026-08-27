"""Fail-closed manifests for the two experiment-local verifier packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = ROOT / "manifests"
PACKAGE_ROOTS = {
    "microsoft_verifier": ROOT / "microsoft_verifier",
    "dom_model": ROOT / "dom_model",
}
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".git", ".venv"}


def tree_receipt(package: str) -> dict[str, Any]:
    root = PACKAGE_ROOTS[package].resolve(strict=True)
    if ROOT.resolve() not in root.parents:
        raise RuntimeError(f"Package escaped benchmarks-2: {root}")
    digest = hashlib.sha256()
    files = 0
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise RuntimeError(f"Verifier packages may not contain symlinks: {path}")
        if not path.is_file():
            continue
        files += 1
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return {
        "package": package,
        "root": str(root),
        "file_count": files,
        "tree_sha256": digest.hexdigest(),
    }


def require_local_package(package: str) -> dict[str, Any]:
    actual = tree_receipt(package)
    manifest_path = MANIFEST_ROOT / f"{package}.json"
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("package", "file_count", "tree_sha256"):
        if actual[key] != expected.get(key):
            raise RuntimeError(
                f"Local {package} package differs from its fixed manifest for {key}: "
                f"{actual[key]!r} != {expected.get(key)!r}"
            )
    return {**actual, "manifest": str(manifest_path.resolve())}


def require_local_packages() -> dict[str, dict[str, Any]]:
    return {name: require_local_package(name) for name in PACKAGE_ROOTS}
