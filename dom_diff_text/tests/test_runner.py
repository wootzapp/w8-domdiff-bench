from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dom_diff_text.runner import (
    _score_path,
    _verifier_identity,
    parse_args,
    preflight_trajectory,
)
from dom_diff_text.utils.rubric import load_frozen_rubric


FIXTURE = Path(__file__).parent / "fixtures" / "dom_diff_text" / "changes_present" / "dom_diff1.txt"


def _rubric() -> dict:
    return {
        "items": [
            {
                "criterion": "Publisher and release date are reported",
                "description": "Use explicit page evidence.",
                "max_points": 10,
                "earned_points": "",
                "justification": "",
            }
        ]
    }


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "task-fixture"
    root.mkdir()
    shutil.copy2(FIXTURE, root / "dom_diff1.txt")
    task_data = {
        "id": "task-fixture",
        "question": "Find the publisher and release date.",
        "init_url": "https://example.test/start",
    }
    (root / "task_data.json").write_text(json.dumps(task_data), encoding="utf-8")
    (root / "final_answer.json").write_text(
        json.dumps({"final_answer": "Microsoft Studios, 7/6/2022", "token_usage": {}}),
        encoding="utf-8",
    )
    (root / "web_surfer.log").write_text(
        json.dumps(
            {
                "action": "left_click",
                "url": "https://example.test/start",
                "arguments": {"action": "left_click", "ref": "button-1"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rubric = tmp_path / "rubric.json"
    rubric.write_text(
        json.dumps({"task_id": "task-fixture", "precomputed_rubric": _rubric()}),
        encoding="utf-8",
    )
    return root, rubric


def test_cli_requires_shared_rubric_and_has_no_s3_mode(tmp_path: Path) -> None:
    args = parse_args(
        [
            "--input", str(tmp_path),
            "--rubric-file", str(tmp_path / "rubric.json"),
            "--eval-config", str(tmp_path),
            "--output", str(tmp_path / "results"),
        ]
    )
    assert args.rubric_file.endswith("rubric.json")
    assert not hasattr(args, "text_s3_cap_enabled")
    assert not hasattr(args, "text_s3_prompt_cap_tokens")


def test_preflight_uses_exact_canonical_rubric_before_clients(tmp_path: Path) -> None:
    root, rubric_path = _bundle(tmp_path)
    _, _, input_dict, frames = preflight_trajectory(
        root, rubric_file=rubric_path
    )
    frozen = load_frozen_rubric(rubric_path, expected_task_id="task-fixture")
    assert len(frames) == 1
    assert input_dict["frozen_rubric_sha256"] == frozen.sha256
    assert input_dict["canonical_rubric_path"] == str(rubric_path.resolve())


def test_preflight_rejects_modality_specific_rubric_drift(tmp_path: Path) -> None:
    root, rubric_path = _bundle(tmp_path)
    task = json.loads((root / "task_data.json").read_text())
    task["precomputed_rubric"] = _rubric()
    task["precomputed_rubric"]["items"][0]["max_points"] = 9
    (root / "task_data.json").write_text(json.dumps(task), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from the canonical"):
        preflight_trajectory(root, rubric_file=rubric_path)


def test_identity_and_score_path_are_result_rooted(tmp_path: Path) -> None:
    root, rubric_path = _bundle(tmp_path)
    digest = load_frozen_rubric(rubric_path, expected_task_id="task-fixture").sha256
    args = {
        "requested_evidence_mode": "dom_diff_text",
        "judge_model": "gpt-5.2",
        "o4mini_model": "o4-mini",
        "rubric_threshold": 0.8,
        "max_evidence_per_criterion": 5,
        "mm_keypoint_score_threshold": 3,
        "majority_vote_instances": 1,
        "success_criterion": "outcome",
        "dom_frame_char_budget": 16000,
        "dom_context_char_budget": 48000,
        "dom_top_k": None,
        "text_relevance_mode": "batched_llm",
        "text_frame_starting_tokens": 1500,
        "text_trajectory_starting_tokens": 16000,
        "text_analysis_starting_tokens": 24000,
        "text_max_chunk_tokens": 256,
        "text_allow_budget_expansion": True,
        "text_model_context_window_tokens": 128000,
        "text_relevance_completion_reserve_tokens": 4096,
        "text_analysis_completion_reserve_tokens": 8192,
        "text_prompt_headroom_tokens": 1024,
        "request_timeout_seconds": 180.0,
        "max_api_retries": 2,
        "eval_config": str(tmp_path / "missing-config"),
        "rubric_file": str(rubric_path),
        "frozen_rubric_sha256": digest,
        "output_dir": str(tmp_path / "results"),
    }
    identity, config = _verifier_identity(args, root)
    assert config["frozen_rubric_sha256"] == digest
    assert "experimental_text_s3_cap" not in config
    assert identity in _score_path(root, args).name
    assert _score_path(root, args).is_relative_to(tmp_path / "results")
