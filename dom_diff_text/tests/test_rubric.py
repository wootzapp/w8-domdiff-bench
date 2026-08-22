import json

import pytest

from dom_diff_text.utils.rubric import (
    canonical_rubric_bytes,
    load_frozen_rubric,
    require_matching_embedded_rubric,
)


def test_canonical_rubric_hash_is_order_independent(tmp_path):
    rubric = {"items": [{"criterion": "One", "description": "D", "max_points": 7}]}
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps({"precomputed_rubric": rubric, "task_id": "task"}))
    loaded = load_frozen_rubric(path, expected_task_id="task")
    assert len(loaded.sha256) == 64
    assert canonical_rubric_bytes(rubric) == canonical_rubric_bytes(
        {"items": [{"max_points": 7, "description": "D", "criterion": "One"}]}
    )


def test_embedded_rubric_must_match_canonical(tmp_path):
    rubric = {"items": [{"criterion": "One", "description": "D", "max_points": 7}]}
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps({"task_id": "task", "precomputed_rubric": rubric}))
    frozen = load_frozen_rubric(path, expected_task_id="task")
    with pytest.raises(ValueError, match="differs"):
        require_matching_embedded_rubric(
            {"precomputed_rubric": {"items": []}}, frozen
        )
