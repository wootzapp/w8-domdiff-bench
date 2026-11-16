import pytest

from w8bench.verifier.dom_model.states import load_dom_model_states


def test_lossless_ordered_state_loading(pair_factory):
    pair = pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    assert [state.index for state in states] == [0, 1]
    assert states[0].url == "https://example.test/start"
    assert "value=Saved" in states[1].raw_text
    assert "save-button" in states[0].control_refs
    assert states[1].provenance.startswith("m1:L1-L")
    assert states[1].raw_text == (pair["dom"] / "dom_model1.txt").read_text(encoding="utf-8")


def test_rejects_gaps_and_malformed_names(pair_factory):
    pair = pair_factory()
    (pair["dom"] / "dom_model1.txt").rename(pair["dom"] / "dom_model2.txt")
    with pytest.raises(ValueError, match="contiguous"):
        load_dom_model_states(pair["dom"])
    (pair["dom"] / "dom_model2.txt").rename(pair["dom"] / "dom_model01.txt")
    with pytest.raises(ValueError, match="Malformed"):
        load_dom_model_states(pair["dom"])


def test_rejects_n_action_n_plus_two_states(pair_factory):
    pair = pair_factory()
    (pair["dom"] / "dom_model2.txt").write_text("URL: https://example.test/extra\nTitle: Extra\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"N\+1"):
        load_dom_model_states(pair["dom"], action_count=1)


def test_sparse_capture_loads_every_available_state_with_original_ids(tmp_path):
    import json
    context = {"expected_state_ids": [1, 2, 3, 4], "format_gaps": {"dom_model": [2]}}
    (tmp_path / "task_data.json").write_text(json.dumps({"evaluation_context": context}))
    for index in (1, 3, 4):
        (tmp_path / f"dom_model{index}.txt").write_text(f"URL: https://example.test/{index}\nTitle: State {index}\n")
    states = load_dom_model_states(tmp_path, action_count=3)
    assert [state.index for state in states] == [1, 3, 4]
    assert [state.path.name for state in states] == ["dom_model1.txt", "dom_model3.txt", "dom_model4.txt"]
    assert "initial browser state" in states[0].model_text(action_count=3, initial_state_index=1)
    assert "after action 2" in states[1].model_text(action_count=3, initial_state_index=1)
    assert "final browser state" in states[2].model_text(action_count=3, initial_state_index=1)
    # An available state may never be silently dropped by its own verifier.
    (tmp_path / "dom_model2.txt").write_text("URL: https://example.test/2\nTitle: Available\n")
    with pytest.raises(ValueError, match="contiguous"):
        load_dom_model_states(tmp_path, action_count=3)


def test_contiguous_loader_and_rendering_preserve_original_contract(pair_factory):
    import hashlib
    pair = pair_factory()
    states = load_dom_model_states(pair["dom"], action_count=1)
    for index, state in enumerate(states):
        path = pair["dom"] / f"dom_model{index}.txt"
        assert state.index == index
        assert state.raw_text == path.read_text()
        assert state.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        phase = "initial browser state (before action 1)" if index == 0 else "final browser state (after action 1)"
        assert state.model_text(action_count=1) == (
            f"DOM_MODEL_STATE_INDEX: {index}\nDOM_MODEL_PHASE: {phase}\n"
            f"DOM_MODEL_PROVENANCE: m{index}:L1-L{state.line_count}\nDOM_MODEL_SHA256: {state.sha256}\n"
            "DOM_MODEL_LIMITATION: This is structured textual browser evidence, not pixels. "
            "Do not infer pixel-only appearance. Missing content is unproven, especially when "
            "the source declares truncation.\n\n" + path.read_text()
        )
