import json

import pytest

from dom_model.utils.preflight import preflight_screenshot_task


def _task(tmp_path, screenshots=2):
    root = tmp_path / "task"
    root.mkdir()
    (root / "web_surfer.log").write_text(
        json.dumps({"action": "left_click", "arguments": {"coordinate": [1, 2]}}) + "\n"
    )
    (root / "final_answer.json").write_text(json.dumps({"final_answer": "done"}))
    for index in range(screenshots):
        (root / f"screenshot{index}.png").write_bytes(b"png")
    return root


def test_accepts_intentional_n_plus_one_screenshots(tmp_path):
    assert preflight_screenshot_task(_task(tmp_path)) == {
        "actions": 1,
        "screenshots": 2,
    }


def test_accepts_zero_actions_with_one_initial_screenshot(tmp_path):
    root = _task(tmp_path, screenshots=1)
    (root / "web_surfer.log").write_text("")

    assert preflight_screenshot_task(root) == {
        "actions": 0,
        "screenshots": 1,
    }


def test_rejects_misaligned_screenshot_count(tmp_path):
    with pytest.raises(ValueError, match="N or intentional N\\+1"):
        preflight_screenshot_task(_task(tmp_path, screenshots=3))
