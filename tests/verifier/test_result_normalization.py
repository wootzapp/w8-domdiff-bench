import json
from copy import deepcopy

import pytest

from w8bench.verifier.compare_results import compare
from w8bench.verifier.common import CANONICAL_ACTION_MODEL, CANONICAL_SETTINGS, canonical_sha256
from w8bench.verifier.normalize_results import normalize_dom_model, normalize_screenshot


def _run(mode):
    return {
        "task_id": "task",
        "evidence_mode": mode,
        "frozen_rubric_sha256": "abc",
        "phase_a_generation_metrics": "/same/metrics.json",
        "judge_models": {"judge": "gpt-5.2", "action_and_validity_judge": CANONICAL_ACTION_MODEL},
        "pipeline_settings": dict(CANONICAL_SETTINGS),
        "result": {"process_score": 1.0, "total_earned_points": 10.0, "total_max_points": 10.0, "outcome_success": True},
        "criteria": [
            {"criterion": "a", "action_only_points": 5.0, "final_points": 7.0, "max_points": 7.0},
            {"criterion": "b", "action_only_points": 2.0, "final_points": 3.0, "max_points": 3.0},
        ],
        "llm_calls": {"total": 2, "api_attempts": 3, "retries": 1, "rubric_generation_calls": 0},
        "token_usage": {"combined": {"prompt_tokens": 10, "completion_tokens": 5, "reasoning_tokens": 2, "total_tokens": 15}},
    }


def test_comparison_accepts_controlled_matching_receipts():
    receipt, markdown = compare(_run("screenshot"), _run("dom_model"))
    assert receipt["status"] == "pass"
    assert set(receipt) == {
        "status", "task_id", "criterion_denominator", "screenshot", "dom_model", "criteria"
    }
    assert set(receipt["screenshot"]) == {
        "process_score", "earned_points", "maximum_points", "outcome_success"
    }
    assert set(receipt["dom_model"]) == set(receipt["screenshot"])
    assert "token" not in markdown.lower()
    assert "calls" not in markdown.lower()
    assert "DOM-model" in markdown

    screenshot = _run("screenshot")
    dom = _run("dom_model")
    for run in (screenshot, dom):
        run["criteria"][1]["condition"] = "Only when needed"
    dom["criteria"][1]["is_applicable"] = False
    dom["criteria"][1]["final_points"] = 0.0
    dom["result"].update(total_max_points=7.0, total_earned_points=7.0)
    original = deepcopy((screenshot, dom))
    receipt, markdown = compare(screenshot, dom)
    assert receipt["criterion_denominator"] == 10.0
    assert receipt["screenshot"]["maximum_points"] == 10.0
    assert receipt["dom_model"]["maximum_points"] == 7.0
    assert (screenshot, dom) == original
    assert "conditional criteria" in markdown


@pytest.mark.parametrize("points_field", ["post_image_earned_points", "post_dom_earned_points"])
def test_penalties_normalize_and_compare_without_changing_frozen_criteria(pair_factory, tmp_path, points_field):
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
    receipt, markdown = compare(screenshot, dom)
    assert receipt["criterion_denominator"] == 10
    for value in (screenshot, dom):
        assert sum(item["max_points"] for item in value["criteria"]) == 10
        assert value["result"]["process_score"] == 10 / 12
        assert value["result"]["total_max_points"] == 12
        assert value["penalty_criteria"][0]["final_points"] == 0
    assert pair["rubric"].read_bytes() == original_rubric
    raw["intermediate_mm_rubric_steps"]["step7_penalty_criteria"][0][points_field] = 1
    result_file.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="zero earned points"):
        (normalize_dom_model if points_field.startswith("post_dom") else normalize_screenshot)(result_file, **kwargs)


@pytest.mark.parametrize("drift", ["hash", "order", "maximum", "generation", "denominator"])
def test_comparison_rejects_frozen_contract_drift(drift):
    screenshot = _run("screenshot")
    dom = deepcopy(_run("dom_model"))
    if drift == "hash":
        dom["frozen_rubric_sha256"] = "different"
    elif drift == "order":
        dom["criteria"].reverse()
    elif drift == "maximum":
        dom["criteria"][0]["max_points"] = 6.0
        dom["criteria"][1]["max_points"] = 4.0
    elif drift == "denominator":
        dom["result"]["total_max_points"] = 9.0
    else:
        dom["llm_calls"]["rubric_generation_calls"] = 1
    with pytest.raises(ValueError):
        compare(screenshot, dom)



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
