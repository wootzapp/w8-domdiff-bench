#!/usr/bin/env python3
"""Run a manual or catalog-defined browser task in a chosen directory."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

# Local runner exports reused here so validation and environment handling have
# one canonical implementation across direct and wrapper-based invocations.
from runner import DEFAULT_NOVNC_URL, load_env, safe_task_id
# Shared exception avoids defining a second CLI-only error hierarchy.
from recorder_errors import RunnerError


ROOT = Path(__file__).resolve().parent
# Local runner entry point receives the validated task definition assembled here.
RUNNER = ROOT / "runner.py"
# The public command refers only to a task selector. This backend URL supplies
# the JSONL catalog and may be replaced through TASK_CATALOG_URL without changing
# the command interface or recorder behavior.
DEFAULT_TASK_CATALOG_URL = (
    "https://huggingface.co/datasets/ishagarg1103/browser-agent-tasks/"
    "resolve/main/tasks.jsonl"
)
RUNTIME_ROOT = ROOT / ".runtime"
ACTIVE_RUN_PATH = RUNTIME_ROOT / "active-run.json"
TRANSITION_LOCK_PATH = RUNTIME_ROOT / "task-transition.lock"
DEFAULT_STOP_TIMEOUT_SECONDS = 15.0
# This grace period lets the old runner flush its manifest before SIGKILL; the
# CLI exposes an override for unusually slow filesystems.


def process_start_ticks(pid: int) -> int | None:
    """Return Linux's process start-time token, which protects against PID reuse."""
    try:
        value = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        fields_after_command = value[value.rfind(")") + 2 :].split()
        return int(fields_after_command[19])
    except (OSError, ValueError, IndexError):
        return None


def process_command(pid: int) -> list[str]:
    """Read a process argv from /proc, returning an empty list if it vanished."""
    try:
        value = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", errors="replace") for part in value.split(b"\0") if part]


def read_active_run(path: Path = ACTIVE_RUN_PATH) -> dict[str, Any] | None:
    """Load the active-run ownership record; malformed or missing JSON is stale."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def owned_process_group(record: dict[str, Any]) -> tuple[int, int] | None:
    """Validate that a PID file still names this project's isolated runner group."""
    try:
        pid = int(record["pid"])
        pgid = int(record["pgid"])
        expected_start = int(record["process_start_ticks"])
    except (KeyError, TypeError, ValueError):
        return None
    if pid <= 1 or pgid != pid or process_start_ticks(pid) != expected_start:
        return None
    try:
        if os.getpgid(pid) != pgid:
            return None
    except ProcessLookupError:
        return None
    command = process_command(pid)
    if str(RUNNER) not in command:
        return None
    return pid, pgid


def wait_for_process_exit(pid: int, timeout: float) -> bool:
    """Poll until a PID exits or the bounded shutdown timeout expires."""
    deadline = time.monotonic() + max(0.0, timeout)
    while process_start_ticks(pid) is not None and time.monotonic() < deadline:
        time.sleep(0.1)
    return process_start_ticks(pid) is None


def stop_previous_run(
    path: Path = ACTIVE_RUN_PATH,
    *,
    timeout: float = DEFAULT_STOP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Stop only the validated prior runner process group, never an unrelated PID."""
    record = read_active_run(path)
    if record is None:
        return {"status": "none"}
    owned = owned_process_group(record)
    if owned is None:
        path.unlink(missing_ok=True)
        return {"status": "stale_record_removed", "record": record}
    pid, pgid = owned
    os.killpg(pgid, signal.SIGTERM)
    if wait_for_process_exit(pid, timeout):
        path.unlink(missing_ok=True)
        return {"status": "stopped", "pid": pid, "run_id": record.get("run_id")}
    os.killpg(pgid, signal.SIGKILL)
    wait_for_process_exit(pid, 2.0)
    path.unlink(missing_ok=True)
    return {
        "status": "killed_after_timeout",
        "pid": pid,
        "run_id": record.get("run_id"),
        "timeout_seconds": timeout,
    }


@contextmanager
def task_transition_lock(path: Path = TRANSITION_LOCK_PATH) -> Iterator[None]:
    """Serialize task handoff so concurrent CLI starts cannot race ownership."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_active_run(record: dict[str, Any], path: Path = ACTIVE_RUN_PATH) -> None:
    """Atomically publish the current runner's PID, start token, and run id."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def clear_active_run(pid: int, path: Path = ACTIVE_RUN_PATH) -> None:
    """Remove ownership only when the caller still owns the recorded PID."""
    record = read_active_run(path)
    try:
        recorded_pid = int(record.get("pid")) if record is not None else None
    except (TypeError, ValueError):
        recorded_pid = None
    if recorded_pid == pid:
        path.unlink(missing_ok=True)


def ensure_browser_service(env_file: Path) -> None:
    """Start the existing browser container without recreating its profile."""
    command = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "up",
        "-d",
        "--no-recreate",
        "--wait",
        "wootz-desktop",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RunnerError(f"could not start persistent browser service: {detail}")


def task_name_slug(value: str) -> str:
    """Create a bounded filesystem-safe task-name component or fail if empty."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise RunnerError("task name must contain at least one letter or digit")
    return slug[:48].rstrip("-")


def validate_task_definition(
    instruction: str,
    start_url: str,
    *,
    model: str = "",
) -> dict[str, str]:
    """Validate a non-empty instruction and absolute HTTP(S) starting URL."""
    task = instruction.strip()
    if not task:
        raise RunnerError("--task must contain an instruction")
    url = start_url.strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RunnerError("--start-url must be an absolute HTTP(S) URL")
    return {"instruction": task, "start_url": url, "model": model.strip()}


def parse_task_catalog(payload: str, *, source: str) -> list[dict[str, Any]]:
    """Parse task objects from JSONL and reject malformed or duplicate IDs."""
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, raw in enumerate(payload.splitlines(), start=1):
        # Empty lines are harmless in JSONL, but every non-empty line must be a
        # complete independent task object.
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RunnerError(
                f"task catalog {source} contains invalid JSON on line {line_number}: {error}"
            ) from error
        if not isinstance(row, dict):
            raise RunnerError(
                f"task catalog {source} line {line_number} is not a JSON object"
            )
        task_id = str(row.get("task_id", "")).strip()
        if not task_id:
            raise RunnerError(
                f"task catalog {source} line {line_number} has no task_id"
            )
        normalized = task_id.casefold()
        if normalized in seen_ids:
            raise RunnerError(f"task catalog {source} contains duplicate task_id {task_id!r}")
        seen_ids.add(normalized)
        rows.append(row)
    if not rows:
        raise RunnerError(f"task catalog {source} contains no task rows")
    return rows


def numeric_task_selector(value: str) -> int | None:
    """Extract a positive numeric alias from forms such as 1 or task1."""
    match = re.fullmatch(r"(?:(?:browser[_-]?)?task[_-]?)?0*(\d+)", value.strip(), re.I)
    if not match:
        return None
    number = int(match.group(1))
    return number if number > 0 else None


def select_catalog_task(
    rows: list[dict[str, Any]], selector: str
) -> dict[str, Any]:
    """Select an exact task ID or one unambiguous trailing-number alias."""
    requested = selector.strip()
    # Exact IDs take precedence so a catalog's own naming remains authoritative.
    exact = [
        row
        for row in rows
        if str(row.get("task_id", "")).strip().casefold() == requested.casefold()
    ]
    if len(exact) == 1:
        return exact[0]
    # Short numeric aliases are accepted only when exactly one catalog ID ends
    # in that number; ambiguous catalogs fail instead of choosing by row order.
    number = numeric_task_selector(requested)
    numbered = []
    if number is not None:
        for row in rows:
            task_id = str(row.get("task_id", "")).strip()
            suffix = re.search(r"(\d+)$", task_id)
            if suffix and int(suffix.group(1)) == number:
                numbered.append(row)
    if len(numbered) == 1:
        return numbered[0]
    if len(numbered) > 1:
        matches = ", ".join(str(row.get("task_id")) for row in numbered)
        raise RunnerError(
            f"task selector {selector!r} is ambiguous: {matches}"
        )
    raise RunnerError(f"task catalog has no task matching selector {selector!r}")


def catalog_task_instruction(row: dict[str, Any]) -> str:
    """Combine goal, stopping condition, and constraints into one agent prompt."""
    instruction = str(row.get("instruction", "")).strip()
    stopping_condition = str(row.get("stopping_condition", "")).strip()
    raw_constraints = row.get("constraints")
    constraints = (
        [str(item).strip() for item in raw_constraints if str(item).strip()]
        if isinstance(raw_constraints, list)
        else []
    )
    # Preserve catalog order and wording while making each contract component
    # explicit to the action model.
    sections = [instruction]
    if stopping_condition:
        sections.append(f"Stopping condition: {stopping_condition}")
    if constraints:
        sections.append("Constraints:\n" + "\n".join(f"- {item}" for item in constraints))
    return "\n\n".join(section for section in sections if section)


def fetch_catalog_task(
    catalog_url: str,
    selector: str,
    *,
    token: str = "",
) -> dict[str, str]:
    """Fetch one task from the configured remote JSONL catalog.

    The complete small catalog is downloaded for each invocation and is not
    cached, so a command always reflects the configured remote source. Standard
    HTTP redirects are handled by urllib. A token is sent only when configured.
    """
    url = catalog_url.strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RunnerError("task catalog URL must be an absolute HTTP(S) URL")
    headers = {"User-Agent": "task-recorder-dom-diff/1"}
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, UnicodeDecodeError) as error:
        raise RunnerError(f"could not fetch task catalog {url}: {error}") from error
    # Parsing and selection are separate pure functions so malformed catalogs
    # and alias collisions can be tested without making a network request.
    row = select_catalog_task(parse_task_catalog(payload, source=url), selector)
    definition = validate_task_definition(
        catalog_task_instruction(row),
        str(row.get("start_url", "")),
    )
    definition.update(
        {
            "source_task_id": str(row.get("task_id", "")).strip(),
            "task_name": str(row.get("category", "")).strip(),
            "source_catalog": url,
        }
    )
    return definition


def unique_run_id(
    task_id: str,
    task_name: str,
    output_dir: Path,
    *,
    timestamp: str | None = None,
) -> str:
    """Build a timestamped run id and suffix collisions instead of overwriting."""
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = safe_task_id(f"{task_id}-{task_name_slug(task_name)}-{stamp}")
    candidate = base
    suffix = 2
    while (output_dir / candidate).exists():
        candidate = safe_task_id(f"{base}-{suffix}")
        suffix += 1
    return candidate


def build_runner_command(
    definition: dict[str, Any],
    *,
    task_id: str,
    task_name: str,
    run_id: str,
    output_dir: Path,
    env_file: Path,
    allow_human_intervention: bool,
    novnc_url: str,
    model: str = "",
    max_steps: int = 80,
) -> list[str]:
    """Translate CLI inputs into the single authoritative runner invocation."""
    command = [
        sys.executable,
        str(RUNNER),
        "--env-file",
        str(env_file),
        "--task",
        str(definition["instruction"]),
        "--task-id",
        run_id,
        "--source-task-id",
        str(definition.get("source_task_id") or task_id),
        "--task-name",
        task_name,
        "--start-url",
        str(definition["start_url"]),
        "--output-dir",
        str(output_dir),
        "--novnc-url",
        novnc_url,
        "--max-steps",
        str(max_steps),
    ]
    if allow_human_intervention:
        command.append("--allow-human-intervention")
    selected_model = model.strip() or str(definition.get("model") or "").strip()
    if selected_model:
        command.extend(["--model", selected_model])
    if definition.get("source_catalog"):
        command.extend(["--source-catalog", str(definition["source_catalog"])])
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the generic task launcher options without starting any process."""
    parser = argparse.ArgumentParser(
        description="Run a configured catalog task or a manually supplied task"
    )
    parser.add_argument("task_id", help="run ID and configured-catalog task selector")
    parser.add_argument(
        "task_name",
        nargs="?",
        help="human-readable run name; defaults to task_id",
    )
    parser.add_argument("--task", help="complete manual task instruction and constraints")
    parser.add_argument("--start-url", help="absolute HTTP(S) starting URL for a manual task")
    parser.add_argument("--catalog-url", help=argparse.SUPPRESS)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="parent directory for this task's timestamped run",
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--novnc-url")
    parser.add_argument(
        "--no-human-intervention",
        action="store_true",
        help="do not permit the runner to pause for manual challenges",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the planned run without starting it",
    )
    parser.add_argument(
        "--no-browser-start",
        action="store_true",
        help="require an already-running browser instead of starting the compose service",
    )
    parser.add_argument(
        "--previous-run-stop-timeout",
        type=float,
        default=DEFAULT_STOP_TIMEOUT_SECONDS,
        help="seconds to allow a previous task runner to shut down before it is killed",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate a task, preserve the browser, replace an old runner, and wait."""
    args = parse_args(argv)
    task_id = safe_task_id(args.task_id.strip())
    if args.max_steps <= 0:
        raise RunnerError("--max-steps must be positive")
    if args.previous_run_stop_timeout < 0:
        raise RunnerError("--previous-run-stop-timeout must not be negative")

    load_env(args.env_file)
    # Supplying either manual field selects manual mode and requires both. With
    # neither field, the positional task id is resolved through the catalog.
    manual_task = args.task is not None or args.start_url is not None
    if manual_task:
        if not args.task or not args.start_url:
            raise RunnerError("manual tasks require both --task and --start-url")
        definition = validate_task_definition(args.task, args.start_url, model=args.model)
    else:
        catalog_url = (
            args.catalog_url
            or os.environ.get("TASK_CATALOG_URL")
            or DEFAULT_TASK_CATALOG_URL
        )
        definition = fetch_catalog_task(
            catalog_url,
            task_id,
            token=os.environ.get("TASK_CATALOG_TOKEN", os.environ.get("HF_TOKEN", "")),
        )
    task_name = (
        args.task_name.strip()
        if args.task_name
        else str(definition.get("task_name") or task_id).strip()
    )
    output_dir = args.output_dir.resolve()
    run_id = unique_run_id(task_id, task_name, output_dir)
    novnc_url = args.novnc_url or os.environ.get("RUNNER_NOVNC_URL", DEFAULT_NOVNC_URL)
    command = build_runner_command(
        definition,
        task_id=task_id,
        task_name=task_name,
        run_id=run_id,
        output_dir=output_dir,
        env_file=args.env_file.resolve(),
        allow_human_intervention=not args.no_human_intervention,
        novnc_url=novnc_url,
        model=args.model,
        max_steps=args.max_steps,
    )

    print(f"Task id: {task_id}")
    print(f"Task name: {task_name}")
    print(f"Start URL: {definition['start_url']}")
    print(f"Output: {output_dir / run_id}")
    print(
        "Human intervention: "
        + ("enabled" if not args.no_human_intervention else "disabled")
    )
    if args.dry_run:
        print("Dry run complete; browser task was not started.")
        return 0
    if not args.no_browser_start:
        ensure_browser_service(args.env_file.resolve())

    process: subprocess.Popen[str] | None = None
    with task_transition_lock():
        takeover = stop_previous_run(timeout=args.previous_run_stop_timeout)
        if takeover["status"] not in {"none", "stale_record_removed"}:
            print(
                "Previous task process: "
                f"{takeover['status']} "
                f"(run={takeover.get('run_id')}, pid={takeover.get('pid')})"
            )
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            start_new_session=True,
        )
        start_ticks = process_start_ticks(process.pid)
        if start_ticks is None:
            process.terminate()
            raise RunnerError("runner process exited before ownership could be recorded")
        write_active_run(
            {
                "schema_version": 1,
                "pid": process.pid,
                "pgid": process.pid,
                "process_start_ticks": start_ticks,
                "run_id": run_id,
                "task_id": task_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "command": command,
            }
        )

    assert process is not None
    try:
        return process.wait()
    except KeyboardInterrupt:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=args.previous_run_stop_timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return process.wait()
    finally:
        clear_active_run(process.pid)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RunnerError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
