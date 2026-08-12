from pathlib import Path

from stagehand_verifier.evidence_projection import select_evidence
from stagehand_verifier.loader import load_stagehand_trajectory


def test_projection_is_bounded_linked_and_clean(stagehand_task: Path) -> None:
    trajectory, _ = load_stagehand_trajectory(stagehand_task)
    criterion = {"id": 0, "criterion": "Alpha is enabled", "points": 1}
    selected = select_evidence(
        trajectory, 0, criterion, top_k=2, min_score=0,
        frame_char_budget=2_000, context_char_budget=3_000,
    )
    assert selected
    assert sum(len(item.projection) for item in selected) <= 3_100
    transition = next(item for item in selected if item.link.evidence_kind == "transition")
    assert transition.link.action_id is not None
    assert transition.link.action_id.startswith("stagehand-")
    assert transition.link.after_url
    combined = "\n".join(item.projection for item in selected)
    assert "[Buffer" not in combined
    assert "cdp_url" not in combined
    assert "screenshot.png" not in combined



def test_terminal_state_is_a_linked_actionless_retrieval_candidate(stagehand_task: Path) -> None:
    trajectory, _ = load_stagehand_trajectory(stagehand_task)
    criterion = {"id": 0, "criterion": "Alpha enabled in the final state", "points": 1}
    selected = select_evidence(
        trajectory, 0, criterion, top_k=3, min_score=0,
        frame_char_budget=4_000, context_char_budget=12_000,
    )
    matches = [item for item in selected if item.link.evidence_kind == "terminal_state"]
    assert len(matches) == 1
    terminal = matches[0]
    assert terminal.frame_index is None
    assert terminal.link.state_ordinal == trajectory.terminal_state.ordinal
    assert terminal.link.step is None
    assert terminal.link.action_id is None
    assert terminal.link.action_name is None
    assert terminal.link.source_paths[-2].endswith("step_003/aria.txt")
    assert terminal.link.source_paths[-1].endswith("step_003/page_state.json")
    assert '"action": null' in terminal.projection
