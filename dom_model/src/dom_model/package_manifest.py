"""Self-contained source receipt with no dependency on another verifier tree."""

from __future__ import annotations

import hashlib
from pathlib import Path


def source_receipt() -> dict[str, object]:
    root = Path(__file__).resolve(strict=True).parent
    files = sorted([*root.rglob("*.py"), *root.rglob("*.md")], key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return {"package": "dom_model", "root": str(root), "files": len(files), "sha256": digest.hexdigest()}

