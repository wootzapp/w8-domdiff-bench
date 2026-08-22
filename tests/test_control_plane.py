from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.common import (
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
    load_canonical_rubric,
    validate_endpoint_configs,
)
from scripts.generate_frozen_rubric import _dataset_only_preflight
from scripts.run_comparison import ROOT, _commands, _prepare_isolated_inputs
from scripts.validate_inputs import validate_pair


TASK = "task4"
SCREENSHOT = ROOT / "data/data-new-screenshot" / TASK
DOM = ROOT / "data/data-new-short-dom" / TASK
RUBRIC = ROOT / "rubrics" / f"{TASK}.json"
ENDPOINTS = ROOT / "config/endpoints/openai/canonical"
TASK4_PAIR_AVAILABLE = SCREENSHOT.is_dir() and DOM.is_dir()
requires_task4_pair = pytest.mark.skipif(
    not TASK4_PAIR_AVAILABLE,
    reason="requires a locally prepared audited Task4 dataset pair",
)


@requires_task4_pair
def test_task4_pair_passes_with_separate_semantically_equivalent_logs() -> None:
    receipt = validate_pair(
        SCREENSHOT,
        DOM,
        rubric_file=RUBRIC,
        eval_config=ENDPOINTS,
    )
    assert receipt["status"] == "pass"
    assert receipt["separate_action_logs_expected"] is True
    assert receipt["semantic_action_contract"] == "matched"
    assert receipt["actions"] == 3
    assert receipt["screenshot_states"] == 4
    assert receipt["dom_text_frames"] == 3
    screenshot_log = hashlib.sha256((SCREENSHOT / "web_surfer.log").read_bytes()).hexdigest()
    dom_log = hashlib.sha256((DOM / "web_surfer.log").read_bytes()).hexdigest()
    assert screenshot_log != dom_log


@requires_task4_pair
def test_task4_uses_one_canonical_rubric_and_denominator() -> None:
    frozen = load_canonical_rubric(RUBRIC)
    receipt = validate_pair(SCREENSHOT, DOM, rubric_file=RUBRIC)
    assert receipt["frozen_rubric_sha256"] == frozen.sha256
    assert receipt["criterion_denominator"] == 18
    assert receipt["criterion_count"] == 6


def test_endpoint_configs_are_local_nonsecret_and_canonical() -> None:
    receipt = validate_endpoint_configs(ENDPOINTS)
    assert set(receipt["models"]) == {
        CANONICAL_JUDGE_MODEL,
        CANONICAL_ACTION_MODEL,
    }
    assert all(str(ROOT) in row["path"] for row in receipt["files"])


@requires_task4_pair
def test_dom_unexpected_observation_file_fails_preflight(tmp_path: Path) -> None:
    screenshot = tmp_path / "screenshot" / TASK
    dom = tmp_path / "dom" / TASK
    shutil.copytree(SCREENSHOT, screenshot)
    shutil.copytree(DOM, dom)
    (dom / "dom_diff.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed DOM diff filenames"):
        validate_pair(screenshot, dom, rubric_file=RUBRIC)


@requires_task4_pair
def test_semantic_action_drift_fails_preflight(tmp_path: Path) -> None:
    screenshot = tmp_path / "screenshot" / TASK
    dom = tmp_path / "dom" / TASK
    shutil.copytree(SCREENSHOT, screenshot)
    shutil.copytree(DOM, dom)
    lines = (dom / "web_surfer.log").read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[1])
    event["arguments"]["url"] = "https://example.invalid/wrong"
    lines[1] = json.dumps(event)
    (dom / "web_surfer.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Semantic action 2 differs for url"):
        validate_pair(screenshot, dom, rubric_file=RUBRIC)


@requires_task4_pair
def test_rubric_generation_dataset_preflight_is_offline() -> None:
    receipt = _dataset_only_preflight(SCREENSHOT, DOM)
    assert receipt == {
        "task_id": "task8-playwright-release-research-20260811T084229Z",
        "task_alias": TASK,
        "actions": 3,
        "screenshots": 4,
        "dom_text_frames": 3,
    }


def test_comparison_runs_from_isolated_copies_without_mutating_sources(
    tmp_path: Path,
) -> None:
    source_screenshot = tmp_path / "source" / "screenshot"
    source_dom = tmp_path / "source" / "dom"
    source_screenshot.mkdir(parents=True)
    source_dom.mkdir(parents=True)
    (source_screenshot / "screenshot0.png").write_bytes(b"source-image")
    (source_dom / "dom_diff1.txt").write_text("source diff", encoding="utf-8")
    run_root = tmp_path / "run"
    run_root.mkdir()

    screenshot_copy, dom_copy = _prepare_isolated_inputs(
        screenshot_task=source_screenshot,
        dom_task=source_dom,
        run_root=run_root,
    )

    assert screenshot_copy == run_root / "_inputs" / "screenshot"
    assert dom_copy == run_root / "_inputs" / "dom"
    assert (screenshot_copy / "screenshot0.png").read_bytes() == b"source-image"
    assert (dom_copy / "dom_diff1.txt").read_text(encoding="utf-8") == "source diff"

    # Simulate the unchanged Microsoft adapter's compatibility alias. It must
    # exist only inside the disposable run bundle.
    (screenshot_copy / "screenshot_1.png").symlink_to("screenshot0.png")
    assert (screenshot_copy / "screenshot_1.png").is_symlink()
    assert not (source_screenshot / "screenshot_1.png").exists()

    commands = _commands(
        screenshot_task=screenshot_copy,
        dom_task=dom_copy,
        rubric_file=RUBRIC,
        eval_config=ENDPOINTS,
        run_root=run_root,
    )
    assert str(screenshot_copy) in commands["microsoft_verifier"]
    assert str(dom_copy) in commands["dom_diff_text"]


def test_controlled_commands_fix_models_settings_and_fresh_outputs(tmp_path: Path) -> None:
    commands = _commands(
        screenshot_task=SCREENSHOT,
        dom_task=DOM,
        rubric_file=RUBRIC,
        eval_config=ENDPOINTS,
        run_root=tmp_path / "fresh-run",
    )
    screenshot = commands["microsoft_verifier"]
    dom = commands["dom_diff_text"]
    for command in (screenshot, dom):
        assert CANONICAL_JUDGE_MODEL in command
        assert CANONICAL_ACTION_MODEL in command
        assert "--rubric-file" in command
        assert str(RUBRIC) in command
        assert "--redo-eval" in command
        assert str(ENDPOINTS) in command
    assert "--max-images-per-criterion" in screenshot
    assert "--max-evidence-per-criterion" in dom
    assert "--text-trajectory-starting-tokens" in dom
    assert "16000" in dom
