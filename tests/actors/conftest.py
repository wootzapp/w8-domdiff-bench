"""Actor observation and request fixtures."""
import json
import pytest

@pytest.fixture
def actor_observation(tmp_path):
    from w8bench.task_recorder.capture import CaptureBundle

    state = tmp_path / "steps" / "step_001"
    state.mkdir(parents=True)
    snapshot = state / "dom.json"
    snapshot.write_text(json.dumps({"nodes": []}))
    (state / "dom_model.txt").write_text("Status: Ready\n", encoding="utf-8")
    return CaptureBundle(
        snapshot={"url": "https://example.test/"},
        snapshot_path=snapshot,
        model_text="Status: Ready\n",
        agent_browser_action_text='- button "Save" [ref=e1]\n',
        agent_browser_refs=frozenset({"e1"}),
        document_url="https://example.test/",
    )

@pytest.fixture
def actor_request_args(actor_observation, tmp_path, monkeypatch):
    monkeypatch.setenv("ACTOR_MODEL", "gemini-3.8-flash")
    return {
        "task": "Inspect the example page.",
        "step": 1,
        "max_steps": 2,
        "bundle": actor_observation,
        "task_memory": "",
        "recent_actions": [],
        "turn_dir": tmp_path / "turns" / "turn_000001",
        "viewport": (1365, 768),
    }
