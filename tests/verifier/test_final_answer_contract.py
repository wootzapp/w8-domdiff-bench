import json

import pytest
from PIL import Image

from w8bench.dom_model.runner import preflight_dom_model_task
from w8bench.dom_model.trajectory import FinalAnswer as DomAnswer
from w8bench.screenshot_verifier.adapter import create_datapoint, normalize_all_screenshot_evidence
from w8bench.screenshot_verifier.rubric_agent import MMRubricAgent
from w8bench.screenshot_verifier.runner import _bind_all_screenshot_evidence
from w8bench.screenshot_verifier.trajectory import FinalAnswer as ScreenshotAnswer, Trajectory
from w8bench.screenshot_verifier.utils.preflight import discover_screenshots, preflight_screenshot_task
from w8bench.verifier.validate_inputs import validate_pair


@pytest.mark.parametrize("legacy", [False, True])
def test_both_verifier_paths_only_consume_answer_text(pair_factory, legacy):
    pair = pair_factory()
    for mode in ("screenshot", "dom"):
        payload = {"final_answer": "Saved"}
        if legacy:
            payload.update({
                "env_state_json": {"ignored": True},
                "env_state_raw": None,
                "screenshots": ["missing.png"],
                "is_aborted": mode == "dom",
                "is_rel_paths": False,
                "token_usage": {"invalid_legacy_usage": "ignored"},
                "extra_legacy_field": "ignored",
            })
        (pair[mode] / "final_answer.json").write_text(json.dumps(payload), encoding="utf-8")
    validated = validate_pair(
        pair["screenshot"], pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"],
    )
    assert validated["actions"] == 1
    _, _, dom = preflight_dom_model_task(
        pair["dom"], rubric_file=pair["rubric"], generation_metrics=pair["metrics"],
    )
    assert dom.answer.final_answer == "Saved"
    assert dom.answer.is_aborted is False
    assert not dom.answer.token_usage
    assert preflight_screenshot_task(pair["screenshot"])["screenshots"] == 2

    for index, color in enumerate(("red", "blue")):
        Image.new("RGB", (2, 2), color=color).save(pair["screenshot"] / f"screenshot{index}.png")
    trajectory = Trajectory(pair["screenshot"])
    assert trajectory.answer.is_aborted is False
    assert trajectory.answer.is_rel_paths is True
    assert not trajectory.answer.token_usage
    datapoint = create_datapoint(
        {"id": "task1", "question": "Save", "init_url": "https://example.test/start"},
        trajectory,
    )
    agent_input = MMRubricAgent._extract_input_from_datapoint(
        datapoint, screenshots_dir=str(pair["screenshot"]), redo_eval=True,
    )
    bound = _bind_all_screenshot_evidence(agent_input, normalize_all_screenshot_evidence(trajectory), 1)
    images = MMRubricAgent._load_screenshots(str(pair["screenshot"]), bound["actions_list"])
    assert [image.getpixel((0, 0)) for image in images] == [(255, 0, 0), (0, 0, 255)]
    # Loading again must not mistake normalization symlinks for original states.
    assert len(Trajectory(pair["screenshot"]).screenshots) == 2


@pytest.mark.parametrize("loader", [DomAnswer, ScreenshotAnswer])
@pytest.mark.parametrize("value", [{}, {"final_answer": None}, {"final_answer": 1}, []])
def test_answer_text_is_still_required(tmp_path, loader, value):
    path = tmp_path / "final_answer.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="final_answer text"):
        loader.load(path)


def test_discovery_orders_double_digit_indices_numerically(tmp_path):
    for index in range(12):
        (tmp_path / f"screenshot{index}.png").touch()
    assert [path.name for path in discover_screenshots(tmp_path)] == [
        f"screenshot{index}.png" for index in range(12)
    ]


def test_discovery_rejects_missing_or_duplicate_state_indices(tmp_path):
    (tmp_path / "screenshot0.png").touch()
    (tmp_path / "screenshot2.png").touch()
    with pytest.raises(ValueError, match="contiguous"):
        discover_screenshots(tmp_path)
    (tmp_path / "screenshot1.png").touch()
    (tmp_path / "screenshot_1.png").touch()
    with pytest.raises(ValueError, match="Duplicate"):
        discover_screenshots(tmp_path)
