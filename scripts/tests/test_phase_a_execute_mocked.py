import copy
import json
import tempfile
from pathlib import Path

from conftest import RUBRIC
from scripts import generate_frozen_rubric as generator


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


def test_phase_a_calls_one_microsoft_workflow_and_writes_both_staged_sidecars(
    pair_factory, monkeypatch
):
    pair = pair_factory(sidecars=False, metrics=False)
    clients = [_Client(), _Client()]

    def fake_from_path(*args, **kwargs):
        return clients.pop(0)

    workflow_invocations = 0

    async def fake_generate(self, task, init_url_context):
        nonlocal workflow_invocations
        workflow_invocations += 1
        # Simulate Microsoft's Step 0a and Step 0b calls through the instrumented judge.
        await self._call_llm([{"role": "user", "content": "step0a"}], self._gpt5_client)
        await self._call_llm([{"role": "user", "content": "step0b"}], self._gpt5_client)
        return copy.deepcopy(RUBRIC)

    monkeypatch.setattr(generator.GracefulRetryClient, "from_path", fake_from_path)
    monkeypatch.setattr(generator.MMRubricAgent, "_generate_rubric", fake_generate)
    monkeypatch.setattr(generator, "load_env_file", lambda path: None)
    monkeypatch.setattr(generator, "require_openai_key", lambda: None)

    experiment = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(dir=experiment / "rubrics") as output_name:
        output = Path(output_name)
        rubric = output / "task1.json"
        metrics = output / "task1_generation_metrics.json"
        rc = generator.main(
            [
                "--screenshot-task", str(pair["screenshot"]),
                "--dom-task", str(pair["dom"]),
                "--staged-root", str(pair["staged"]),
                "--rubric-file", str(rubric),
                "--metrics-file", str(metrics),
                "--eval-config", str(pair["config"]),
                "--env-file", str(output / "unused.env"),
                "--execute",
            ]
        )
        assert rc == 0
        assert workflow_invocations == 1
        metric_value = json.loads(metrics.read_text(encoding="utf-8"))
        assert metric_value["rubric_generation_calls"] == 2
        assert metric_value["token_usage"]["combined"]["total_tokens"] == 10
        for root in (pair["screenshot"], pair["dom"]):
            sidecar = json.loads(
                (root / "task_data_with_canonical_rubric.json").read_text(encoding="utf-8")
            )
            assert sidecar["precomputed_rubric"] == RUBRIC
