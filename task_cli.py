#!/usr/bin/env python3
"""Run any browser task in a unique fresh-tasks recording directory."""

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
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from runner import DEFAULT_NOVNC_URL, RunnerError, load_env, safe_task_id


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "runner.py"
FRESH_TASKS_ROOT = ROOT / "fresh-tasks"
RUNTIME_ROOT = ROOT / ".runtime"
ACTIVE_RUN_PATH = RUNTIME_ROOT / "active-run.json"
TRANSITION_LOCK_PATH = RUNTIME_ROOT / "task-transition.lock"
DEFAULT_STOP_TIMEOUT_SECONDS = 15.0


def process_start_ticks(pid: int) -> int | None:
    """Return Linux's process start-time token, which protects against PID reuse."""
    try:
        value = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        fields_after_command = value[value.rfind(")") + 2 :].split()
        return int(fields_after_command[19])
    except (OSError, ValueError, IndexError):
        return None


def process_command(pid: int) -> list[str]:
    try:
        value = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", errors="replace") for part in value.split(b"\0") if part]


def read_active_run(path: Path = ACTIVE_RUN_PATH) -> dict[str, Any] | None:
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
    deadline = time.monotonic() + max(0.0, timeout)
    while process_start_ticks(pid) is not None and time.monotonic() < deadline:
        time.sleep(0.1)
    return process_start_ticks(pid) is None


def stop_previous_run(
    path: Path = ACTIVE_RUN_PATH,
    *,
    timeout: float = DEFAULT_STOP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_active_run(record: dict[str, Any], path: Path = ACTIVE_RUN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def clear_active_run(pid: int, path: Path = ACTIVE_RUN_PATH) -> None:
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
    task = instruction.strip()
    if not task:
        raise RunnerError("--task must contain an instruction")
    url = start_url.strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RunnerError("--start-url must be an absolute HTTP(S) URL")
    return {"instruction": task, "start_url": url, "model": model.strip()}


def unique_run_id(
    task_id: str,
    task_name: str,
    output_dir: Path,
    *,
    timestamp: str | None = None,
) -> str:
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
        task_id,
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
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run any browser task in a unique fresh-tasks directory"
    )
    parser.add_argument("task_id", help="stable task id, for example task17 or checkout-prices")
    parser.add_argument(
        "task_name",
        nargs="?",
        help="human-readable run name; defaults to task_id",
    )
    parser.add_argument("--task", required=True, help="complete task instruction and constraints")
    parser.add_argument("--start-url", required=True, help="absolute HTTP(S) starting URL")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="parent for this task's timestamped runs; defaults to fresh-tasks/<task-id>",
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
    args = parse_args(argv)
    task_id = safe_task_id(args.task_id.strip())
    task_name = args.task_name.strip() if args.task_name else task_id
    if args.max_steps <= 0:
        raise RunnerError("--max-steps must be positive")
    if args.previous_run_stop_timeout < 0:
        raise RunnerError("--previous-run-stop-timeout must not be negative")

    load_env(args.env_file)
    definition = validate_task_definition(args.task, args.start_url, model=args.model)
    output_dir = (
        args.output_dir or (FRESH_TASKS_ROOT / task_id)
    ).resolve()
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
