#!/usr/bin/env python3
"""Run one browser task or the complete task catalog in a chosen directory."""

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
from .runner import DEFAULT_NOVNC_URL, load_env, safe_task_id
# Shared exception avoids defining a second CLI-only error hierarchy.
from .recorder_support import RunnerError


ROOT = Path(__file__).resolve().parents[2]
RUNNER_MODULE = "w8bench.task_recorder.runner"
# The public command refers only to a task selector. This backend URL supplies
# the JSONL catalog and may be replaced through TASK_CATALOG_URL without changing
# the command interface or recorder behavior.
DEFAULT_TASK_CATALOG_URL = (
    "https://huggingface.co/datasets/WootzappLab/browser-agent-tasks/"
    "resolve/main/tasks.jsonl"
)
RUNTIME_ROOT = ROOT / ".runtime"
ACTIVE_RUN_PATH = RUNTIME_ROOT / "active-run.json"
TRANSITION_LOCK_PATH = RUNTIME_ROOT / "task-transition.lock"
DEFAULT_STOP_TIMEOUT_SECONDS = 15.0
DEFAULT_PROFILE_TASK_COUNT_PATH = "/home/wootz/.task-recorder-dom-diff-task-count"
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
    if RUNNER_MODULE not in command:
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
    """Start the existing w8-core container without recreating its profile."""
    command = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "up",
        "-d",
        "--no-recreate",
        "--wait",
        "w8-core",
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


def restart_browser_service(env_file: Path) -> None:
    """Restart one managed browser process without recreating its container or profile."""
    ensure_browser_service(env_file)
    command = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "restart",
        "w8-core",
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
        raise RunnerError(f"could not restart browser service at task boundary: {detail}")
    ensure_browser_service(env_file)


def browser_container_cdp_url(container_name: str) -> str:
    """Return the CDP URL for agent-browser running inside w8-core.

    Its loopback address is container-local and must not be used by host-side
    CDP clients such as the recorder's direct ChromiumRL connection.
    """
    completed = subprocess.run(
        [
            "docker",
            "exec",
            container_name,
            "sh",
            "-c",
            'printf "%s" "${CDP_PORT:-9222}"',
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RunnerError(f"could not read w8-core container CDP port: {detail}")
    try:
        port = int(completed.stdout.strip())
    except ValueError as error:
        raise RunnerError("w8-core container CDP_PORT is not an integer") from error
    if not 1 <= port <= 65535:
        raise RunnerError("w8-core container CDP_PORT is outside the valid range")
    return f"http://127.0.0.1:{port}"


def claim_browser_profile_provenance(container_name: str) -> dict[str, Any]:
    """Atomically claim one task slot for this container-lifetime profile."""
    profile_task_count_path = os.environ.get(
        "BROWSER_PROFILE_TASK_COUNT_PATH",
        DEFAULT_PROFILE_TASK_COUNT_PATH,
    )
    inspected = subprocess.run(
        ["docker", "inspect", container_name],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if inspected.returncode != 0:
        detail = inspected.stderr.strip() or inspected.stdout.strip()
        raise RunnerError(f"could not inspect w8-core container provenance: {detail}")
    try:
        values = json.loads(inspected.stdout)
        container = values[0]
        container_id = str(container["Id"])
        container_created_at = str(container["Created"])
    except (json.JSONDecodeError, IndexError, KeyError, TypeError) as error:
        raise RunnerError("docker inspect returned invalid container provenance") from error

    counted = subprocess.run(
        [
            "docker", "exec", container_name, "sh", "-c",
            'path="$1"; test -f "$path" && cat "$path" || printf 0',
            "task-recorder-profile-counter", profile_task_count_path,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if counted.returncode != 0:
        detail = counted.stderr.strip() or counted.stdout.strip()
        raise RunnerError(f"could not read browser profile task count: {detail}")
    try:
        tasks_previously_run = int(counted.stdout.strip() or "0")
    except ValueError as error:
        raise RunnerError("browser profile task count is not an integer") from error
    if tasks_previously_run < 0:
        raise RunnerError("browser profile task count must not be negative")

    next_count = tasks_previously_run + 1
    updated = subprocess.run(
        [
            "docker", "exec", container_name, "sh", "-c",
            'set -eu; path="$1"; value="$2"; umask 077; '
            'printf "%s\n" "$value" > "${path}.tmp"; mv "${path}.tmp" "$path"',
            "task-recorder-profile-counter", profile_task_count_path, str(next_count),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if updated.returncode != 0:
        detail = updated.stderr.strip() or updated.stdout.strip()
        raise RunnerError(f"could not update browser profile task count: {detail}")
    return {
        "container_id": container_id,
        "container_created_at": container_created_at,
        "profile_fresh_at_run_start": tasks_previously_run == 0,
        "tasks_previously_run_in_container": tasks_previously_run,
    }


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


def fetch_task_catalog(catalog_url: str, *, token: str = "") -> list[dict[str, Any]]:
    """Fetch and parse the configured JSONL catalog once per invocation."""
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
    return parse_task_catalog(payload, source=url)


def catalog_task_definition(row: dict[str, Any], catalog_url: str) -> dict[str, str]:
    """Preserve one catalog task's instruction, constraints, and provenance."""
    definition = validate_task_definition(
        catalog_task_instruction(row),
        str(row.get("start_url", "")),
    )
    definition.update(
        {
            "source_task_id": str(row.get("task_id", "")).strip(),
            "task_name": str(row.get("category", "")).strip(),
            "source_catalog": catalog_url.strip(),
        }
    )
    return definition


def fetch_catalog_task(
    catalog_url: str, selector: str, *, token: str = ""
) -> dict[str, str]:
    """Fetch one task by its exact catalog ID or numeric alias."""
    rows = fetch_task_catalog(catalog_url, token=token)
    return catalog_task_definition(select_catalog_task(rows, selector), catalog_url)


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
    post_action_language_redirect: bool = False,
    model: str = "",
    max_steps: int = 80,
) -> list[str]:
    """Translate CLI inputs into the single authoritative runner invocation."""
    command = [
        sys.executable,
        "-m",
        RUNNER_MODULE,
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
    command.append(
        "--post-action-language-redirect"
        if post_action_language_redirect
        else "--no-post-action-language-redirect"
    )
    selected_model = model.strip() or str(definition.get("model") or "").strip()
    if selected_model:
        command.extend(["--model", selected_model])
    if definition.get("source_catalog"):
        command.extend(["--source-catalog", str(definition["source_catalog"])])
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the generic task launcher options without starting any process."""
    parser = argparse.ArgumentParser(
        description="Run one catalog/manual task or every task with --all"
    )
    parser.add_argument("task_id", nargs="?", help="run ID and configured-catalog task selector")
    parser.add_argument(
        "--all",
        action="store_true",
        help="run every catalog task sequentially, continuing after failures",
    )
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
    language_redirect_group = parser.add_mutually_exclusive_group()
    language_redirect_group.add_argument(
        "--post-action-language-redirect",
        dest="post_action_language_redirect",
        action="store_true",
        help="Enable compatibility-mode automatic locale redirects after actions",
    )
    language_redirect_group.add_argument(
        "--no-post-action-language-redirect",
        dest="post_action_language_redirect",
        action="store_false",
        help="Keep post-action locale redirects disabled (the default)",
    )
    parser.set_defaults(post_action_language_redirect=False)
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
    args = parser.parse_args(argv)
    if args.all:
        if any(value is not None for value in (args.task_id, args.task_name, args.task, args.start_url)):
            parser.error("--all cannot be combined with a task selector, task name, --task, or --start-url")
    elif args.task_id is None:
        parser.error("a task selector or --all is required")
    return args


def main(argv: list[str] | None = None) -> int:
    """Validate a task, preserve the browser, replace an old runner, and wait."""
    args = parse_args(argv)
    if args.max_steps <= 0:
        raise RunnerError("--max-steps must be positive")
    if args.previous_run_stop_timeout < 0:
        raise RunnerError("--previous-run-stop-timeout must not be negative")

    load_env(args.env_file)
    catalog_url = (
        args.catalog_url
        or os.environ.get("TASK_CATALOG_URL")
        or DEFAULT_TASK_CATALOG_URL
    )
    token = os.environ.get("TASK_CATALOG_TOKEN", os.environ.get("HF_TOKEN", ""))
    if args.all:
        try:
            return run_all_tasks(args, catalog_url, token=token)
        except KeyboardInterrupt:
            return 130
    task_id = safe_task_id(args.task_id.strip())
    # Supplying either manual field selects manual mode and requires both. With
    # neither field, the positional task id is resolved through the catalog.
    manual_task = args.task is not None or args.start_url is not None
    if manual_task:
        if not args.task or not args.start_url:
            raise RunnerError("manual tasks require both --task and --start-url")
        definition = validate_task_definition(args.task, args.start_url, model=args.model)
    else:
        definition = fetch_catalog_task(
            catalog_url,
            task_id,
            token=token,
        )
    try:
        return run_task(args, definition, task_id=task_id)
    except KeyboardInterrupt:
        return 130


def run_all_tasks(args: argparse.Namespace, catalog_url: str, *, token: str = "") -> int:
    """Run catalog tasks in order using the same task-boundary lifecycle."""
    rows = fetch_task_catalog(catalog_url, token=token)
    results: list[dict[str, Any]] = []
    interrupted = False
    for ordinal, row in enumerate(rows, start=1):
        source_id = str(row["task_id"]).strip()
        print(f"[{ordinal}/{len(rows)}] {source_id}", flush=True)
        result: dict[str, Any] = {"task_id": source_id}
        try:
            task_id = safe_task_id(source_id)
            definition = catalog_task_definition(row, catalog_url)
            code = run_task(args, definition, task_id=task_id)
            result["return_code"] = code
            interrupted = code in (130, -signal.SIGINT, -signal.SIGTERM)
        except KeyboardInterrupt:
            result["return_code"] = 130
            interrupted = True
        except (RunnerError, OSError) as error:
            result.update({"return_code": 1, "error": str(error)})
        results.append(result)
        if interrupted:
            break
        if result["return_code"] != 0:
            detail = result.get("error", f"exit status {result['return_code']}")
            print(f"{source_id}: failed: {detail}", file=sys.stderr, flush=True)
    failed = [result for result in results if result["return_code"] != 0]
    print(json.dumps({
        "mode": "dry_run" if args.dry_run else "recording",
        "source_catalog": catalog_url,
        "selected_tasks": len(rows),
        "attempted_tasks": len(results),
        "successful_tasks": len(results) - len(failed),
        "failed_tasks": len(failed),
        "interrupted": interrupted,
        "results": results,
    }, ensure_ascii=False, indent=2), flush=True)
    return 130 if interrupted else int(bool(failed))


def run_task(args: argparse.Namespace, definition: dict[str, Any], *, task_id: str) -> int:
    """Launch one validated task and wait before another task may start."""
    task_name = (
        args.task_name.strip()
        if args.task_name
        else str(definition.get("task_name") or task_id).strip()
    )
    output_dir = args.output_dir.resolve()
    run_id = unique_run_id(task_id, task_name, output_dir)
    default_novnc_url = (
        "http://127.0.0.1:"
        + os.environ.get("NOVNC_HOST_PORT", "16191")
        + "/vnc.html?resize=scale&autoconnect=1&path=websockify"
    )
    novnc_url = args.novnc_url or os.environ.get(
        "RUNNER_NOVNC_URL", default_novnc_url
    )
    command = build_runner_command(
        definition,
        task_id=task_id,
        task_name=task_name,
        run_id=run_id,
        output_dir=output_dir,
        env_file=args.env_file.resolve(),
        allow_human_intervention=not args.no_human_intervention,
        novnc_url=novnc_url,
        post_action_language_redirect=args.post_action_language_redirect,
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
    process: subprocess.Popen[str] | None = None
    with task_transition_lock():
        takeover = stop_previous_run(timeout=args.previous_run_stop_timeout)
        if takeover["status"] not in {"none", "stale_record_removed"}:
            print(
                "Previous task process: "
                f"{takeover['status']} "
                f"(run={takeover.get('run_id')}, pid={takeover.get('pid')})"
            )
        if not args.no_browser_start:
            restart_browser_service(args.env_file.resolve())
        container_name = os.environ.get(
            "CONTAINER_NAME", "w8-core-browser-engine"
        )
        profile_provenance = claim_browser_profile_provenance(container_name)
        runner_environment = os.environ.copy()
        if not runner_environment.get("AGENT_BROWSER_CDP_URL"):
            runner_environment["AGENT_BROWSER_CDP_URL"] = (
                browser_container_cdp_url(container_name)
            )
        runner_environment["RUNNER_BROWSER_PROFILE_PROVENANCE"] = json.dumps(
            profile_provenance, separators=(",", ":")
        )
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            env=runner_environment,
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
            process.wait(timeout=args.previous_run_stop_timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    finally:
        clear_active_run(process.pid)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RunnerError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
