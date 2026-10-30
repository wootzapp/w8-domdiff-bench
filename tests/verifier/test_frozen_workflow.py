import json
import copy
import importlib
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from w8bench.verifier.generate_frozen_rubric import main as generate_main
from w8bench.verifier.run_comparison import commands, validate_command_parity
from w8bench.verifier.validate_inputs import compare_semantic_actions, parse_actions, validate_pair


def test_action_judge_model_matches_both_packages_and_endpoint_config():
    from w8bench.dom_model.control import CANONICAL_ACTION_MODEL as dom_model
    from w8bench.verifier.common import CANONICAL_ACTION_MODEL, validate_endpoint_configs

    root = Path(__file__).resolve().parents[2]
    assert CANONICAL_ACTION_MODEL == dom_model == "gpt-5.6-terra"
    validate_endpoint_configs(root / "config")
    endpoint = json.loads((root / "config/openai_gpt5_6_terra.json").read_text())
    assert endpoint["CHAT_COMPLETION_KWARGS_JSON"]["model"] == CANONICAL_ACTION_MODEL


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
def test_standalone_action_judge_defaults_to_terra_and_allows_override(package):
    module = importlib.import_module(f"w8bench.{package}.runner")
    arguments = ["--input", "task", "--rubric-file", "rubric.json",
                 "--eval-config", "config", "--output", "result.json"]
    if package == "dom_model":
        arguments += ["--generation-metrics", "metrics.json"]
    assert module.parse_args(arguments).action_model == "gpt-5.6-terra"
    # Allow an explicit action/validity model selection.
    assert module.parse_args(arguments + ["--action-model", "custom-model"]).action_model == "custom-model"


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
@pytest.mark.parametrize("action,keys,expected", [
    ("left_click", ["ref", "target", "thoughts"], None),
    ("left_click", ["coordinate", "_call_id"], None),
    ("type", ["text", "thoughts"], None),
    ("type", ["ref", "text", "target", "delete_existing_text"], None),
    ("scroll", ["ref", "pixels", "target", "thoughts"], None),
    ("select", ["ref", "text", "target", "thoughts"], None),
    ("key", ["key", "thoughts"], None),
    ("key", ["keys"], None),
    ("wait", ["seconds", "thoughts"], None),
    ("wait", ["time"], None),
    ("left_click", ["ref", "unexpected_parameter"], "6.1"),
    ("visit_url", ["url", "ref"], "6.1"),
    ("invented_action", ["ref", "thoughts"], "6.2"),
])
def test_diagnostics_recognize_commands_without_hiding_real_errors(package, action, keys, expected):
    module = importlib.import_module(f"w8bench.{package}.rubric_agent")
    schema = importlib.import_module(f"w8bench.{package}.utils.action_schema")
    steps = [{"step_number": 1, "action_name": action, "action_args_keys": keys}]
    original = copy.deepcopy(steps)
    errors = module.MMRubricAgent._detect_tool_interaction_errors(steps, schema.FARA_ACTION_DEFINITIONS)
    assert [row["error_code"] for row in errors] == ([expected] if expected else [])
    assert steps == original


def test_both_verifiers_use_identical_diagnostic_definitions():
    from w8bench.dom_model.utils.action_schema import ACTION_METADATA_KEYS, FARA_ACTION_DEFINITIONS
    from w8bench.screenshot_verifier.utils import action_schema
    assert FARA_ACTION_DEFINITIONS == action_schema.FARA_ACTION_DEFINITIONS
    assert ACTION_METADATA_KEYS == action_schema.ACTION_METADATA_KEYS == {"thoughts", "target"}


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
def test_diagnostic_filter_does_not_strip_judge_action_context(package):
    module = importlib.import_module(f"w8bench.{package}.rubric_agent")
    models = importlib.import_module(f"w8bench.{package}.models")
    schema = importlib.import_module(f"w8bench.{package}.utils.action_schema")
    arguments = {"ref": "e1", "target": {"role": "button", "name": "Save"},
                 "coordinate": [20, 30], "thoughts": "Save the value."}
    summary = models.StepSummary(index=1, action_name="left_click", action_args=arguments)
    history = module.MMRubricAgent._format_action_history([summary])
    steps = [{"step_number": 1, "action_name": "left_click", "action_args_keys": list(arguments)}]
    assert module.MMRubricAgent._detect_tool_interaction_errors(steps, schema.FARA_ACTION_DEFINITIONS) == []
    assert module.MMRubricAgent._format_action_history([summary]) == history
    for key in arguments:
        assert f'"{key}"' in history


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
def test_failure_analysis_explains_metadata_without_changing_history(package):
    module = importlib.import_module(f"w8bench.{package}.rubric_agent")
    schema = importlib.import_module(f"w8bench.{package}.utils.action_schema")
    agent = object.__new__(module.MMRubricAgent)
    agent.config = SimpleNamespace(action_definitions=schema.FARA_ACTION_DEFINITIONS,
                                   max_iters=1, gpt5_client=None)
    agent._call_llm = AsyncMock(return_value=json.dumps({
        "reasoning": "The recorded command is valid.", "has_failure": False, "failure_points": []
    }))
    history = 'left_click({"ref":"e1","target":{"name":"Save"},"thoughts":"Save it"})'
    result = asyncio.run(agent._first_point_of_failure_analysis(
        rubric={"items": []}, evidence_by_criterion={}, task="Inspect the page.",
        init_url_context="", action_history=history, predicted_output="Done.",
        outcome_result={"output_success": True},
        step_actions=[{"step_number": 1, "action_name": "left_click",
                       "action_args_keys": ["ref", "target", "thoughts"]}],
    ))
    assert result["has_failure"] is False
    agent._call_llm.assert_awaited_once()
    prompt = agent._call_llm.call_args.args[0][-1]["content"]
    assert history in prompt
    assert "Recorder annotations (target, thoughts)" in prompt
    assert "their presence alone is not an invalid invocation" in prompt


@pytest.mark.parametrize("package", ["screenshot_verifier", "dom_model"])
@pytest.mark.parametrize("earned", [0, 5, 10])
@pytest.mark.parametrize("success", [False, True])
def test_failure_diagnostics_do_not_change_numeric_or_outcome_scores(package, earned, success):
    module = importlib.import_module(f"w8bench.{package}.rubric_agent")
    # Exercise pure result wrapping without constructing any API clients.
    agent = object.__new__(module.MMRubricAgent)
    agent.config = SimpleNamespace(rubric_score_threshold=0.8)
    field = "post_dom_earned_points" if package == "dom_model" else "post_image_earned_points"
    result = {"items": [{"criterion": "Recorded fact", "max_points": 10, field: earned}],
              "total_max_points": 10, "total_earned_points": earned,
              "outcome_verification": {"output_success": success}}
    changed = copy.deepcopy(result)
    changed["first_point_of_failure"] = {"has_failure": True, "first_failure_step": 1}
    changed["intermediate_mm_rubric_steps"] = {"step9_first_point_of_failure": changed["first_point_of_failure"]}
    before, after = agent._wrap_result(result), agent._wrap_result(changed)
    assert before[0].score == after[0].score == earned / 10
    assert before[0].rubric_is_success == after[0].rubric_is_success == (earned >= 8)
    assert before[1].output_success == after[1].output_success == success
    assert module.MMRubricAgent._compute_final_scores(result) == module.MMRubricAgent._compute_final_scores(changed)
    assert module.MMRubricAgent._build_scored_rubric_summary(result) == module.MMRubricAgent._build_scored_rubric_summary(changed)


def test_keyboard_typing_does_not_require_an_element_ref(tmp_path):
    log = tmp_path / "web_surfer.log"
    log.write_text(json.dumps({"action": "type", "arguments": {"action": "type", "text": "Find this"}}) + "\n")
    assert parse_actions(log, mode="dom_model")[0]["text"] == "Find this"


def test_explicit_fill_still_requires_a_target(tmp_path):
    log = tmp_path / "web_surfer.log"
    log.write_text(json.dumps({"action": "fill", "arguments": {"action": "fill", "text": "value"}}) + "\n")
    with pytest.raises(ValueError, match="requires ref or target"):
        parse_actions(log, mode="dom_model")


def test_screenshot_click_with_ref_does_not_require_coordinates(tmp_path):
    log = tmp_path / "screenshot.log"
    log.write_text(
        json.dumps({"action": "left_click", "arguments": {"action": "left_click", "ref": "e107"}}) + "\n",
        encoding="utf-8",
    )

    actions = parse_actions(log, mode="screenshot")

    assert actions[0]["action"] == "click"
    assert actions[0]["ref"] == "e107"


def test_empty_action_log_represents_a_valid_zero_action_trajectory(tmp_path):
    log = tmp_path / "empty.log"
    log.write_text("", encoding="utf-8")

    assert parse_actions(log, mode="screenshot") == []
    assert parse_actions(log, mode="dom_model") == []


def test_key_action_is_preserved_and_compared(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    event = json.dumps({"action": "key", "arguments": {"action": "key", "key": "Enter"}}) + "\n"
    screenshot_log.write_text(event, encoding="utf-8")
    dom_log.write_text(event, encoding="utf-8")

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")

    assert screenshot_actions[0]["action"] == "key"
    assert screenshot_actions[0]["key"] == "Enter"
    compare_semantic_actions(screenshot_actions, dom_actions)


def test_wait_action_is_preserved_and_compared(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    event = json.dumps({"action": "wait", "arguments": {"action": "wait", "seconds": 1.0}}) + "\n"
    screenshot_log.write_text(event, encoding="utf-8")
    dom_log.write_text(event, encoding="utf-8")

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")

    assert screenshot_actions[0]["action"] == "wait"
    assert screenshot_actions[0]["seconds"] == 1.0
    compare_semantic_actions(screenshot_actions, dom_actions)


def test_select_action_is_preserved_and_compared(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    event = json.dumps({"action": "select", "arguments": {"action": "select", "ref": "e69", "text": "Avg. Customer Review"}}) + "\n"
    screenshot_log.write_text(event, encoding="utf-8")
    dom_log.write_text(event, encoding="utf-8")

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")

    assert screenshot_actions[0]["action"] == "select"
    compare_semantic_actions(screenshot_actions, dom_actions)


def test_history_back_aliases_normalize_to_screenshot_action(tmp_path):
    screenshot_log = tmp_path / "screenshot.log"
    dom_log = tmp_path / "dom.log"
    screenshot_log.write_text(
        json.dumps({"action": "back", "arguments": {}}) + "\n",
        encoding="utf-8",
    )
    dom_log.write_text(
        json.dumps({"action": "history_back", "arguments": {}}) + "\n",
        encoding="utf-8",
    )

    screenshot_actions = parse_actions(screenshot_log, mode="screenshot")
    dom_actions = parse_actions(dom_log, mode="dom_model")
    compare_semantic_actions(screenshot_actions, dom_actions)

    assert screenshot_actions[0]["action"] == "history_back"
    assert dom_actions[0]["action"] == "history_back"


def test_generator_dry_run_has_zero_writes(pair_factory, capsys, tmp_path):
    pair = pair_factory(sidecars=False, metrics=False)
    experiment = Path(__file__).resolve().parents[2]
    rubric = experiment / "__offline_dry_run_rubric.json"
    metrics = experiment / "__offline_dry_run_metrics.json"
    rc = generate_main(
        [
            "--screenshot-task", str(pair["screenshot"]),
            "--dom-task", str(pair["dom"]),
            "--staged-root", str(pair["staged"]),
            "--rubric-file", str(rubric),
            "--metrics-file", str(metrics),
            "--eval-config", str(pair["config"]),
        ]
    )
    assert rc == 0
    assert '"paid_calls_authorized": false' in capsys.readouterr().out
    assert not rubric.exists() and not metrics.exists()
    assert not (pair["screenshot"] / "task_data_with_canonical_rubric.json").exists()
    assert not (pair["dom"] / "task_data_with_canonical_rubric.json").exists()


def test_phase_b_requires_matching_sidecars_metrics_and_rubric(pair_factory):
    pair = pair_factory()
    receipt = validate_pair(
        pair["screenshot"], pair["dom"], rubric_file=pair["rubric"],
        generation_metrics=pair["metrics"], eval_config=pair["config"],
    )
    assert receipt["screenshot_sidecar_validated"] is True
    assert receipt["dom_model_sidecar_validated"] is True
    assert receipt["rubric_generation_calls_during_scoring"] == 0
    assert receipt["maximum_points"] == [7.0, 3.0]


def test_both_commands_share_exact_rubric_and_redo_eval(tmp_path):
    rubric = tmp_path / "frozen.json"
    built = commands(
        screenshot_task=tmp_path / "s", dom_task=tmp_path / "d", rubric_file=rubric,
        generation_metrics=tmp_path / "metrics.json", eval_config=tmp_path / "config",
        run_root=tmp_path / "run",
    )
    values = []
    for command in built.values():
        values.append(command[command.index("--rubric-file") + 1])
        assert "--redo-eval" in command
    assert values == [str(rubric), str(rubric)]
    dom_command = built["dom_model"]
    assert dom_command[dom_command.index("--output") + 1] == str(
            tmp_path / "run" / "dom_model"
    )
    parity = validate_command_parity(built)
    assert parity["min_relevance_threshold"] == "0"
    assert parity["max_evidence_items_per_criterion"] == "5"
    assert parity["redo_eval"] is True


def test_command_parity_rejects_dom_relevance_filter(tmp_path):
    built = commands(
        screenshot_task=tmp_path / "s", dom_task=tmp_path / "d",
        rubric_file=tmp_path / "rubric.json",
        generation_metrics=tmp_path / "metrics.json",
        eval_config=tmp_path / "config", run_root=tmp_path / "run",
    )
    dom = built["dom_model"]
    dom[dom.index("--min-relevance-threshold") + 1] = "3"
    with pytest.raises(ValueError, match="min_relevance_threshold"):
        validate_command_parity(built)


def test_command_parity_rejects_any_shared_control_drift(tmp_path):
    built = commands(
        screenshot_task=tmp_path / "s", dom_task=tmp_path / "d",
        rubric_file=tmp_path / "rubric.json",
        generation_metrics=tmp_path / "metrics.json",
        eval_config=tmp_path / "config", run_root=tmp_path / "run",
    )
    dom = built["dom_model"]
    dom[dom.index("--rubric-threshold") + 1] = "0.9"
    with pytest.raises(ValueError, match="rubric_threshold"):
        validate_command_parity(built)


def test_phase_a_rejects_protected_source_tree_as_staging_root():
    repository = Path(__file__).resolve().parents[2]
    protected = repository / "benchmarks"
    with pytest.raises(ValueError, match="protected source tree"):
        generate_main(
            [
                "--screenshot-task", str(protected / "unused-screenshot"),
                "--dom-task", str(protected / "unused-dom"),
                "--staged-root", str(protected),
                "--rubric-file", str(repository / "unused-rubric.json"),
                "--metrics-file", str(repository / "unused-metrics.json"),
                "--eval-config", str(repository / "config"),
            ]
        )
