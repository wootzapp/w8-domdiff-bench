from pathlib import Path

from dom_diff_text.evidence import parse_dom_diff_text
from dom_diff_text.utils.transitions import project_dom_transition_timeline


def test_transition_envelope_matches_legacy_text_frame_behavior():
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "dom_diff_text"
        / "changes_present"
        / "dom_diff1.txt"
    )
    frame = parse_dom_diff_text(fixture, task_id="task", action_ordinal=1)
    assert project_dom_transition_timeline([frame]) == (
        "GLOBAL DOM TRANSITION EVIDENCE (chronological, not task/rubric filtered)\n"
        "frames=1\n"
        "CROSS-FRAME SEMANTIC STATE CHANGES "
        "(N actions -> N+1 states; no task-term filtering):\n"
        "none represented\n"
        "---\n\n"
        "---\n"
        "FRAME 1 action_id=1 capture=complete coverage=text_diff_only\n"
        "action=\n"
        "before_page=unavailable\n"
        "after_page=unavailable\n"
        "UNFILTERED EXPLICIT CHANGES:\n"
        "counts={}\n\n"
        "AFTER STATE unavailable"
    )
