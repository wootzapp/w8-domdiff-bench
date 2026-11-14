#!/usr/bin/env python3
"""Run a manual or catalog-defined browser task in a chosen directory."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

# Local runner exports reused here so validation and environment handling have
# one canonical implementation across direct and wrapper-based invocations.
from .runner import load_env, safe_task_id
# Shared exception avoids defining a second CLI-only error hierarchy.
from .recorder_support import RunnerError, write_json_lines, utc_now


ROOT = Path(__file__).resolve().parents[2]
RUNNER_MODULE = "w8bench.task_recorder.runner"
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


def restart_browser_service(env_file: Path) -> None:
    """Recreate only this checkout's Compose service with a fresh profile."""
    configured = subprocess.run(
        ["docker", "compose", "--env-file", str(env_file), "config", "--format", "json"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if configured.returncode:
        raise RunnerError("could not resolve this checkout's browser configuration")
    config = json.loads(configured.stdout)
    project = str(config["name"])
    name = str(config["services"]["w8-core"]["container_name"])
    relocation_path = RUNTIME_ROOT / "browser-relocation.json"
    relocation = {}
    if relocation_path.is_file():
        try:
            relocation = json.loads(relocation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RunnerError("browser checkout relocation receipt is invalid") from error
        if not isinstance(relocation, dict):
            raise RunnerError("browser checkout relocation receipt must be an object")
    # Compose identifies services by project labels, not just container name.
    # Check both so a copied/global project setting cannot recreate another
    # checkout's service even when its configured container name differs.
    found = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}",
         "--filter", "label=com.docker.compose.service=w8-core"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if found.returncode:
        raise RunnerError("could not inspect existing browser service ownership")
    for candidate in set(found.stdout.split()) | {name}:
        inspected = subprocess.run(["docker", "inspect", candidate], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if inspected.returncode:
            if candidate != name:
                raise RunnerError("an existing Compose browser could not be inspected")
            continue  # The new container name is not allocated yet.
        container = json.loads(inspected.stdout)[0]
        labels = (container.get("Config") or {}).get("Labels") or {}
        # An explicitly recorded checkout move can retain its existing container
        # until the next normal fresh-profile launch. Bind that permission to
        # the exact container, both directories, project and service.
        moved_checkout = (
            relocation.get("container_id") == container.get("Id")
            and relocation.get("source_directory") == labels.get("com.docker.compose.project.working_dir")
            and relocation.get("target_directory") == str(ROOT)
            and relocation.get("compose_project") == project
            and relocation.get("service") == "w8-core"
        )
        if (labels.get("com.docker.compose.project.working_dir") != str(ROOT) and not moved_checkout
                or labels.get("com.docker.compose.project") != project
                or labels.get("com.docker.compose.service") != "w8-core"):
            raise RunnerError("browser configuration points to a container owned by another checkout")
    completed = subprocess.run(
        ["docker", "compose", "--env-file", str(env_file), "up", "-d",
         "--force-recreate", "--wait", "w8-core"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise RunnerError("could not create a fresh browser: " + (completed.stderr.strip() or completed.stdout.strip()))
    relocation_path.unlink(missing_ok=True)


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

    ownership = (container.get("Config") or {}).get("Labels") or {}
    if ownership.get("com.docker.compose.project.working_dir") != str(ROOT):
        raise RunnerError("refusing to claim a browser profile owned by another checkout")

    # Inspect by immutable image ID, not by a tag that may have moved since this
    # container started. Older images remain usable with unknown source labels.
    image_id = container.get("Image")
    image_labels = (container.get("Config") or {}).get("Labels") or {}
    repo_digests: list[str] = []
    image_inspection_error = None
    if image_id:
        try:
            image_result = subprocess.run(
                ["docker", "image", "inspect", image_id],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            if image_result.returncode:
                raise ValueError(image_result.stderr.strip() or "image inspection failed")
            image = json.loads(image_result.stdout)[0]
            if image.get("Id") != image_id:
                raise ValueError("image inspection returned a different image ID")
            repo_digests = image.get("RepoDigests") or []
            image_labels = (image.get("Config") or {}).get("Labels") or {}
            if not isinstance(repo_digests, list) or any(not isinstance(part, str) for part in repo_digests):
                raise ValueError("image inspection returned invalid repository digests")
            if not isinstance(image_labels, dict):
                raise ValueError("image inspection returned invalid build labels")
        except (OSError, ValueError, IndexError, TypeError, AttributeError) as error:
            repo_digests = []
            image_labels = (container.get("Config") or {}).get("Labels") or {}
            image_inspection_error = str(error)
    browser_build = {
        "image_reference": (container.get("Config") or {}).get("Image"),
        "image_id": image_id,
        "repo_digests": repo_digests,
        "image_source_revision": image_labels.get("org.opencontainers.image.revision"),
        "image_version": image_labels.get("org.opencontainers.image.version"),
        "overlay_revision": image_labels.get("org.wootzapp.browser.overlay.revision"),
        "chromium_revision": image_labels.get("org.wootzapp.browser.chromium.revision"),
        "protocol_sha256": image_labels.get("org.wootzapp.browser.protocol.sha256"),
        "inspection_error": image_inspection_error,
    }

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
        "browser_build": browser_build,
        "browser_environment": dict(item.split("=",1) for item in (container.get("Config") or {}).get("Env",[])
            if item.partition("=")[0] in {"TZ","LANG","LANGUAGE","LC_ALL","BROWSER_LANG",
                "BROWSER_ACCEPT_LANGUAGE","CHROMIUM_EXTRA_ARGS","CHROMIUM_HEADLESS","CHROMIUM_RESET_PROFILE",
                "VNC_SCREEN","CDP_PORT","CHROMIUM_CDP_PORT"}),
    }


def validate_task_definition(
    instruction: str,
    start_url: str,
) -> dict[str, str]:
    """Validate a non-empty instruction and absolute HTTP(S) starting URL."""
    task = instruction.strip()
    if not task:
        raise RunnerError("--task must contain an instruction")
    url = start_url.strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RunnerError("--start-url must be an absolute HTTP(S) URL")
    return {"instruction": task, "start_url": url}


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
) -> dict[str, Any]:
    """Load one task from a frozen local JSONL catalog or an HTTP(S) source."""
    url = catalog_url.strip()
    parsed = urlsplit(url)
    if not parsed.scheme:
        path = Path(url).expanduser().resolve(strict=True)
        catalog_bytes = path.read_bytes()
        payload = catalog_bytes.decode("utf-8")
        url = str(path)
    else:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RunnerError("task catalog must be a local file or an absolute HTTP(S) URL")
        headers = {"User-Agent": "w8-paired-capture/1"}
        if token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                catalog_bytes = response.read()
                payload = catalog_bytes.decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, UnicodeDecodeError) as error:
            raise RunnerError(f"could not fetch task catalog {url}: {error}") from error
    catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
    if parsed.scheme:
        # A content-addressed local snapshot forwards provenance without another
        # HTTP request or a separate hash argument to the actor runner.
        frozen = RUNTIME_ROOT / "catalogs" / f"{catalog_hash}.jsonl"
        frozen.parent.mkdir(parents=True, exist_ok=True)
        if frozen.exists() and frozen.read_bytes() != catalog_bytes:
            raise RunnerError("frozen remote catalog bytes changed")
        if not frozen.exists():
            frozen.write_bytes(catalog_bytes)
        url = str(frozen.resolve())
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
            "task_name": str(row.get("task_name") or "").strip()
            or str(row.get("category") or "").strip(),
            "source_catalog": url,
            "catalog_sha256": catalog_hash,
            "category": row.get("category"),
            "difficulty": row.get("difficulty"),
            "valid_until": None,
        }
    )
    validity_path = ROOT / "internal" / "task_validity.json"
    if validity_path.is_file():
        validity = json.loads(validity_path.read_text(encoding="utf-8"))
        curated_catalog = (ROOT / validity["catalog"]).resolve(strict=True)
        if not curated_catalog.is_relative_to(ROOT.resolve()):
            raise RunnerError("task validity catalog must remain inside this checkout")
        if hashlib.sha256(curated_catalog.read_bytes()).hexdigest() == catalog_hash:
            valid_until = validity["tasks"].get(definition["source_task_id"], {}).get("valid_until")
            if valid_until is not None and (not isinstance(valid_until, str) or
                    date.fromisoformat(valid_until).isoformat() != valid_until):
                raise RunnerError("task validity valid_until must be an ISO UTC date or null")
            definition["valid_until"] = valid_until
    return definition


def build_runner_command(
    definition: dict[str, Any],
    *,
    task_id: str,
    task_name: str,
    run_id: str,
    output_dir: Path,
    env_file: Path,
    model: str = "",
    max_steps: int = 200,
    observation_mode: str = "dom",
    viewport_width: int = 1365,
    viewport_height: int = 768,
    max_output_tokens: int = 10000,
) -> list[str]:
    """Translate CLI inputs into the single authoritative runner invocation."""
    if max_output_tokens != 10000:
        raise RunnerError("actor output limit must be exactly 10000 tokens")
    if not 1 <= max_steps <= 200:
        raise RunnerError("actor turn budget must be positive and no greater than 200")
    command = [
        sys.executable,
        "-m",
        RUNNER_MODULE,
        "--observation-mode", observation_mode,
        "--viewport-width", str(viewport_width),
        "--viewport-height", str(viewport_height),
        "--max-output-tokens", str(max_output_tokens),
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
        "--max-steps",
        str(max_steps),
    ]
    configured_model = os.environ.get("OPENAI_MODEL", "").strip()
    if configured_model != "gpt-6.1-terra" or model and model != configured_model:
        raise RunnerError("actor model must match the single OPENAI_MODEL=gpt-6.1-terra configuration")
    command.extend(["--model", configured_model])
    if definition.get("source_catalog"):
        command.extend(["--source-catalog", str(definition["source_catalog"])])
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the generic task launcher options without starting any process."""
    parser = argparse.ArgumentParser(
        description="Run a configured catalog task or a manually supplied task"
    )
    parser.add_argument("task_id", nargs="*", help="catalog task selectors; omitted in a batch means the full catalog")
    parser.add_argument("--trials", type=int, help="positive trial count per arm; required to schedule a batch")
    parser.add_argument("--rubric-dir", type=Path, help="frozen task rubrics; required for full evaluation of every batch recording")
    parser.add_argument("--judge-model", help="explicit gpt-5.6-sol completion judge; required for batches")
    parser.add_argument("--task", help="complete manual task instruction and constraints")
    parser.add_argument("--start-url", help="absolute HTTP(S) starting URL for a manual task")
    catalog_group = parser.add_mutually_exclusive_group()
    catalog_group.add_argument("--catalog-url", help="HTTP(S) task catalog URL")
    catalog_group.add_argument("--catalog-file", type=Path, help="Frozen local JSONL task catalog")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--run-name", help="Experiment name; otherwise W8_RUN_NAME or run_1")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="parent directory for this task's recording",
    )
    parser.add_argument("--observation-mode", choices=["dom", "screenshot"])
    parser.add_argument("--viewport-width", type=int, default=1365)
    parser.add_argument("--viewport-height", type=int, default=768)
    parser.add_argument("--max-output-tokens", type=int, default=10000,
        help="fixed actor output limit; only 10000 is accepted")
    parser.add_argument("--model", default="")
    parser.add_argument("--allow-expired", action="store_true",
        help="explicitly allow a catalog task past its inclusive UTC valid_until date")
    parser.add_argument("--max-turns", "--max-steps", dest="max_steps", type=int, default=200,
        help="positive actor turn budget, at most 200")
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
    """Validate one task, prepare this checkout's browser, and wait for its runner."""
    args = parse_args(argv)
    load_env(args.env_file)
    configured_model = os.environ.get("OPENAI_MODEL", "").strip()
    if configured_model != "gpt-6.1-terra" or args.model and args.model != configured_model:
        raise RunnerError("actor model must match the single OPENAI_MODEL=gpt-6.1-terra configuration")
    args.model = configured_model
    if args.rubric_dir and not args.judge_model:
        raise RunnerError("completion grading requires explicit --judge-model gpt-5.6-sol; actor fallback is forbidden")
    if args.judge_model and args.judge_model != "gpt-5.6-sol":
        raise RunnerError("completion judge must be explicitly configured as gpt-5.6-sol")
    if args.max_steps <= 0 or min(args.viewport_width, args.viewport_height, args.max_output_tokens) <= 0:
        raise RunnerError("turn budget, viewport and output budget must be positive")
    if args.max_output_tokens != 10000:
        raise RunnerError("actor output limit must be exactly 10000 tokens")
    if args.max_steps > 200:
        raise RunnerError("actor turn budget must be positive and no greater than 200")
    if args.previous_run_stop_timeout < 0:
        raise RunnerError("--previous-run-stop-timeout must not be negative")
    if args.trials is not None:
        if args.trials <= 0 or args.observation_mode or args.task or args.start_url or args.no_browser_start or args.catalog_url:
            raise RunnerError("a batch requires positive --trials, catalog tasks, fresh profiles and both arms")
        if args.judge_model != "gpt-5.6-sol" or not args.dry_run and args.rubric_dir is None:
            raise RunnerError("every batch trial requires explicit --judge-model gpt-5.6-sol and execution requires --rubric-dir")
        from w8bench.run_paths import run_directory, resolve_run_name
        catalog_path = args.catalog_file or Path(os.environ.get("TASK_CATALOG_FILE", ""))
        if not catalog_path.is_file():
            raise RunnerError("a batch needs a frozen local --catalog-file")
        catalog_bytes = catalog_path.read_bytes()
        raw_catalog = catalog_bytes.decode("utf-8")
        catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
        selectors = args.task_id or [str(json.loads(line)["task_id"]) for line in raw_catalog.splitlines() if line.strip()]
        definitions = [fetch_catalog_task(str(catalog_path), selector) for selector in selectors]
        if any(definition["catalog_sha256"] != catalog_hash for definition in definitions):
            raise RunnerError("task catalog changed while selecting batch tasks")
        if not definitions or len({d["source_task_id"] for d in definitions}) != len(definitions):
            raise RunnerError("batch task identities must be nonempty and unique")
        checked_at = datetime.now(timezone.utc)
        for definition in definitions:
            if definition.get("valid_until") and checked_at.date() > date.fromisoformat(definition["valid_until"]):
                print(f"Warning: task {definition['source_task_id']} expired after {definition['valid_until']} UTC.", file=sys.stderr)
                if not args.allow_expired:
                    raise RunnerError("expired catalog task; review it or explicitly use --allow-expired")
        planning_only = args.dry_run and (args.rubric_dir is None or any(
            not (args.rubric_dir.resolve() / f"{safe_task_id(definition['source_task_id'])}.json").is_file()
            for definition in definitions))
        batch_dir = run_directory(args.output_dir, resolve_run_name(args.run_name)).resolve()
        batch_dir.mkdir(parents=True, exist_ok=True)
        frozen_catalog = batch_dir / "catalog.jsonl"
        if frozen_catalog.exists() and frozen_catalog.read_bytes() != catalog_bytes:
            raise RunnerError("saved batch catalog differs from the requested catalog")
        if not frozen_catalog.exists():
            frozen_catalog.write_bytes(catalog_bytes)
        for definition in definitions:
            definition["source_catalog"] = str(frozen_catalog)
        ledger_path = batch_dir / ("schedule_preview.jsonl" if planning_only else "ledger.jsonl")
        model_name = args.model
        schedule = []
        for trial in range(1, args.trials + 1):
            for index, definition in enumerate(definitions):
                modes = ["dom", "screenshot"] if (index + trial - 1) % 2 == 0 else ["screenshot", "dom"]
                for order, mode in enumerate(modes, 1):
                    identity = safe_task_id(definition["source_task_id"])
                    rubric = args.rubric_dir.resolve() / f"{identity}.json" if args.rubric_dir else None
                    if not args.dry_run and (rubric is None or not rubric.is_file()):
                        raise RunnerError(f"missing frozen rubric: {rubric}")
                    schedule.append({"sequence": len(schedule)+1, "task_id": identity, "arm": mode,
                        "trial": trial, "trials": args.trials, "arm_order": order,
                        "run_name": f"trial_{trial:04d}", "task": definition,
                        "catalog_sha256": catalog_hash,
                        "recording": str(batch_dir / f"trial_{trial:04d}" / mode / identity),
                        "configuration": {"model": model_name, "max_turns": args.max_steps,
                            "max_output_tokens": args.max_output_tokens,
                            "viewport": [args.viewport_width, args.viewport_height],
                            "image": os.environ.get("IMAGE"), "reasoning_effort": "medium",
                            "allow_expired": args.allow_expired,
                            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                            "browser_lang": os.environ.get("BROWSER_LANG", "en-US"),
                            "browser_accept_language": os.environ.get("BROWSER_ACCEPT_LANGUAGE", "en-US,en;q=0.9"),
                            "recorder_code_sha256": hashlib.sha256(b"".join(
                                f.read_bytes() for f in sorted((ROOT / "w8bench").rglob("*.py")))).hexdigest()},
                        "rubric": str(rubric) if rubric else None,
                        "rubric_sha256": hashlib.sha256(rubric.read_bytes()).hexdigest() if rubric and rubric.is_file() else None,
                        "planning_only": planning_only,
                        "judge_model": args.judge_model,
                        "completed": False, "technical_outcome": "not_started", "grade_outcome": "ungraded",
                        "grade_completed": False, "evaluation_outcome": "not_started"})
        # The global batch lock prevents two schedules from alternating through one browser.
        with task_transition_lock(RUNTIME_ROOT / "batch.lock"):
            if ledger_path.exists() and not planning_only:
                ledger = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
                if any(row.get("planning_only") for row in ledger):
                    raise RunnerError("a planning-only schedule cannot be resumed as an execution ledger")
                if len(ledger) != len(schedule):
                    raise RunnerError("saved schedule differs from requested task/arm/trial set")
                for saved, expected in zip(ledger, schedule):
                    if any(saved.get(key) != value for key, value in expected.items()
                           if key not in {"completed", "technical_outcome", "grade_outcome", "grade_completed", "evaluation_outcome"}):
                        raise RunnerError("saved schedule configuration differs; choose a new run name")
            else:
                ledger = schedule
                write_json_lines(ledger_path, ledger)  # Commit the entire denominator before starting work.
            marker = read_active_run()
            if marker is not None:
                if owned_process_group(marker) is not None:
                    raise RunnerError("a recorder is still running; finish or stop it before resuming the batch")
                ACTIVE_RUN_PATH.unlink(missing_ok=True)
            # A killed batch may leave its launcher or judge alive before/after the recorder marker.
            # Refuse reconciliation while those processes can still mutate scheduled artifacts.
            for entry in Path("/proc").iterdir():
                if not entry.name.isdigit() or int(entry.name) == os.getpid():
                    continue
                command = process_command(int(entry.name))
                if ("w8bench.task_recorder.task_cli" in command and str(batch_dir) in command
                        or "w8bench.verifier.run_comparison" in command
                        and any(row["recording"] in command for row in ledger)):
                    raise RunnerError(f"a scheduled launcher or judge is still running: pid {entry.name}")
            if args.dry_run:
                print(f"{'Planning-only schedule' if planning_only else 'Schedule'}: {ledger_path}; {len(ledger)} rows; no tasks started" +
                    ("; execution requires frozen rubrics" if planning_only else ""))
                return 0
            for row in ledger:
                if hashlib.sha256(frozen_catalog.read_bytes()).hexdigest() != row["catalog_sha256"]:
                    raise RunnerError("frozen batch catalog changed after scheduling")
                directory = Path(row["recording"])
                if not row["completed"]:
                    # A started attempt is terminal on resume; never silently buy another attempt.
                    if row["technical_outcome"] == "running" or row.get("started_at"):
                        final_path = directory / "final.json"
                        row["technical_outcome"] = (json.loads(final_path.read_text())["run_status"]
                            if final_path.is_file() else "interrupted")
                        row.update(completed=True, ended_at=utc_now())
                        if args.rubric_dir and final_path.is_file():
                            row["grade_outcome"] = "pending"
                    else:
                        row.update(technical_outcome="running", started_at=utc_now(), launcher_pid=os.getpid())
                        write_json_lines(ledger_path, ledger)
                        log_path = batch_dir / "logs" / f"attempt_{row['sequence']:06d}.log"
                        log_path.parent.mkdir(parents=True, exist_ok=True)
                        row["log"] = str(log_path)
                        command = [sys.executable, "-m", "w8bench.task_recorder.task_cli", row["task_id"],
                            "--catalog-file", str(catalog_path.resolve()), "--env-file", str(args.env_file.resolve()),
                            "--observation-mode", row["arm"], "--output-dir", str(batch_dir),
                            "--run-name", row["run_name"], "--model", model_name,
                            "--max-turns", str(args.max_steps), "--max-output-tokens", str(args.max_output_tokens),
                            "--viewport-width", str(args.viewport_width), "--viewport-height", str(args.viewport_height),
                            "--previous-run-stop-timeout", str(args.previous_run_stop_timeout)]
                        if args.allow_expired:
                            command.append("--allow-expired")
                        try:
                            with log_path.open("a", encoding="utf-8") as log:
                                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
                            row["exit_code"] = result.returncode
                            final_path = directory / "final.json"
                            row["technical_outcome"] = (json.loads(final_path.read_text())["run_status"]
                                if final_path.is_file() else "incomplete_recording" if directory.exists() else "startup_failure")
                            if args.rubric_dir and final_path.is_file():
                                row["grade_outcome"] = "pending"
                        except KeyboardInterrupt:
                            row.update(technical_outcome="interrupted", completed=True, ended_at=utc_now())
                            write_json_lines(ledger_path, ledger)
                            raise
                        except Exception as error:
                            row["technical_outcome"] = "startup_failure" if not directory.exists() else "incomplete_recording"
                            row["error"] = f"{type(error).__name__}: {error}"
                        row.update(completed=True, ended_at=utc_now(), actor_ended_at=utc_now())
                    write_json_lines(ledger_path, ledger)
                    print(f"{row['sequence']}/{len(ledger)} {row['task_id']} {row['arm']} trial {row['trial']}: "
                        f"{row['technical_outcome']}; grade={row['grade_outcome']}", flush=True)
                # Record both arms back to back before any grading latency.
                if row["arm_order"] == 2:
                    for partner in ledger[row["sequence"]-2:row["sequence"]]:
                        if partner["grade_completed"]:
                            continue
                        recording_path = Path(partner["recording"])
                        if not (recording_path / "final.json").is_file():
                            partner.update(grade_completed=True, grade_outcome="ungraded",
                                evaluation_outcome="unavailable", evaluation_reason="recording_not_finalized")
                            write_json_lines(ledger_path, ledger)
                            continue
                        if "log" not in partner:
                            path = batch_dir / "logs" / f"attempt_{partner['sequence']:06d}.log"
                            path.parent.mkdir(parents=True, exist_ok=True)
                            partner["log"] = str(path)
                        grade_path = recording_path / "completion.json"
                        if partner["grade_outcome"] == "running":
                            partner["evaluation_previous_interruption"] = True
                        partner.update(grade_outcome="running", evaluation_outcome="running", judge_started_at=utc_now())
                        write_json_lines(ledger_path, ledger)
                        try:
                            with Path(partner["log"]).open("a", encoding="utf-8") as log:
                                grade = subprocess.run([sys.executable, "-m", "w8bench.verifier.run_comparison",
                                    "--run", str(recording_path), "--rubric", partner["rubric"],
                                    "--env-file", str(args.env_file.resolve()), "--judge-model", partner["judge_model"], "--execute"],
                                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
                            partner["judge_exit_code"] = grade.returncode
                            partner["grade_outcome"] = (json.loads(grade_path.read_text())["verdict"]
                                if grade_path.is_file() else "grading_error")
                            from .prepare_verifier_data import inspect_recording
                            checked = inspect_recording(recording_path)
                            evaluation_path = (recording_path.parent.parent / "evaluations" / partner["run_name"] /
                                partner["arm"] / partner["task_id"] / checked["recording_sha256"] / "evaluation.json")
                            partner["evaluation_path"] = str(evaluation_path)
                            partner["evaluation_outcome"] = (json.loads(evaluation_path.read_text())["status"]
                                if evaluation_path.is_file() else "unavailable")
                        except KeyboardInterrupt:
                            partner.update(grade_outcome="interrupted", evaluation_outcome="interrupted",
                                grade_completed=False, judge_ended_at=utc_now())
                            write_json_lines(ledger_path, ledger)
                            raise
                        except Exception as error:
                            partner.update(grade_outcome="grading_error", evaluation_outcome="failed",
                                judge_error=f"{type(error).__name__}: {error}")
                        partner.update(grade_completed=True, judge_ended_at=utc_now())
                        write_json_lines(ledger_path, ledger)
            print(ledger_path)
            return 0
    if len(args.task_id) != 1 or not args.observation_mode:
        raise RunnerError("one task needs --observation-mode; a batch needs --trials")
    if args.rubric_dir or args.judge_model:
        raise RunnerError("batch grading options require --trials")
    task_id = safe_task_id(args.task_id[0].strip())
    from w8bench.run_paths import run_directory, resolve_run_name
    args.run_name = resolve_run_name(args.run_name)
    args.output_dir = run_directory(args.output_dir, args.run_name)
    # Supplying either manual field selects manual mode and requires both. With
    # neither field, the positional task id is resolved through the catalog.
    manual_task = args.task is not None or args.start_url is not None
    if manual_task:
        if not args.task or not args.start_url:
            raise RunnerError("manual tasks require both --task and --start-url")
        definition = validate_task_definition(args.task, args.start_url)
    else:
        catalog_url = (
            (str(args.catalog_file) if args.catalog_file is not None else None)
            or args.catalog_url
            or os.environ.get("TASK_CATALOG_FILE")
            or os.environ.get("TASK_CATALOG_URL")
        )
        if not catalog_url:
            raise RunnerError("task selection requires --catalog-file, --catalog-url, or an explicit catalog environment setting")
        definition = fetch_catalog_task(
            catalog_url,
            task_id,
            token=os.environ.get("TASK_CATALOG_TOKEN", os.environ.get("HF_TOKEN", "")),
        )
    if definition.get("valid_until") and datetime.now(timezone.utc).date() > date.fromisoformat(definition["valid_until"]):
        print(f"Warning: task {definition.get('source_task_id', task_id)} expired after {definition['valid_until']} UTC.", file=sys.stderr)
        if not args.allow_expired:
            raise RunnerError("expired catalog task; review it or explicitly use --allow-expired")
    task_name = str(definition.get("task_name") or task_id).strip()
    output_dir = (args.output_dir / args.observation_mode).resolve()
    run_id = safe_task_id(str(definition.get("source_task_id") or task_id))
    if (output_dir / run_id).exists():
        raise RunnerError("attempt directory already exists; use batch resume or a new run name")
    command = build_runner_command(
        definition,
        task_id=task_id,
        task_name=task_name,
        run_id=run_id,
        output_dir=args.output_dir.resolve(),
        env_file=args.env_file.resolve(),
        model=args.model,
        max_steps=args.max_steps, observation_mode=args.observation_mode,
        viewport_width=args.viewport_width, viewport_height=args.viewport_height,
        max_output_tokens=args.max_output_tokens,
    )

    command.extend(["--run-name", args.run_name])
    if args.allow_expired:
        command.append("--allow-expired")
    print(f"Task id: {task_id}")
    print(f"Task name: {task_name}")
    print(f"Start URL: {definition['start_url']}")
    print(f"Output: {output_dir / run_id}")
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
            "CONTAINER_NAME", "w8-turns-browser-engine"
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
