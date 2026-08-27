from dom_model.dom_model_agent import DomModelRubricAgent


def test_grouping_is_inherited_and_prefers_later_state_on_tie():
    assert "_group_screenshots_by_criterion" not in DomModelRubricAgent.__dict__
    agent = object.__new__(DomModelRubricAgent)
    agent.config = type("Config", (), {"max_images_per_criterion": 2})()
    grouped = agent._group_screenshots_by_criterion(
        {
            0: {0: 8, "screenshot_idx": 0},
            1: {0: 8, "screenshot_idx": 1},
            2: {0: 7, "screenshot_idx": 2},
        },
        1,
    )
    assert grouped == {0: [1, 0]}


def test_filtering_is_inherited_unchanged():
    assert "_filter_irrelevant_screenshots" not in DomModelRubricAgent.__dict__

