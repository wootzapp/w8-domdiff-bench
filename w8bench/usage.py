"""Provider token components with explicit unknown values."""
import math


def valid_token_component(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def known_token_component(value):
    return value if valid_token_component(value) else None
