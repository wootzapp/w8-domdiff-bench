import json

from w8bench.verifier.screenshot_verifier.runner import _read_task_data, parse_args


def test_runner_requires_shared_canonical_rubric(tmp_path):
    args = parse_args(
        [
            "--input", str(tmp_path),
            "--rubric-file", str(tmp_path / "rubric.json"),
            "--eval-config", str(tmp_path),
            "--output", str(tmp_path / "results"),
        ]
    )
    assert args.rubric_file.endswith("rubric.json")
    assert args.output.endswith("results")


def test_runner_normalizes_verified_one_item_task_data_format(tmp_path):
    (tmp_path / "task_data.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "task4",
                    "confirmed_task": "Find product details",
                    "website": "https://example.test",
                }
            ]
        )
    )
    task = _read_task_data(tmp_path)
    assert task["id"] == "task4"
    assert task["question"] == "Find product details"
    assert task["init_url"] == "https://example.test"

def test_sparse_screenshot_binding_and_loading_keep_original_ids(tmp_path):
    from PIL import Image
    from w8bench.verifier.screenshot_verifier.runner import _bind_all_screenshot_evidence
    from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent
    context = {"expected_state_ids": [1, 2, 3, 4], "format_gaps": {"screenshot": [2]}}
    names = ["screenshot1.png", "screenshot3.png", "screenshot4.png"]
    for index, name in enumerate(names):
        Image.new("RGB", (3, 2), (index * 70, 0, 0)).save(tmp_path / name)
    bound = _bind_all_screenshot_evidence({"action_history": "full 3 actions"}, names, 3, context)
    assert [item["id"] for item in bound["actions_list"]] == [1, 3, 4]
    images = MMRubricAgent._load_evidence(str(tmp_path), bound["actions_list"])
    assert list(images) == [1, 3, 4]
    assert images[3].getpixel((0, 0)) == (70, 0, 0)
    assert bound["action_history"] == "full 3 actions"


def test_contiguous_screenshot_binding_is_unchanged():
    from w8bench.verifier.screenshot_verifier.runner import _bind_all_screenshot_evidence
    input_value = {"action_history": "one actual action", "step_actions": [{"step_number": 1}]}
    assert _bind_all_screenshot_evidence(input_value, ["screenshot_1.png", "screenshot_2.png"], 1) == {
        **input_value, "actions_list": [{"id": 1, "screenshot": "screenshot_1.png"}, {"id": 2, "screenshot": "screenshot_2.png"}]}


def test_sparse_evidence_labels_preserve_source_id_without_dense_count_confusion():
    from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent
    rubric = {"items": [{"criterion": "saved"}]}
    base = {"screenshot_idx": 4, "source_state_id": 4, "screenshot_evidence": "Saved", "criterion_analysis": "Shown", "discrepancies": "None"}
    text = MMRubricAgent._build_all_evidence_text(rubric, {0: [base]}, 3)
    assert "Screenshot state 4 (3 available)" in text and "4 of 3" not in text
    original = {key: value for key, value in base.items() if key != "source_state_id"}
    assert "Screenshot 5 of 6" in MMRubricAgent._build_all_evidence_text(rubric, {0: [original]}, 6)
