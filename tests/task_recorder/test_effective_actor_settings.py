"""Each actor manifest records the policy actually used for its observations."""

import json

import pytest

from w8bench import settings
from w8bench.task_recorder import runner
from w8bench.task_recorder.recorder_support import RunnerError

from tests.turn_benchmark.test_modes import no_network, run_pair


def test_actor_manifest_records_actual_viewport_capture_and_timeout_settings(run_pair):
    paths, *_ = run_pair
    contracts = []
    for mode, path in paths.items():
        manifest = json.loads((path / "manifest.json").read_text())
        contract = manifest["effective_settings"]
        contracts.append(contract)
        assert contract["viewport"] == [1365, 768]
        assert contract["max_turns"] == 6 and contract["settle_seconds"] == 0
        assert contract["snapshot_max_nodes"] == manifest["dom_capture_parameters"]["max_nodes"]
        assert contract["snapshot_max_text_chars"] == manifest["dom_capture_parameters"]["max_text_chars"]
        assert contract["agent_browser_timeout"] == 90 and contract["transport_timeout"] == 180 and contract["cdp_timeout"] == 90
        assert set(contract["prompt_sha256"]) == {"dom", "screenshot"}
        assert "recorder_code_sha256" not in contract
        assert contract["model"] == "gemini-3.1-pro-preview"
    assert contracts[0] == contracts[1]


@pytest.mark.asyncio
async def test_actor_refuses_changed_scheduled_policy_before_browser_or_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.1-pro-preview")
    expected = settings.actor_settings({"max_turns": 99})
    monkeypatch.setenv("W8_EXPECTED_ACTOR_SETTINGS", json.dumps(expected))
    monkeypatch.setattr(runner, "CDPClient", lambda *args, **kwargs: pytest.fail("settings drift reached the browser"))
    monkeypatch.setattr(runner.ModelClient, "_post", lambda *args: pytest.fail("settings drift reached the model"))
    args = runner.parse_args(["--env-file", str(tmp_path / "absent.env"), "--task", "Read the heading.",
        "--observation-mode", "screenshot", "--output-dir", str(tmp_path / "recordings"), "--api-key", "offline"])
    with pytest.raises(RunnerError, match="effective settings differ") as caught:
        await runner.run(args)
    assert "max_turns" in str(caught.value)
