from pathlib import Path

import pytest

from dom_model.state_parser import load_dom_model_states


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

