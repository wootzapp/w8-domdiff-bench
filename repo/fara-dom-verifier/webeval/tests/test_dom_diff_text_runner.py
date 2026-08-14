from __future__ import annotations

import ast
import asyncio
import hashlib
import importlib.util
import json
import logging
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from webeval.rubric_agent import dom_diff_text_adapter


PROJECT_ROOT = Path(__file__).resolve().parents[2].parent.parent
DOM_REPO = PROJECT_ROOT / "repo" / "fara-dom-verifier"
SCRIPT = DOM_REPO / "webeval" / "scripts" / "verify_trajectories_dom_diff_text.py"
SUMMARY_RUNNER = (
    DOM_REPO / "webeval" / "scripts" / "verify_trajectories_dom_diff_summary.py"
)
SUMMARY_RUNNER_SHA256 = (
    "2c3cff38f17a40427a3ff06db08d8eaf3f666ed23a3a17958063504108302d58"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "verify_trajectories_dom_diff_text_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _copy_task(tmp_path: Path, task_name: str = "task5") -> Path:
    target = tmp_path / task_name
    shutil.copytree(PROJECT_ROOT / "data-new-short-dom" / task_name, target)
    return target


def _install_frozen_rubric(task_dir: Path) -> dict:
    path = task_dir / "task_data.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    task = payload[0] if isinstance(payload, list) else payload
    task["precomputed_rubric"] = {
        "items": [
            {
                "criterion": "Report the requested fact",
                "description": "The exact requested fact is reported.",
                "max_points": 7,
                "earned_points": "",
                "justification": "",
            },
            {
                "criterion": "Stop after research",
                "description": "No prohibited follow-up action is taken.",
                "max_points": 3,
                "earned_points": "",
                "justification": "",
            },
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return task


def _args(eval_config: Path) -> dict:
    return {
        "eval_config": str(eval_config),
        "judge_model": "gpt-5.2",
        "o4mini_model": "o4-mini",
        "rubric_threshold": 0.8,
        "max_evidence_per_criterion": 5,
        "mm_keypoint_score_threshold": 3,
        "majority_vote_instances": 1,
        "redo_eval": False,
        "success_criterion": "outcome",
        "dom_frame_char_budget": 16000,
        "dom_context_char_budget": 48000,
        "dom_top_k": None,
        "text_relevance_mode": "batched_llm",
        "text_frame_starting_tokens": 1500,
        "text_trajectory_starting_tokens": 16000,
        "text_analysis_starting_tokens": 24000,
        "text_max_chunk_tokens": 256,
        "text_allow_budget_expansion": True,
        "text_model_context_window_tokens": 128000,
        "text_relevance_completion_reserve_tokens": 4096,
        "text_analysis_completion_reserve_tokens": 8192,
        "text_prompt_headroom_tokens": 1024,
        "request_timeout_seconds": 180.0,
        "max_api_retries": 2,
    }


def test_runner_import_has_no_client_logging_or_artifact_side_effects(
    tmp_path: Path,
) -> None:
    before_handlers = tuple(logging.getLogger().handlers)
    before_files = set(tmp_path.rglob("*"))
    module = _load_runner()
    assert module._GLOBAL_AGENT is None
    assert tuple(logging.getLogger().handlers) == before_handlers
    assert set(tmp_path.rglob("*")) == before_files
    assert not hasattr(module, "GracefulRetryClient")


def test_preflight_failure_occurs_before_client_initialization(
    tmp_path: Path, monkeypatch
) -> None:
    task = _copy_task(tmp_path)
    config = tmp_path / "endpoints.json"
    config.write_text("{}", encoding="utf-8")
    report = tmp_path / "preflight.jsonl"
    called = False

    def forbidden_pool_init(args):
        nonlocal called
        del args
        called = True
        raise AssertionError("judge clients must not be initialized")

    monkeypatch.setattr(runner, "_pool_init", forbidden_pool_init)
    with pytest.raises(SystemExit, match="no judge clients were initialized"):
        runner.main(
            [
                "--input",
                str(task),
                "--eval-config",
                str(config),
                "--report",
                str(report),
            ]
        )
    assert called is False
    row = json.loads(report.read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == "input_validation_error"
    assert "frozen" in row["error"].casefold()


def test_frozen_preflight_succeeds_without_constructing_clients(tmp_path: Path) -> None:
    task = _copy_task(tmp_path)
    runtime_task_data = _install_frozen_rubric(task)
    (task / "task_data_with_canonical_rubric.json").write_text(
        json.dumps([runtime_task_data]), encoding="utf-8"
    )
    trajectory, task_data, input_dict, frames = runner.preflight_trajectory(task)
    assert trajectory.path == task
    assert task_data["precomputed_rubric"] == input_dict["precomputed_rubric"]
    assert input_dict["frozen_input_denominator"] == 10
    assert len(frames) == 1
    assert runner._GLOBAL_AGENT is None


def test_sidecar_is_allowed_but_never_used_as_frozen_rubric_fallback(
    tmp_path: Path,
) -> None:
    task = _copy_task(tmp_path)
    base_payload = json.loads((task / "task_data.json").read_text(encoding="utf-8"))
    sidecar_payload = json.loads(json.dumps(base_payload))
    sidecar_task = (
        sidecar_payload[0] if isinstance(sidecar_payload, list) else sidecar_payload
    )
    sidecar_task["precomputed_rubric"] = {
        "items": [
            {
                "criterion": "Sidecar-only criterion",
                "description": "This must not enter verifier input implicitly.",
                "max_points": 1,
                "earned_points": "",
                "justification": "",
            }
        ]
    }
    (task / "task_data_with_canonical_rubric.json").write_text(
        json.dumps(sidecar_payload), encoding="utf-8"
    )

    with pytest.raises(
        ValueError, match="Scoring requires a task-specific frozen precomputed_rubric"
    ):
        runner.preflight_trajectory(task)

    _, input_dict, _ = dom_diff_text_adapter.preflight_dom_diff_text_bundle(
        task,
        base_payload[0] if isinstance(base_payload, list) else base_payload,
        require_frozen_rubric=False,
    )
    assert input_dict["precomputed_rubric"] is None


def test_unexpected_task_data_json_is_still_rejected(tmp_path: Path) -> None:
    task = _copy_task(tmp_path)
    (task / "task_data_backup.json").write_text("{}", encoding="utf-8")
    task_data = json.loads((task / "task_data.json").read_text(encoding="utf-8"))[0]
    with pytest.raises(ValueError, match="task_data_backup.json"):
        dom_diff_text_adapter.preflight_dom_diff_text_bundle(
            task, task_data, require_frozen_rubric=False
        )


def test_exact_control_file_contract_rejects_alternate_log_name(tmp_path: Path) -> None:
    task = _copy_task(tmp_path)
    (task / "websurfer.log").write_text("duplicate", encoding="utf-8")
    task_data = json.loads((task / "task_data.json").read_text(encoding="utf-8"))[0]
    with pytest.raises(ValueError, match="exactly web_surfer.log"):
        dom_diff_text_adapter.preflight_dom_diff_text_bundle(
            task, task_data, require_frozen_rubric=False
        )


def test_runner_rejects_global_frame_top_k() -> None:
    with pytest.raises(SystemExit):
        runner.parse_args(
            [
                "--input",
                "unused",
                "--eval-config",
                "unused",
                "--dom-top-k",
                "1",
            ]
        )


def test_cache_identity_covers_source_rubric_endpoint_and_every_text_budget(
    tmp_path: Path,
) -> None:
    task = _copy_task(tmp_path)
    config = tmp_path / "endpoints.json"
    config.write_text('{"endpoint":"test-a"}', encoding="utf-8")
    args = _args(config)
    original, original_config = runner._verifier_identity(args, task)
    assert original_config["source_text_sha256"]
    assert original_config["frozen_rubric_sha256"] is None
    assert (
        original_config["eval_config_sha256"]
        == hashlib.sha256(config.read_bytes()).hexdigest()
    )

    budget_keys = (
        "text_frame_starting_tokens",
        "text_trajectory_starting_tokens",
        "text_analysis_starting_tokens",
        "text_max_chunk_tokens",
        "text_model_context_window_tokens",
        "text_relevance_completion_reserve_tokens",
        "text_analysis_completion_reserve_tokens",
        "text_prompt_headroom_tokens",
    )
    for key in budget_keys:
        changed = dict(args)
        changed[key] += 1
        assert runner._verifier_identity(changed, task)[0] != original
    changed = dict(args)
    changed["text_allow_budget_expansion"] = False
    assert runner._verifier_identity(changed, task)[0] != original

    _install_frozen_rubric(task)
    rubric_identity, rubric_config = runner._verifier_identity(args, task)
    assert rubric_identity != original
    assert rubric_config["frozen_rubric_sha256"]
    config.write_text('{"endpoint":"test-b"}', encoding="utf-8")
    assert runner._verifier_identity(args, task)[0] != rubric_identity


def test_cache_acceptance_and_score_path_are_text_specific(tmp_path: Path) -> None:
    task = _copy_task(tmp_path)
    config = tmp_path / "endpoints.json"
    config.write_text("{}", encoding="utf-8")
    args = _args(config)
    identity, _ = runner._verifier_identity(args, task)
    cache = tmp_path / "score.json"
    cache.write_text(json.dumps({"cache_identity": identity, "result": {}}))
    assert runner._read_cache(cache, args, task) is not None
    args["text_analysis_starting_tokens"] += 1
    assert runner._read_cache(cache, args, task) is None
    assert "dom_diff_text" in runner._score_path(task, args).name


class _Endpoint:
    def __init__(self, prompt: int, completion: int, reasoning: int):
        self.usage = SimpleNamespace(
            prompt_tokens=prompt,
            completion_tokens=completion,
            reasoning_tokens=reasoning,
        )

    async def create(self, *args, **kwargs):
        del args, kwargs
        return "ok"

    def total_usage(self):
        return self.usage


class _RetryingClient:
    def __init__(self):
        self._clients = [_Endpoint(10, 4, 2), _Endpoint(20, 6, 3)]

    async def create(self, *args, **kwargs):
        del args, kwargs
        await self._clients[0].create()
        await self._clients[1].create()
        return "ok"


def test_runner_plumbing_counts_usage_logical_calls_attempts_and_retries() -> None:
    client = _RetryingClient()
    assert runner._usage_dict(client) == {
        "prompt_tokens": 30,
        "completion_tokens": 10,
        "reasoning_tokens": 5,
        "total_tokens": 40,
    }
    runner._instrument_client_calls(client)
    asyncio.run(client.create())
    assert runner._call_metrics(client) == {
        "logical_calls": 1,
        "api_attempts": 2,
        "retries": 1,
    }
    assert runner._delta(
        {"prompt_tokens": 15, "completion_tokens": 9},
        {"prompt_tokens": 10, "completion_tokens": 4},
    ) == {"prompt_tokens": 5, "completion_tokens": 5}


def test_local_action_mapping_matches_protected_source_before_target_extensions() -> (
    None
):
    tree = ast.parse((DOM_REPO / "src" / "fara" / "fara_agent.py").read_text())
    source_mapping = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "FARA_ACTION_DEFINITIONS":
                source_mapping = ast.literal_eval(node.value)
                break
    assert source_mapping == dom_diff_text_adapter._BASE_FARA_ACTION_DEFINITIONS
    local = dom_diff_text_adapter.semantic_action_definitions()
    for name in ("left_click", "type", "scroll"):
        assert local[name] == source_mapping[name] | {"ref", "target"}
    assert local["visit_url"] == source_mapping["visit_url"]


def test_protected_summary_runner_hash_is_unchanged() -> None:
    assert (
        hashlib.sha256(SUMMARY_RUNNER.read_bytes()).hexdigest() == SUMMARY_RUNNER_SHA256
    )
