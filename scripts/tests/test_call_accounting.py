from scripts.common import sum_call_metrics, sum_usage


def test_call_and_token_accounting_keeps_reasoning_as_subset():
    calls = sum_call_metrics(
        {"logical_calls": 2, "api_attempts": 3},
        {"logical_calls": 1, "api_attempts": 1},
    )
    assert calls == {"logical_calls": 3, "api_attempts": 4, "retries": 1}
    usage = sum_usage(
        {"prompt_tokens": 10, "completion_tokens": 5, "reasoning_tokens": 3, "total_tokens": 15},
        {"prompt_tokens": 4, "completion_tokens": 2, "reasoning_tokens": 1, "total_tokens": 6},
    )
    assert usage == {"prompt_tokens": 14, "completion_tokens": 7, "reasoning_tokens": 4, "total_tokens": 21}

