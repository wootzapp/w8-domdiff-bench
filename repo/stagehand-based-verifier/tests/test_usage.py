from stagehand_verifier.usage_delta import usage_delta


def test_usage_delta_is_per_task_not_cumulative() -> None:
    before = {
        "by_role": {
            "main.outcome": {
                "calls": 1, "prompt_tokens": 10, "completion_tokens": 5,
                "reasoning_tokens": 2, "total_tokens": 15,
            }
        }
    }
    after = {
        "by_role": {
            "main.outcome": {
                "calls": 2, "prompt_tokens": 25, "completion_tokens": 11,
                "reasoning_tokens": 3, "total_tokens": 36,
            }
        }
    }
    delta = usage_delta(before, after)
    assert delta["total"]["calls"] == 1
    assert delta["total"]["prompt_tokens"] == 15
    assert delta["total"]["completion_tokens"] == 6
    assert delta["total"]["total_tokens"] == 21
