import json

from microsoft_verifier.runner import _read_task_data, parse_args


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
