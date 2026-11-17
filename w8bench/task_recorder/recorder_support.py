"""Shared recorder exception, URL validation, timestamps, and atomic writers."""

from __future__ import annotations

import json
import argparse
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


class RunnerError(RuntimeError):
    """Raised when a task-recording operation cannot safely continue."""


def _finite_float(value: str, *, positive: bool) -> float:
    requirement = "finite and positive" if positive else "finite and nonnegative"
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(f"must be {requirement}") from error
    if not math.isfinite(number) or number < 0 or positive and number == 0:
        raise argparse.ArgumentTypeError(f"must be {requirement}")
    return number


def finite_nonnegative_float(value: str) -> float:
    """Parse a finite delay, including an immediate zero delay."""
    return _finite_float(value, positive=False)


def finite_positive_float(value: str) -> float:
    """Parse a finite timeout with a strictly positive duration."""
    return _finite_float(value, positive=True)


def normalized_http_url(value: str) -> str:
    """Validate a CDP HTTP endpoint and discard any accidental path/query."""
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RunnerError(f"invalid CDP URL: {value!r}")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def clean_dom_text(value: Any) -> str:
    """Normalize whitespace for recorder comparisons and labels."""
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def utc_now() -> str:
    """Return a millisecond-resolution UTC timestamp in JSON-friendly form."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    """Atomically write indented UTF-8 JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_json_line(path: Path, value: Any) -> None:
    """Append one compact JSON object to an audit JSONL stream."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def write_json_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    """Atomically write JSONL so a failed export cannot leave a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    """Atomically replace a UTF-8 text artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
