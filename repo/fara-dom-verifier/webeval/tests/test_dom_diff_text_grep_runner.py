from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from webeval.rubric_agent.dom_diff_text_grep_tools import RawEvidenceBundle


SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_trajectories_dom_diff_text_grep.py"
SPEC = importlib.util.spec_from_file_location("dom_diff_text_grep_runner", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _endpoint(provider: str, *, function_calling: bool = True):
    return SimpleNamespace(
        metadata={"provider": provider},
        capabilities=SimpleNamespace(function_calling=function_calling),
    )


def test_tool_transport_requires_one_supported_family():
    chat = SimpleNamespace(_clients=[_endpoint("azure_chat"), _endpoint("azure_chat")])
    responses = SimpleNamespace(
        _clients=[_endpoint("azure_responses"), _endpoint("azure_responses")]
    )
    mixed = SimpleNamespace(
        _clients=[_endpoint("azure_chat"), _endpoint("azure_responses")]
    )
    unsupported = SimpleNamespace(
        _clients=[_endpoint("azure_chat", function_calling=False)]
    )
    assert RUNNER.validate_tool_transport(chat) == "chat"
    assert RUNNER.validate_tool_transport(responses) == "responses"
    with pytest.raises(ValueError, match="homogeneous"):
        RUNNER.validate_tool_transport(mixed)
    with pytest.raises(ValueError, match="does not support"):
        RUNNER.validate_tool_transport(unsupported)


def test_runner_uses_strict_frozen_rubric_preflight_and_discards_projection():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "preflight_dom_diff_text_bundle" in source
    assert "require_frozen_rubric=True" in source
    assert "del parsed_frames" in source
    assert "DOMDiffTextGrepMMRubricAgent" in source
    assert "requested_evidence_mode" in source
    assert "validate_raw_tool_file_contract" in source


def test_raw_tool_contract_exposes_exact_numeric_task_root_files(tmp_path):
    actions = []
    for ordinal in (1, 2, 3):
        path = tmp_path / f"dom_diff{ordinal}.txt"
        path.write_text(f"raw source {ordinal}\n", encoding="utf-8")
        actions.append(
            {
                "id": ordinal,
                "dom_action_ordinal": ordinal,
                "dom_diff_text_path": str(path),
            }
        )
    input_dict = {"dom_actions": actions}
    RUNNER.validate_raw_tool_file_contract(tmp_path, input_dict)
    bundle = RawEvidenceBundle.from_dom_actions(actions, task_id=tmp_path.name)
    assert [item.filename for item in bundle.files] == [
        "dom_diff1.txt", "dom_diff2.txt", "dom_diff3.txt"
    ]
    assert [item.frame_index for item in bundle.files] == [0, 1, 2]
    assert [item.action_ordinal for item in bundle.files] == [1, 2, 3]
    assert [item.path for item in bundle.files] == [
        (tmp_path / f"dom_diff{ordinal}.txt").resolve()
        for ordinal in (1, 2, 3)
    ]


def test_raw_tool_contract_rejects_same_named_file_outside_task_root(tmp_path):
    task = tmp_path / "task"
    task.mkdir()
    (task / "dom_diff1.txt").write_text("expected task evidence\n", encoding="utf-8")
    outside = tmp_path / "other"
    outside.mkdir()
    path = outside / "dom_diff1.txt"
    path.write_text("not task evidence\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly the task-root"):
        RUNNER.validate_raw_tool_file_contract(
            task,
            {"dom_actions": [{
                "id": 1,
                "dom_action_ordinal": 1,
                "dom_diff_text_path": str(path),
            }]},
        )


def test_isolated_path_does_not_import_old_dom_compression_or_retrieval():
    agent_source = (
        Path(__file__).parents[1]
        / "src" / "webeval" / "rubric_agent" / "dom_diff_text_grep_agent.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "dom_diff_text_compaction",
        "dom_diff_text_retrieval",
        "dom_diff_text_summary",
        "dom_diff_summary",
        "dom_diff_text_s3_capping",
    )
    assert all(name not in agent_source for name in forbidden)


def test_runner_defines_separate_trace_artifacts_and_no_file_upload_path():
    source = SCRIPT.read_text(encoding="utf-8")
    assert ".model_calls.jsonl" in source
    assert ".tool_calls.jsonl" in source
    assert "grep_runtime_metrics" in source
    assert "input_file" not in source
    assert "file_data" not in source
    assert "files.create" not in source
