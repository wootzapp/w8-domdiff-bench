"""Upload and fetch paired verifier trajectories from Hugging Face."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = REPOSITORY_ROOT / "dataset"
DEFAULT_REPO_ID = "WootzappLab/browser-agent-tasks"
DEFAULT_REVISION = "main"
REMOTE_PREFIX = "trajectories"
TASK_RE = re.compile(r"^task_[0-9]+$")


def _require_huggingface_hub() -> tuple[Callable[..., str], type[Any]]:
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as exc:  # pragma: no cover - exercised by installation, not unit tests.
        raise RuntimeError(
            "huggingface_hub is required; install the project dependencies"
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


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


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
    with tempfile.TemporaryDirectory(prefix=".dataset-download-", dir=target.parent) as name:
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
                # File presence alone does not establish the selected revision.
                # Never silently score a different cohort from an older cache.
                for modality in ("data-ss", "data-dom"):
                    remote_task = remote_root / modality / alias
                    local_task = target / modality / alias
                    if _tree_hashes(remote_task) != _tree_hashes(local_task):
                        raise ValueError(
                            f"Cached trajectory differs from selected Hugging Face inputs: {local_task}. "
                            "Move the existing download folder aside before fetching again."
                        )
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
    """Upload paired trajectories and their loadable JSONL index."""

    source = Path(data_root).resolve(strict=True)
    aliases = _local_paired_tasks(source)
    if not aliases:
        raise ValueError(f"No paired tasks found under {source}")
    validated = [validate_downloaded_pair(source, alias) for alias in aliases]
    index = build_trajectory_index(source)
    if api is None:
        _, api_type = _require_huggingface_hub()
        api = api_type()
    result = api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        revision=revision,
        folder_path=str(source),
        path_in_repo=REMOTE_PREFIX,
        allow_patterns=["data-ss/**", "data-dom/**", "pairs.jsonl"],
        commit_message="Add paired screenshot and DOM verifier trajectories",
    )
    return {
        "status": "uploaded",
        "repo_id": repo_id,
        "revision": revision,
        "remote_prefix": REMOTE_PREFIX,
        "task_count": len(validated),
        "index_sha256": index["sha256"],
        "commit": str(result),
    }


def build_trajectory_index(data_root: str | Path) -> dict[str, Any]:
    """Index complete paired inputs without changing any source task file."""
    source = Path(data_root).resolve(strict=True)
    aliases = _local_paired_tasks(source)
    if not aliases:
        raise ValueError(f"No paired tasks found under {source}")
    screenshot_tasks = {p.name for p in (source / "data-ss").iterdir() if p.is_dir()}
    dom_tasks = {p.name for p in (source / "data-dom").iterdir() if p.is_dir()}
    if screenshot_tasks != dom_tasks:
        raise ValueError("Screenshot and DOM task folders differ; a pair is incomplete")
    records = []
    for alias in aliases:
        validated = validate_downloaded_pair(source, alias)
        if validated["screenshot_states"] != validated["dom_states"]:
            raise ValueError(f"Screenshot and DOM state counts differ for {alias}")
        screenshot, dom = source / "data-ss" / alias, source / "data-dom" / alias
        shared_files = {}
        identities, answers = [], []
        for mode, folder in (("screenshot", screenshot), ("dom_model", dom)):
            for name in ("task_data.json", "final_answer.json", "web_surfer.log"):
                shared_files[(mode, name)] = (folder / name).read_bytes().decode("utf-8")
            metadata = json.loads(shared_files[(mode, "task_data.json")])
            if isinstance(metadata, list) and len(metadata) == 1:
                metadata = metadata[0]
            if not isinstance(metadata, dict):
                raise ValueError(f"Expected one task object for {alias}, {mode}")
            identities.append((metadata.get("task_id") or metadata.get("id"),
                               metadata.get("confirmed_task") or metadata.get("question"),
                               metadata.get("website") or metadata.get("init_url")))
            answer = json.loads(shared_files[(mode, "final_answer.json")])
            if not isinstance(answer, dict) or "final_answer" not in answer:
                raise ValueError(f"Missing final answer object for {alias}, {mode}")
            answers.append(answer["final_answer"])
        if identities[0] != identities[1] or not all(identities[0]):
            raise ValueError(f"Screenshot and DOM task identities differ or are incomplete for {alias}")
        if answers[0] != answers[1]:
            raise ValueError(f"Screenshot and DOM final answers differ for {alias}")
        screenshot_log = shared_files[("screenshot", "web_surfer.log")]
        dom_log = shared_files[("dom_model", "web_surfer.log")]
        if screenshot_log != dom_log:
            raise ValueError(f"Screenshot and DOM action logs differ for {alias}")
        images = sorted(
            (path for path in screenshot.iterdir() if path.is_file() and not path.is_symlink()
             and re.fullmatch(r"screenshot_?(0|[1-9]\d*)\.(?:png|jpe?g|webp)", path.name, re.I)),
            key=lambda path: int(re.search(r"\d+", path.name).group()),
        )
        if len(images) != validated["screenshot_states"]:
            raise ValueError(f"Original screenshot sources are incomplete for {alias}")
        states = []
        for index, image in enumerate(images):
            model = dom / f"dom_model{index}.txt"
            states.append({
                "index": index,
                "screenshot_path": f"{REMOTE_PREFIX}/data-ss/{alias}/{image.name}",
                "screenshot_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "dom_model_path": f"{REMOTE_PREFIX}/data-dom/{alias}/{model.name}",
                "dom_model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                "dom_model_text": model.read_bytes().decode("utf-8"),
            })
        records.append({
            "task_alias": alias,
            "screenshot_task_data_json": shared_files[("screenshot", "task_data.json")],
            "dom_model_task_data_json": shared_files[("dom_model", "task_data.json")],
            "screenshot_final_answer_json": shared_files[("screenshot", "final_answer.json")],
            "dom_model_final_answer_json": shared_files[("dom_model", "final_answer.json")],
            "web_surfer_log": screenshot_log,
            "states": states,
        })
    index_path = source / "pairs.jsonl"
    pending = index_path.with_suffix(".jsonl.tmp")
    pending.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    pending.replace(index_path)
    return {"status": "indexed", "task_count": len(records),
            "index_path": os.path.relpath(index_path, REPOSITORY_ROOT),
            "sha256": hashlib.sha256(index_path.read_bytes()).hexdigest()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "upload", "index"))
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--task")
    selection.add_argument("--all", action="store_true")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_DATASET_ROOT),
        help="Local dataset directory populated from Hugging Face",
    )
    parser.add_argument(
        "--source-dir",
        default=str(REPOSITORY_ROOT / "trajectories"),
        help="Prepared local trajectories used by index and upload",
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
            raise ValueError(f"{args.command} uses every validated paired task")
        result = build_trajectory_index(args.source_dir) if args.command == "index" else upload_trajectories(
            data_root=args.source_dir,
            repo_id=args.repo_id,
            revision=args.revision,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
