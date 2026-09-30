"""Upload and fetch paired verifier trajectories from Hugging Face."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
DEFAULT_CACHE_ROOT = REPOSITORY_ROOT / ".cache" / "hf-trajectories"
DEFAULT_REPO_ID = "WootzappLab/browser-agent-tasks"
DEFAULT_REVISION = "main"
REMOTE_PREFIX = "trajectories"
TASK_RE = re.compile(r"^task_[0-9]+$")


def _require_huggingface_hub() -> tuple[Callable[..., str], type[Any]]:
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as exc:  # pragma: no cover - exercised by installation, not unit tests.
        raise RuntimeError(
            "huggingface_hub is required; install verifier/requirements.txt"
        ) from exc
    return snapshot_download, HfApi


def _validate_task_name(task: str) -> str:
    if not TASK_RE.fullmatch(task):
        raise ValueError(f"Invalid task alias {task!r}; expected task_N or task_0N")
    return task


def _state_indices(root: Path, pattern: re.Pattern[str]) -> list[int]:
    return sorted(
        int(match.group(1))
        for path in root.iterdir()
        if path.is_file() and (match := pattern.fullmatch(path.name))
    )


def validate_downloaded_pair(data_root: Path, task: str) -> dict[str, Any]:
    """Validate the files needed before the existing verifier preflight runs."""

    screenshot = data_root / "data-ss" / task
    dom = data_root / "data-dom" / task
    for modality, root in (("screenshot", screenshot), ("DOM", dom)):
        if not root.is_dir():
            raise ValueError(f"Downloaded {modality} task folder is missing: {root}")
        for name in ("task_data.json", "web_surfer.log", "final_answer.json"):
            if not (root / name).is_file():
                raise ValueError(f"Downloaded {modality} task lacks {name}: {root}")

    screenshot_indices = _state_indices(
        screenshot, re.compile(r"^screenshot_?(0|[1-9]\d*)\.(?:png|jpe?g|webp)$", re.I)
    )
    dom_indices = _state_indices(dom, re.compile(r"^dom_model(0|[1-9]\d*)\.txt$"))
    if not screenshot_indices or screenshot_indices != list(range(len(screenshot_indices))):
        raise ValueError(
            f"Downloaded screenshots for {task} must be contiguous from 0; "
            f"got {screenshot_indices}"
        )
    if not dom_indices or dom_indices != list(range(len(dom_indices))):
        raise ValueError(
            f"Downloaded DOM states for {task} must be contiguous from 0; got {dom_indices}"
        )
    return {
        "task": task,
        "screenshot_states": len(screenshot_indices),
        "dom_states": len(dom_indices),
        "screenshot_path": str(screenshot),
        "dom_path": str(dom),
    }


def _local_paired_tasks(data_root: Path) -> list[str]:
    screenshot_root = data_root / "data-ss"
    dom_root = data_root / "data-dom"
    if not screenshot_root.is_dir() or not dom_root.is_dir():
        return []
    screenshot = {path.name for path in screenshot_root.iterdir() if path.is_dir()}
    dom = {path.name for path in dom_root.iterdir() if path.is_dir()}
    return sorted(screenshot & dom)


def fetch_trajectories(
    *,
    data_root: str | Path,
    task: str | None,
    repo_id: str = DEFAULT_REPO_ID,
    revision: str = DEFAULT_REVISION,
    snapshot_download_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Fetch one paired task, or every task, without changing verifier inputs."""

    target = Path(data_root).resolve()
    if task is not None:
        _validate_task_name(task)
    if snapshot_download_fn is None:
        snapshot_download_fn, _ = _require_huggingface_hub()
    patterns = [
        f"{REMOTE_PREFIX}/data-ss/{task}/**",
        f"{REMOTE_PREFIX}/data-dom/{task}/**",
    ] if task else [
        f"{REMOTE_PREFIX}/data-ss/**",
        f"{REMOTE_PREFIX}/data-dom/**",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hf-trajectories-", dir=target.parent) as name:
        stage = Path(name)
        snapshot_root = Path(
            snapshot_download_fn(
                repo_id=repo_id,
                repo_type="dataset",
                revision=revision,
                allow_patterns=patterns,
                local_dir=stage,
            )
        )
        remote_root = snapshot_root / REMOTE_PREFIX
        if not remote_root.is_dir():
            raise ValueError(
                f"Hugging Face dataset {repo_id}@{revision} does not contain {REMOTE_PREFIX}/"
            )
        screenshot_tasks = {
            path.name for path in (remote_root / "data-ss").iterdir() if path.is_dir()
        } if (remote_root / "data-ss").is_dir() else set()
        dom_tasks = {
            path.name for path in (remote_root / "data-dom").iterdir() if path.is_dir()
        } if (remote_root / "data-dom").is_dir() else set()
        aliases = sorted(screenshot_tasks & dom_tasks)
        if task and aliases != [task]:
            raise ValueError(f"No complete paired trajectory found for {task} in {repo_id}")
        if not aliases:
            raise ValueError(f"No paired trajectories found in {repo_id}@{revision}")

        copied: list[str] = []
        for alias in aliases:
            if _pair_is_valid(target, alias):
                copied.append(alias)
                continue
            existing = [
                target / modality / alias
                for modality in ("data-ss", "data-dom")
                if (target / modality / alias).exists()
            ]
            if existing:
                raise ValueError(
                    "Refusing to replace incomplete local trajectory directories: "
                    + ", ".join(str(path) for path in existing)
                )
            for modality in ("data-ss", "data-dom"):
                source = remote_root / modality / alias
                destination = target / modality / alias
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, destination)
            copied.append(alias)

    validated = [validate_downloaded_pair(target, alias) for alias in copied]
    return {
        "status": "resolved_from_huggingface",
        "repo_id": repo_id,
        "revision": revision,
        "data_root": str(target),
        "tasks": validated,
    }


def _pair_is_valid(data_root: Path, task: str) -> bool:
    try:
        validate_downloaded_pair(data_root, task)
    except ValueError:
        return False
    return True


def upload_trajectories(
    *,
    data_root: str | Path,
    repo_id: str = DEFAULT_REPO_ID,
    revision: str = DEFAULT_REVISION,
    api: Any | None = None,
) -> dict[str, Any]:
    """Upload paired trajectories without adding them to the Dataset Viewer config."""

    source = Path(data_root).resolve(strict=True)
    aliases = _local_paired_tasks(source)
    if not aliases:
        raise ValueError(f"No paired tasks found under {source}")
    validated = [validate_downloaded_pair(source, alias) for alias in aliases]
    if api is None:
        _, api_type = _require_huggingface_hub()
        api = api_type()
    result = api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        revision=revision,
        folder_path=str(source),
        path_in_repo=REMOTE_PREFIX,
        allow_patterns=["data-ss/**", "data-dom/**"],
        commit_message="Add paired screenshot and DOM verifier trajectories",
    )
    return {
        "status": "uploaded",
        "repo_id": repo_id,
        "revision": revision,
        "remote_prefix": REMOTE_PREFIX,
        "task_count": len(validated),
        "commit": str(result),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "upload"))
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--task")
    selection.add_argument("--all", action="store_true")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_CACHE_ROOT),
        help="Ignored local cache populated from Hugging Face",
    )
    parser.add_argument(
        "--source-dir",
        default=str(REPOSITORY_ROOT / "data"),
        help="Maintainer-only local source used by the upload command",
    )
    parser.add_argument(
        "--repo-id", default=os.environ.get("W8_BENCH_DATASET_REPO", DEFAULT_REPO_ID)
    )
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "fetch":
        if not args.task and not args.all:
            raise ValueError("fetch requires --task TASK or --all")
        result = fetch_trajectories(
            data_root=args.output_dir,
            task=None if args.all else args.task,
            repo_id=args.repo_id,
            revision=args.revision,
        )
    else:
        if args.task or args.all:
            raise ValueError("upload always publishes every validated paired task")
        result = upload_trajectories(
            data_root=args.source_dir,
            repo_id=args.repo_id,
            revision=args.revision,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
