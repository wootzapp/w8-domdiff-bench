import json

import pytest

from w8bench.verifier.common import canonical_sha256
from w8bench.verifier.normalize_results import normalize_dom_model, normalize_screenshot


@pytest.mark.parametrize("points_field", ["post_image_earned_points", "post_dom_earned_points"])
def test_penalties_normalize_without_changing_frozen_criteria(pair_factory, tmp_path, points_field):
    pair = pair_factory()
    original_rubric = pair["rubric"].read_bytes()
    rubric = json.loads(original_rubric)["precomputed_rubric"]
    rows = [{**item, "earned_points": item["max_points"],
             points_field: item["max_points"]} for item in rubric["items"]]
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
           "criterion_denominator": 10, "rubric_total_max_points": 12,
           "rubric_total_earned_points": 10, "rubric_score": 10 / 12,
           "intermediate_mm_rubric_steps": {"step6_rescoring_summary": rows,
               "step7_penalty_criteria": [{"criterion": "Unsolicited material side effect",
                   "max_points": 2, "earned_points": 0, points_field: 0,
                   "penalty": True}]}}
    result_file = tmp_path / "penalty.json"
    result_file.write_text(json.dumps(raw))
    kwargs = {"input_task": pair["screenshot"], "rubric_file": pair["rubric"],
              "generation_metrics": pair["metrics"], "run_log": tmp_path / "run.log"}
    screenshot = normalize_screenshot(result_file, **kwargs)
    dom = normalize_dom_model(result_file, **kwargs)
    assert screenshot["frozen_rubric_sha256"] == dom["frozen_rubric_sha256"] == canonical_sha256(rubric)
    for value in (screenshot, dom):
        assert sum(item["max_points"] for item in value["criteria"]) == 10
        assert value["result"]["frozen_full_score"] is True
        assert value["result"]["frozen_total_earned_points"] == 10
        assert value["result"]["frozen_total_max_points"] == 10
        assert value["result"]["runtime_penalty_total_max_points"] == 2
        assert value["result"]["process_score"] == 10 / 12
        assert value["result"]["total_max_points"] == 12
        assert value["penalty_criteria"][0]["final_points"] == 0
    assert pair["rubric"].read_bytes() == original_rubric
    raw["intermediate_mm_rubric_steps"]["step7_penalty_criteria"][0][points_field] = 1
    result_file.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="zero earned points"):
        (normalize_dom_model if points_field.startswith("post_dom") else normalize_screenshot)(result_file, **kwargs)


@pytest.mark.parametrize("normalizer", [normalize_screenshot, normalize_dom_model])
@pytest.mark.parametrize("drift", ["hash", "order", "maximum", "generation", "denominator"])
def test_normalizer_rejects_frozen_contract_drift(pair_factory, tmp_path, drift, normalizer):
    pair = pair_factory()
    rubric = json.loads(pair["rubric"].read_text())["precomputed_rubric"]
    rows = [{**item, "earned_points": item["max_points"], "post_image_earned_points": item["max_points"],
             "post_dom_earned_points": item["max_points"]} for item in rubric["items"]]
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
        "criterion_denominator": 10, "rubric_total_max_points": 10, "rubric_total_earned_points": 10,
        "rubric_score": 1, "intermediate_mm_rubric_steps": {"step6_rescoring_summary": rows}}
    if drift == "hash":
        raw["rubric_sha256"] = "different"
    elif drift == "order":
        rows.reverse()
    elif drift == "maximum":
        rows[0]["max_points"] = 6; rows[1]["max_points"] = 4
    elif drift == "generation":
        raw["rubric_generation_calls"] = 1
    else:
        raw["rubric_total_max_points"] = 9
    path = tmp_path / "result.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        normalizer(path, input_task=pair["dom"], rubric_file=pair["rubric"], generation_metrics=pair["metrics"], run_log=tmp_path / "run.log")



@pytest.mark.parametrize(
    ("points_field", "normalizer"),
    [
        ("post_image_earned_points", normalize_screenshot),
        ("post_dom_earned_points", normalize_dom_model),
        ("post_image_earned_points", normalize_dom_model),
    ],
    ids=("screenshot", "dom-native", "dom-historical"),
)
def test_normalizer_accepts_conditional_denominator(
    tmp_path, points_field, normalizer
):
    items = [
        {
            "criterion": "always",
            "description": "always applies",
            "max_points": 7,
            "justification": "",
            "earned_points": "",
        },
        {
            "criterion": "conditional",
            "description": "applies only when unavailable",
            "max_points": 3,
            "justification": "",
            "earned_points": "",
        },
    ]
    rubric = {"items": items}
    rubric_file = tmp_path / "rubric.json"
    rubric_file.write_text(json.dumps({"task_id": "task", "precomputed_rubric": rubric}))
    generation_metrics = tmp_path / "generation.json"
    generation_metrics.write_text("{}")
    run_log = tmp_path / "run.log"
    run_log.write_text("")
    result = {
        "task_id": "task",
        "rubric_sha256": canonical_sha256(rubric),
        "criterion_denominator": 10,
        "rubric_total_max_points": 7,
        "rubric_total_earned_points": 7,
        "rubric_score": 1.0,
        "rubric_generation_calls": 0,
        "intermediate_mm_rubric_steps": {
            "step6_rescoring_summary": [
                {
                    "criterion": "always",
                    "max_points": 7,
                    "earned_points": 7,
                    points_field: 7,
                },
                {
                    "criterion": "conditional",
                    "max_points": 3,
                    "earned_points": 0,
                    points_field: 0,
                    "condition": "Only when unavailable",
                    "is_condition_met": False,
                },
            ]
        },
    }
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps(result))

    normalized = normalizer(
        result_file,
        input_task=tmp_path,
        rubric_file=rubric_file,
        generation_metrics=generation_metrics,
        run_log=run_log,
    )

    assert normalized["result"]["total_max_points"] == 7
    assert normalized["criteria"][1]["is_applicable"] is False
    assert normalized["result"]["process_score"] == 1
    assert normalized["result"]["frozen_full_score"] is False
    assert normalized["result"]["frozen_total_earned_points"] == 7
    assert normalized["result"]["frozen_total_max_points"] == 10


@pytest.mark.parametrize("normalizer", [normalize_screenshot, normalize_dom_model])
@pytest.mark.parametrize("include_validity", [False, True])
def test_normalizer_reads_ambiguity_from_its_actual_stage_and_preserves_missing(pair_factory, tmp_path, normalizer, include_validity):
    pair = pair_factory()
    rubric = json.loads(pair["rubric"].read_text())["precomputed_rubric"]
    steps = {"step6_rescoring_summary": [{**item, "earned_points": item["max_points"]} for item in rubric["items"]],
        "step9_first_point_of_failure": {"has_failure": False, "is_ambiguous": False, "ambiguity_codes": []}}
    if include_validity:
        steps["step9b_task_verification_with_trajectory"] = {"is_ambiguous": True, "ambiguity_codes": ["7.1"], "is_invalid": False}
        steps["step10_task_verification"] = {"is_ambiguous": False, "ambiguity_codes": [], "is_invalid": True}
    raw = {"task_id": pair["task"]["task_id"], "rubric_sha256": canonical_sha256(rubric),
        "rubric_total_max_points": 10, "rubric_total_earned_points": 10, "rubric_score": 1,
        "intermediate_mm_rubric_steps": steps}
    path = tmp_path / "result.json"
    path.write_text(json.dumps(raw))
    value = normalizer(path, input_task=pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"], run_log=tmp_path / "run.log")["result"]
    assert value["is_ambiguous"] is (True if include_validity else None)
    assert value["ambiguity_codes"] == (["7.1"] if include_validity else None)
    assert value["is_invalid"] is (True if include_validity else None)
    assert value["trajectory_task_verification"] == (steps["step9b_task_verification_with_trajectory"] if include_validity else None)
    assert value["task_only_verification"] == (steps["step10_task_verification"] if include_validity else None)
    assert value["process_score"] == 1 and value["frozen_full_score"] is True
