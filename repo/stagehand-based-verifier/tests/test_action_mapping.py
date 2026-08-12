from stagehand_verifier.action_mapping import sanitize_action_arguments, validate_action


def test_action_arguments_are_not_fabricated() -> None:
    original = {"direction": "down", "reasoning": "private"}
    assert sanitize_action_arguments("scroll", original) == {"direction": "down"}
    assert "pixels" not in sanitize_action_arguments("scroll", original)


def test_invalid_invocation_has_deterministic_error() -> None:
    errors = validate_action("goto", {})
    assert errors[0]["error_code"] == "6.1"
