from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


_fara_stub = types.ModuleType("fara")
_fara_stub.FARA_ACTION_DEFINITIONS = {}
if "fara" in sys.modules:
    setattr(sys.modules["fara"], "FARA_ACTION_DEFINITIONS", {})
else:
    sys.modules["fara"] = _fara_stub
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_trajectories.py"
_SPEC = importlib.util.spec_from_file_location("verify_trajectories", _SCRIPT)
assert _SPEC and _SPEC.loader
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def _args(**overrides):
    value = {
        "eval_config": "/tmp/endpoints",
        "judge_model": "gpt-5.2",
        "o4mini_model": "o4-mini",
        "rubric_threshold": 0.8,
        "max_images_per_criterion": 5,
        "mm_keypoint_score_threshold": 3,
        "majority_vote_instances": 1,
        "redo_eval": False,
        "success_criterion": "outcome",
        "evidence_mode": "screenshot",
        "evidence_schema_version": "screenshot/v1",
        "prompt_version": "mmrubric-prompts/v1",
        "dom_frame_char_budget": 16000,
        "dom_context_char_budget": 48000,
        "dom_top_k": None,
    }
    value.update(overrides)
    return value


def test_cli_accepts_dom_versioning_and_budget_options():
    args = runner.parse_args(
        [
            "--input",
            "/tmp/traj",
            "--task-data",
            "/tmp/tasks.json",
            "--task-data-format",
            "om2w",
            "--eval-config",
            "/tmp/endpoints",
            "--evidence-mode",
            "dom",
            "--evidence-schema-version",
            "dom-custom/v3",
            "--prompt-version",
            "dom-prompts/v2",
            "--dom-frame-char-budget",
            "8000",
            "--dom-context-char-budget",
            "24000",
            "--dom-top-k",
            "7",
        ]
    )
    assert args.evidence_mode == "dom"
    assert args.evidence_schema_version == "dom-custom/v3"
    assert args.prompt_version == "dom-prompts/v2"
    assert args.dom_frame_char_budget == 8000
    assert args.dom_context_char_budget == 24000
    assert args.dom_top_k == 7


def test_legacy_screenshot_cli_defaults_remain_unchanged():
    args = runner.parse_args(
        [
            "--input",
            "/tmp/traj",
            "--task-data",
            "/tmp/tasks.json",
            "--task-data-format",
            "om2w",
            "--eval-config",
            "/tmp/endpoints",
        ]
    )
    assert args.evidence_mode == "screenshot"
    assert args.evidence_schema_version == "screenshot/v1"
    assert args.success == "outcome"
    assert args.max_images_per_criterion == 5


def test_cache_identity_separates_modality_versions_models_and_config(tmp_path):
    baseline = _args()
    baseline_path = runner._score_path(tmp_path, baseline)
    assert "screenshot" in baseline_path.name
    assert baseline_path.name != "mmrubric_0.8-5-3.json"

    variants = [
        _args(evidence_mode="dom", evidence_schema_version="dom/v1"),
        _args(evidence_schema_version="screenshot/v2"),
        _args(prompt_version="mmrubric-prompts/v2"),
        _args(judge_model="gpt-5.3"),
        _args(dom_frame_char_budget=12000),
    ]
    assert all(runner._score_path(tmp_path, item) != baseline_path for item in variants)
    assert len({runner._score_path(tmp_path, item) for item in variants}) == len(
        variants
    )

    baseline_path.parent.mkdir()
    identity, _ = runner._verifier_identity(baseline)
    baseline_path.write_text(
        json.dumps({"cache_identity": identity, "score": 1}), encoding="utf-8"
    )
    assert runner._read_matching_cached_score(baseline_path, baseline)["score"] == 1
    assert runner._read_matching_cached_score(baseline_path, variants[0]) is None


def test_screenshot_dom_and_dual_caches_are_pairwise_isolated(tmp_path):
    configs = [
        _args(evidence_mode=mode, evidence_schema_version=schema)
        for mode, schema in (
            ("screenshot", "screenshot/v1"),
            ("dom", "dom-trajectory-manifest/v2"),
            ("dual", "screenshot/v1+dom-trajectory-manifest/v2"),
        )
    ]
    paths = [runner._score_path(tmp_path, config) for config in configs]
    identities = [runner._verifier_identity(config)[0] for config in configs]

    assert len(set(paths)) == 3
    assert len(set(identities)) == 3
    assert {path.name.split("-")[-2] for path in paths} == {
        "screenshot",
        "dom",
        "dual",
    }


def test_cached_report_rows_retain_parity_labels(tmp_path, monkeypatch):
    args = _args()
    score_path = runner._score_path(tmp_path, args)
    score_path.parent.mkdir()
    identity, _ = runner._verifier_identity(args)
    score_path.write_text(
        json.dumps(
            {
                "cache_identity": identity,
                "evidence_format": "screenshot",
                "capture_coverage": {"complete_for_requested_mode": True},
                "result": {
                    "rubric": {
                        "score": 0.75,
                        "is_success": False,
                        "total_max_points": 4,
                        "total_earned_points": 3,
                    },
                    "outcome": {"success": True},
                    "error_taxonomy": {
                        "first_point_of_failure": {"first_failure_step": 2}
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "_GLOBAL_ARGS", args)

    result = runner._run_one(str(tmp_path))

    assert result["status"] == "cached"
    assert result["rubric_score"] == 0.75
    assert result["rubric_is_success"] is False
    assert result["outcome_success"] is True
    assert result["first_failure_step"] == 2


def test_versioned_output_keeps_legacy_fields_and_adds_structured_metadata():
    args = _args(
        evidence_mode="dom",
        evidence_schema_version="dom-trajectory-manifest/v2",
    )
    coverage = {
        "actions": 1,
        "dom_frames": 1,
        "complete_for_requested_mode": True,
    }
    result = {"top_score": 1, "rubric": {"score": 1.0}}
    payload = runner._build_score_payload(
        args, 1, {"rubric_is_success": 1}, coverage, result
    )

    assert payload["score"] == 1
    assert json.loads(payload["gpt_response_text"])["rubric_is_success"] == 1
    assert payload["evidence_format"] == "semantic-dom"
    assert payload["evidence_schema_version"] == "dom-trajectory-manifest/v2"
    assert payload["verifier_schema_version"] == "mmrubric-result/v2"
    assert payload["prompt_version"] == "mmrubric-prompts/v1"
    assert payload["model_roles"] == {
        "judge": "gpt-5.2",
        "action_rubric": "o4-mini",
    }
    assert payload["capture_coverage"] is coverage
    assert payload["result"] is result
    assert payload["cache_identity"]


def test_capture_coverage_summarizes_dual_frames():
    coverage = runner._capture_coverage(
        {
            "evidence_mode": "dual",
            "actions_list": [{"screenshot": "screenshot0.png"}],
            "dom_actions": [
                {
                    "dom_after_snapshot_path": "semantic_dom.json",
                    "dom_evidence_schema_version": "semantic-dom-snapshot/v1",
                    "dom_capture_status": "captured",
                    "dom_coverage_status": "partial",
                }
            ],
        },
        n_actions=1,
    )
    assert coverage["complete_for_requested_mode"] is True
    assert coverage["capture_status_counts"] == {"captured": 1}
    assert coverage["coverage_status_counts"] == {"partial": 1}
    assert coverage["dom_frame_schema_versions"] == {
        "semantic-dom-snapshot/v1": 1
    }
