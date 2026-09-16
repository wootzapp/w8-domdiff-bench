import asyncio

from dom_model.dom_model_agent import DomModelRubricAgent


def test_grouping_is_inherited_and_prefers_later_state_on_tie():
    assert "_group_dom_states_by_criterion" not in DomModelRubricAgent.__dict__
    agent = object.__new__(DomModelRubricAgent)
    agent.config = type("Config", (), {"max_states_per_criterion": 2})()
    grouped = agent._group_dom_states_by_criterion(
        {
            0: {0: 8, "dom_model_state_idx": 0},
            1: {0: 8, "dom_model_state_idx": 1},
            2: {0: 7, "dom_model_state_idx": 2},
        },
        1,
    )
    assert grouped == {0: [1, 0]}



def test_loader_includes_all_n_plus_one_states(pair_factory):
    pair = pair_factory()
    agent = object.__new__(DomModelRubricAgent)
    agent.config = type("Config", (), {"dom_model_state_char_budget": 350000})()

    states = agent._load_dom_states(str(pair["dom"]), actions_list=[{}])

    assert [state.index for state in states] == [0, 1]
    assert [state.path.name for state in states] == ["dom_model0.txt", "dom_model1.txt"]
    assert agent.evidence_audit["state_selection_policy"] == "all_states_0_through_n"
    assert agent.evidence_audit["source_complete_state_count"] == 2
    assert agent.evidence_audit["complete_state_count"] == 2
    assert agent.evidence_audit["excluded_source_states"] == []

def test_filtering_is_inherited_unchanged():
    assert "_filter_irrelevant_dom_states" not in DomModelRubricAgent.__dict__


def test_microsoft_default_does_not_drop_zero_relevance_top_k():
    """Regression for Task 16: zero scores still reach the top-K analysis set."""

    agent = object.__new__(DomModelRubricAgent)
    agent.config = type(
        "Config", (), {"max_states_per_criterion": 2, "min_relevance_threshold": 0}
    )()
    relevance = {
        0: {0: 0, "dom_model_state_idx": 0},
        1: {0: 0, "dom_model_state_idx": 1},
        2: {0: 0, "dom_model_state_idx": 2},
    }
    grouped = agent._group_dom_states_by_criterion(relevance, 1)

    assert grouped == {0: [2, 1]}
    assert agent.config.min_relevance_threshold == 0


def test_zero_relevance_top_k_reaches_dom_evidence_analysis():
    agent = object.__new__(DomModelRubricAgent)
    agent.config = type("Config", (), {"max_iters": 1})()
    agent.evidence_audit = {"selection": {}}
    analyzed = []

    async def fake_analyze_pair(**kwargs):
        analyzed.append((kwargs["criterion_idx"], kwargs["state_idx"]))
        return kwargs["criterion_idx"], {
            "dom_model_evidence": "DOM_MODEL_STATE_INDEX: test",
            "criterion_analysis": "EVIDENCE_STATUS: UNKNOWN",
            "discrepancies": "None",
            "environment_issues_confirmed": False,
            "dom_model_state_idx": kwargs["state_idx"],
        }

    agent._analyze_pair = fake_analyze_pair
    evidence = asyncio.run(
        agent._analyze_dom_evidence_batched(
            dom_states=[object(), object(), object()],
            rubric={"items": [{"criterion": "Deliver final recommendation"}]},
            grouped_dom_states={0: [2, 1]},
            task="task",
            init_url_context="",
            action_history="",
            predicted_output="",
            relevance_scores={
                0: {0: 0}, 1: {0: 0}, 2: {0: 0},
            },
            min_relevance_threshold=0,
        )
    )

    assert analyzed == [(0, 2), (0, 1)]
    assert len(evidence[0]) == 2

