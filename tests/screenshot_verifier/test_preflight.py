import json

import pytest

from w8bench.verifier.screenshot_verifier.utils.preflight import preflight_screenshot_task


def _task(tmp_path, screenshots=2):
    root = tmp_path / "task"
    root.mkdir()
    (root / "web_surfer.log").write_text(
        json.dumps({"action": "left_click", "arguments": {"coordinate": [1, 2]}}) + "\n"
    )
    (root / "final_answer.json").write_text(
        json.dumps(
            {
                "final_answer": "done",
                "screenshots": [f"screenshot{index}.png" for index in range(screenshots)],
            }
        )
    )
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
    with pytest.raises(ValueError, match="exactly N\\+1"):
        preflight_screenshot_task(_task(tmp_path, screenshots=3))

def test_capture_gaps_are_explicit_and_own_available_states_are_never_dropped(tmp_path):
    root = _task(tmp_path, screenshots=3)
    (root / "web_surfer.log").write_text("\n".join(json.dumps({"action": "wait", "arguments": {}}) for _ in range(3)))
    for path in list(root.glob("screenshot*.png")):
        path.unlink()
    for index in (1, 3, 4):
        (root / f"screenshot{index}.png").write_bytes(b"png")
    (root / "final_answer.json").write_text(json.dumps({"final_answer": "done", "screenshots": ["screenshot1.png", "screenshot3.png", "screenshot4.png"]}))
    (root / "task_data.json").write_text(json.dumps({"evaluation_context": {"expected_state_ids": [1, 2, 3, 4], "format_gaps": {"screenshot": [2]}, "navigation_states": [3]}}))
    receipt = preflight_screenshot_task(root)
    assert receipt["available_state_ids"] == [1, 3, 4]
    assert receipt["missing_states"] == [2]
    assert receipt["navigation_states"] == [3]
    (root / "screenshot2.png").write_bytes(b"available")
    with pytest.raises(ValueError, match="capture gaps"):
        preflight_screenshot_task(root)
