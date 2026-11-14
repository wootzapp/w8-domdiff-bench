import copy
import json
from pathlib import Path

import pytest

from .conftest import RUBRIC
from w8bench.verifier import generate_frozen_rubric as generator


class _Response:
    content = "{}"


class _Usage:
    def __init__(self, calls):
        self.prompt_tokens = 3 * calls
        self.completion_tokens = 2 * calls
        self.reasoning_tokens = calls


class _Endpoint:
    def __init__(self):
        self.calls = 0

    async def create(self, *args, **kwargs):
        self.calls += 1
        return _Response()

    def total_usage(self):
        return _Usage(self.calls)


class _Client:
    def __init__(self):
        self._clients = [_Endpoint()]

    async def create(self, *args, **kwargs):
        return await self._clients[0].create(*args, **kwargs)

    def supports_json(self):
        return True


@pytest.fixture
def catalog_case(tmp_path, monkeypatch):
    catalog = tmp_path / "tasks.jsonl"
    catalog.write_text("".join(json.dumps({"task_id": f"task_{number:02d}",
        "instruction": f"Inspect public page {number}.", "start_url": "https://example.test",
        "stopping_condition": "Report the visible fact.",
        "constraints": ["Use run-time evidence."]}) + "\n" for number in (1, 2)))
    monkeypatch.setattr(generator, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(generator, "require_local_packages", lambda: {})
    monkeypatch.setattr(generator, "validate_endpoint_configs", lambda path: {})
    monkeypatch.setattr(generator, "load_env_file", lambda path: None)
    monkeypatch.setattr(generator, "require_openai_key", lambda: None)
    monkeypatch.setattr(generator.GracefulRetryClient, "from_path", lambda *args, **kwargs: _Client())

    async def generate(self, task, context):
        assert "Stopping condition: Report the visible fact." in task
        assert "Constraints:\n- Use run-time evidence." in task
        await self._call_llm([{"role": "user", "content": "generation"}], self._gpt5_client)
        await self._call_llm([{"role": "user", "content": "dependency"}], self._gpt5_client)
        return copy.deepcopy(RUBRIC)

    monkeypatch.setattr(generator.MMRubricAgent, "_generate_rubric", generate)
    return {"root": tmp_path, "catalog": catalog, "drafts": tmp_path / "internal/rubrics/drafts",
        "frozen": tmp_path / "data/rubrics", "review": tmp_path / "internal/rubrics/review.json",
        "args": ["--catalog-file", str(catalog), "--draft-dir", str(tmp_path / "internal/rubrics/drafts"),
            "--rubric-dir", str(tmp_path / "data/rubrics")]}


def test_catalog_draft_dry_preflight_has_no_calls_or_writes(catalog_case, monkeypatch, capsys):
    monkeypatch.setattr(generator.GracefulRetryClient, "from_path",
        lambda *args, **kwargs: pytest.fail("dry preflight constructed a model client"))
    assert generator.main(catalog_case["args"] + ["--stage", "draft"]) == 0
    assert '"paid_calls_authorized": false' in capsys.readouterr().out
    assert not catalog_case["drafts"].exists()
    assert not catalog_case["frozen"].exists()


def test_catalog_drafts_use_original_workflow_then_resume_without_calls(catalog_case, monkeypatch):
    args = catalog_case["args"] + ["--stage", "draft", "--execute"]
    assert generator.main(args) == 0
    for number in (1, 2):
        receipt = json.loads((catalog_case["drafts"] / f"task_{number:02d}.metrics.json").read_text())
        assert receipt["status"] == "complete" and receipt["rubric_generation_calls"] == 2
        assert receipt["token_usage"]["gpt-5.2"]["total_tokens"] == 10
        assert receipt["token_usage"]["gpt-5.6-terra"]["total_tokens"] == 0
    monkeypatch.setattr(generator.GracefulRetryClient, "from_path",
        lambda *args, **kwargs: pytest.fail("completed rubric was regenerated"))
    assert generator.main(args) == 0
    assert not catalog_case["frozen"].exists()


def test_catalog_freeze_requires_review_approval_and_preserves_weights(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    with pytest.raises(ValueError, match="explicit approval"):
        generator.main(args + ["--stage", "freeze", "--execute"])
    review = json.loads(catalog_case["review"].read_text())
    review.update(approved_by="task reviewer", approval_date="2026-11-14")
    for task in review["tasks"]:
        task.update(approved=True, review_notes="All documented checks reviewed against task.")
    catalog_case["review"].write_text(json.dumps(review))
    assert generator.main(args + ["--stage", "freeze"]) == 0
    assert not catalog_case["frozen"].exists()
    assert generator.main(args + ["--stage", "freeze", "--execute"]) == 0
    assert generator.main(args + ["--stage", "freeze", "--execute"]) == 0
    for number in (1, 2):
        frozen = json.loads((catalog_case["frozen"] / f"task_{number:02d}.json").read_text())
        assert frozen["precomputed_rubric"] == RUBRIC
        assert frozen["instruction"].endswith("- Use run-time evidence.")
        assert frozen["rubric_approval_sha256"]


def test_changed_draft_invalidates_prior_approval(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    review = json.loads(catalog_case["review"].read_text())
    review.update(approved_by="reviewer", approval_date="2026-11-14")
    for item in review["tasks"]:
        item.update(approved=True, review_notes="Reviewed")
    catalog_case["review"].write_text(json.dumps(review))
    draft = catalog_case["drafts"] / "task_01.json"
    value = json.loads(draft.read_text())
    value["precomputed_rubric"]["items"][0]["description"] = "Corrected observable criterion."
    draft.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="hashes changed"):
        generator.main(args + ["--stage", "freeze", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    updated = json.loads(catalog_case["review"].read_text())
    assert updated["tasks"][0]["approved"] is False
    assert updated["tasks"][1]["approved"] is True
    assert list((catalog_case["review"].parent / "review_history").glob("*.json"))


def test_failed_draft_preserves_calls_and_resume_attempt_history(catalog_case, monkeypatch):
    original = generator.MMRubricAgent._generate_rubric

    async def fail_second(self, task, context):
        if "page 2" in task:
            await self._call_llm([{"role": "user", "content": "attempt"}], self._gpt5_client)
            raise KeyboardInterrupt()
        return await original(self, task, context)

    monkeypatch.setattr(generator.MMRubricAgent, "_generate_rubric", fail_second)
    with pytest.raises(KeyboardInterrupt):
        generator.main(catalog_case["args"] + ["--stage", "draft", "--execute"])
    path = catalog_case["drafts"] / "task_02.metrics.json"
    receipt = json.loads(path.read_text())
    assert receipt["status"] == "interrupted" and receipt["rubric_generation_calls"] == 1
    assert receipt["token_usage"]["gpt-5.2"]["total_tokens"] == 5
    assert not (catalog_case["drafts"] / "task_02.json").exists()
    monkeypatch.setattr(generator.MMRubricAgent, "_generate_rubric", original)
    generator.main(catalog_case["args"] + ["--stage", "draft", "--execute"])
    saved = json.loads(path.read_text())
    assert saved["status"] == "complete" and saved["attempt_history"][0]["rubric_generation_calls"] == 1


def test_catalog_edit_and_unsafe_task_id_fail_before_generation(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    rows = [json.loads(s) for s in catalog_case["catalog"].read_text().splitlines()]
    rows[0]["instruction"] = "Changed task."
    catalog_case["catalog"].write_text("".join(json.dumps(x) + "\n" for x in rows))
    with pytest.raises(ValueError, match="task changed"):
        generator.main(args + ["--stage", "draft", "--execute"])
    rows[0]["task_id"] = "../escape"
    catalog_case["catalog"].write_text("".join(json.dumps(x) + "\n" for x in rows))
    with pytest.raises(Exception, match="task id|Task ID|task-id|task ID"):
        generator.main(args + ["--stage", "draft"])


def test_public_catalog_has_only_eight_fields_and_shared_constraints():
    from collections import Counter
    root = Path(__file__).resolve().parents[2]
    rows = [json.loads(line) for line in (root / "data/tasks.jsonl").read_text().splitlines()]
    fields = {"task_id", "task_name", "category", "difficulty", "instruction", "start_url",
        "stopping_condition", "constraints"}
    assert len(rows) == 25
    assert {row["task_id"] for row in rows} == {f"task_{number:02d}" for number in range(1, 26)}
    assert Counter(row["difficulty"] for row in rows) == {"medium": 10, "hard": 10, "complex": 5}
    constraints = rows[0]["constraints"]
    assert len(constraints) >= 5 and all(isinstance(item, str) and item.strip() for item in constraints)
    for row in rows:
        assert set(row) == fields
        assert row["constraints"] == constraints
        assert len(row["instruction"].splitlines()) == 1 and len(row["instruction"]) <= 1800
        assert len(row["stopping_condition"].splitlines()) == 1
        assert all(isinstance(row[field], str) and row[field].strip() for field in fields - {"constraints"})
        generator.validate_task_definition(generator.catalog_task_instruction(row), row["start_url"])


def test_unreceipted_prior_attempt_is_unknown_not_zero_in_review(catalog_case):
    args = catalog_case["args"]
    generator.main(args + ["--stage", "draft", "--execute"])
    path = catalog_case["drafts"] / "task_02.metrics.json"
    receipt = json.loads(path.read_text())
    receipt.update(status="running")
    receipt.pop("rubric_generation_calls")
    receipt.pop("token_usage")
    path.write_text(json.dumps(receipt))
    (catalog_case["drafts"] / "task_02.json").unlink()
    generator.main(args + ["--stage", "draft", "--execute"])
    generator.main(args + ["--stage", "review", "--execute"])
    review = json.loads(catalog_case["review"].read_text())
    entry = review["tasks"][1]
    assert entry["generation_calls_all_attempts"] is None
    assert entry["generation_calls_known_lower_bound"] == 2
    assert entry["prior_attempt_usage"][0]["token_usage"] is None
    assert entry["generation_cost"]["estimated_usd"] is None
