"""Named experiment directories shared by recording and evaluation commands."""

import os
import re
from pathlib import Path


def resolve_run_name(value: str | None = None) -> str:
    name = value if value is not None else os.environ.get("W8_RUN_NAME", "run_1")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("Run name must contain letters, digits, underscores or hyphens")
    return name


def run_directory(root: str | Path, run_name: str | None = None) -> Path:
    name = resolve_run_name(run_name)
    root = Path(root)
    return root if root.name == name else root / name
