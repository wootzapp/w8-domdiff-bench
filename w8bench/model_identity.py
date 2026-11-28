"""Configured model identities and response acceptance records."""
import re

from .usage import valid_token_component

MODEL_ACCEPTANCE_POLICY = "returned-model-acceptance/v2"


def match_model_id(configured, returned):
    """Accept the configured ID or a numeric/date/version suffix of that ID."""
    form = "refused"
    if isinstance(configured, str) and configured and isinstance(returned, str):
        if returned == configured:
            form = "exact"
        elif re.fullmatch(re.escape(configured) + r"-(?:[vV]\d+|\d+)(?:[._-]\d+)*", returned):
            form = "suffix"
    return {"matched": form != "refused", "form": form,
        "configured_model": configured, "returned_model": returned}


class ModelResponseRefusal(ValueError):
    """A response cannot be accepted under its recorded model policy."""


def response_acceptance(configured, returned, response, *, output_cap=None):
    match = match_model_id(configured, returned)
    reason = None
    if not match["matched"]:
        reason = f"returned model {returned!r} does not match configured model {configured!r}"
    else:
        status = response.get("status", response.get("response_status"))
        details = response.get("incomplete_details") or {}
        finish = str(response.get("finish_reason") or "").upper().split(".")[-1]
        output = (response.get("usage") or {}).get("output_tokens", (response.get("usage") or {}).get("completion_tokens"))
        incomplete = (status not in {None, "completed"} or response.get("incomplete") is True
            or response.get("truncated") is True or response.get("output_limit_hit") is True
            or details.get("reason") in {"max_output_tokens", "max_tokens", "length", "truncated"}
            or finish in {"LENGTH", "MAX_TOKENS", "MAX_OUTPUT_TOKENS", "INCOMPLETE", "TRUNCATED"}
            or output_cap is not None and valid_token_component(output) and output >= output_cap)
        if incomplete:
            reason = "incomplete response or output limit reached"
    return {"policy_version": MODEL_ACCEPTANCE_POLICY, "model_id_match": match,
        "accepted": reason is None, "refusal_reason": reason}
