"""Named experiment directories shared by recording and evaluation commands."""

import os
import re
from pathlib import Path


TEMPORAL_NAME_PATTERN = re.compile(
    r"(?<!\d)(?:[12]\d{3}[-_](?:0?[1-9]|1[0-2])(?:[-_](?:0?[1-9]|[12]\d|3[01]))?"
    r"|[12]\d{3}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])"
    r"|(?:[01]\d|2[0-3])[-_][0-5]\d[-_][0-5]\d(?:[._-]\d{1,6})?"
    r"|[12]\d{9}(?:\d{3})?)(?!\d)"
)


def resolve_run_name(value: str | None = None) -> str:
    name = value if value is not None else os.environ.get("W8_RUN_NAME", "run1")
    if not re.fullmatch(r"[0-9a-fA-F]{64}(?:_\d+)?(?:\.[A-Za-z0-9]+)?", name) and TEMPORAL_NAME_PATTERN.search(name):
        raise ValueError("Run names must use labels and sequence numbers without dates or times")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("Run name must contain letters, digits, underscores or hyphens")
    return name


def run_directory(root: str | Path, run_name: str | None = None, *, fresh: bool = False, reserve: bool = True, area: str | None = None) -> Path:
    """Resolve a numbered run folder or one recording's sibling output area."""
    if area is not None:
        source = Path(root)
        if area not in {"trajectories", "evaluations", "logs"}:
            raise ValueError("Recording output area must be trajectories, evaluations or logs")
        if source.name.startswith("attempt_") and source.parent.parent.parent.name == "attempts":
            run = source.parents[3]
            relative = Path("attempts") / source.parent.parent.name / source.parent.name / source.name
        elif source.parent.name in {"dom", "screenshot"}:
            run = source.parent.parent
            relative = Path(source.parent.name) / source.name
        else:
            run = source
            relative = Path()
        base = run.parent.parent if relative.parts or run.parent.name == "recordings" else run.parent
        return base / area / run.name / relative
    name = resolve_run_name(run_name)
    root = Path(root)
    if fresh and any(not re.fullmatch(r"[0-9a-fA-F]{64}(?:_\d+)?(?:\.[A-Za-z0-9]+)?", part) and TEMPORAL_NAME_PATTERN.search(part) for part in root.parts):
        raise ValueError("Output folders must use labels and sequence numbers without dates or times")
    directory = root if root.name == name else root / name
    if not fresh:
        return directory
    match = re.fullmatch(r"(.+?)(_?)(\d+)", name)
    prefix, separator, number = (match.group(1), match.group(2), int(match.group(3))) if match else (name, "_", 1)
    while True:
        try:
            if reserve:
                directory.mkdir(parents=True, exist_ok=False)
            elif directory.exists():
                raise FileExistsError(directory)
            return directory
        except FileExistsError:
            number += 1
            directory = directory.parent / f"{prefix}{separator}{number}"
