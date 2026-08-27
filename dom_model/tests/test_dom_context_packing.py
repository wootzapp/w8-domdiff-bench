from dom_model.context_packing import pack_state
from dom_model.state_parser import load_dom_model_states


def test_oversized_state_packs_records_and_reports_every_omission(tmp_path):
    body = "".join(f"Control {index}: role=button name=Button-{index} value=Value-{index}\n" for index in range(30))
    (tmp_path / "dom_model0.txt").write_text(
        "URL: https://example.test/final\n"
        "Title: Final page\n"
        "Snapshot: returnedNodes=32 groups=1 truncated=true\n"
        "=== VISIBLE CONTENT ===\n"
        + body
        + "Dialog: Saved successfully\n"
        + "Error: none\n",
        encoding="utf-8",
    )
    state = load_dom_model_states(tmp_path, action_count=0)[0]
    rendered, omissions = pack_state(state, action_count=0, max_chars=700)
    assert omissions
    assert "URL: https://example.test/final" in rendered
    assert "Title: Final page" in rendered
    assert "truncated=true" in rendered
    assert "Dialog: Saved successfully" in rendered
    assert "Error: none" in rendered
    assert "DOM_MODEL_CONTEXT_OMISSIONS:" in rendered
    assert all(item["provenance"].startswith("m0:L") for item in omissions)
    assert all(item["char_count"] > 0 and item["estimated_tokens"] > 0 for item in omissions)
