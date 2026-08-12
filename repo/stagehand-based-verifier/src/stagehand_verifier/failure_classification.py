from __future__ import annotations

from typing import Any

from .taxonomy import canonical_taxonomy_entry


def normalize_failure(
    response: dict[str, Any], deterministic_errors: list[dict[str, Any]]
) -> dict[str, Any]:
    """Constrain judge output to the pinned two-level taxonomy."""
    result = dict(response)
    raw_code = result.get("error_code")
    code = str(raw_code) if raw_code not in {None, "", "null"} else None
    entry = canonical_taxonomy_entry(code)
    if entry is None and deterministic_errors:
        first = deterministic_errors[0]
        fallback = str(first.get("error_code") or "")
        fallback_entry = canonical_taxonomy_entry(fallback)
        if fallback_entry is not None:
            code = fallback
            entry = fallback_entry
            result.setdefault("first_failure_step", first.get("step"))
            result["reasoning"] = (
                str(result.get("reasoning") or "")
                + f" Deterministic tool validation: {first.get('message', '')}"
            ).strip()
    if entry is not None:
        result["error_code"] = code
        result["error_category"] = entry[0]
        result["error_type"] = entry[1]
    elif code is None:
        result["error_code"] = None
        result["error_category"] = str(result.get("error_category") or "none")
    else:
        result["error_code"] = None
        result["error_category"] = "unknown"
        result["error_type"] = "Unclassified failure"
        result["reasoning"] = (
            str(result.get("reasoning") or "")
            + f" Judge returned unsupported taxonomy code {code!r}."
        ).strip()
    return result
