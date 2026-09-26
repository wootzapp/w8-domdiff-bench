import json

import pytest

from microsoft_verifier.utils.rubric import (
    load_frozen_rubric,
    require_matching_embedded_rubric,
)


def test_loads_required_canonical_rubric(tmp_path):
    rubric = {"items": [{"criterion": "One", "description": "D", "max_points": 10}]}
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps({"task_id": "task", "precomputed_rubric": rubric}))
    frozen = load_frozen_rubric(path, expected_task_id="task")
    assert len(frozen.sha256) == 64
    assert require_matching_embedded_rubric({}, frozen)["precomputed_rubric"] == rubric


def test_rejects_wrong_task_and_embedded_drift(tmp_path):
    rubric = {"items": [{"criterion": "One", "description": "D", "max_points": 10}]}
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps({"task_id": "task", "precomputed_rubric": rubric}))
    with pytest.raises(ValueError, match="task_id mismatch"):
        load_frozen_rubric(path, expected_task_id="other")
    frozen = load_frozen_rubric(path, expected_task_id="task")
    with pytest.raises(ValueError, match="differs"):
        require_matching_embedded_rubric({"precomputed_rubric": {"items": []}}, frozen)
