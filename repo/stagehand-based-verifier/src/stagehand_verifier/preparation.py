from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .loader import load_stagehand_trajectory


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_stagehand_trajectory(source: str | Path, destination: str | Path) -> Path:
    source_root = Path(source).resolve()
    destination_root = Path(destination).resolve()
    if destination_root.exists() and any(destination_root.iterdir()):
        raise ValueError(f"Destination must be absent or empty: {destination_root}")
    trajectory, _ = load_stagehand_trajectory(source_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    task_data: dict[str, Any] = {
        "id": trajectory.task.task_id,
        "question": trajectory.task.instruction,
        "init_url": trajectory.task.init_url,
    }
    if trajectory.task.precomputed_rubric is not None:
        task_data["precomputed_rubric"] = trajectory.task.precomputed_rubric
    _write_json(destination_root / "task_data.json", task_data)
    _write_json(
        destination_root / f"{trajectory.task.task_id}_answer.json",
        {
            "final_answer": trajectory.final_answer,
            "is_aborted": trajectory.is_aborted,
            "token_usage": trajectory.solver_token_usage,
        },
    )
    log_lines = []
    for action in trajectory.actions:
        log_lines.append(
            json.dumps(
                {
                    "action": action.name,
                    "arguments": action.arguments,
                    "url": action.url,
                    "action_id": action.action_id,
                },
                ensure_ascii=False,
            )
        )
    (destination_root / "web_surfer.log").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )

    source_hashes: dict[str, str] = {}
    for ordinal in range(1, len(trajectory.actions) + 2):
        source_step = source_root / f"step_{ordinal:03d}"
        target_step = destination_root / source_step.name
        target_step.mkdir()
        names = ["aria.txt", "page_state.json"]
        if ordinal <= len(trajectory.actions):
            names.extend(["action.json", "tool_result.json"])
        for name in names:
            source_file = source_step / name
            target_file = target_step / name
            shutil.copy2(source_file, target_file)
            source_hashes[str(target_file.relative_to(destination_root))] = _sha256(target_file)

    manifest = dict(trajectory.manifest)
    manifest["source_path"] = str(source_root)
    manifest["source_hashes"] = source_hashes
    _write_json(destination_root / "stagehand_manifest.json", manifest)
    return destination_root


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a minimal Stagehand verifier dataset")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = prepare_stagehand_trajectory(args.input, args.output)
    print(output)
    return 0
