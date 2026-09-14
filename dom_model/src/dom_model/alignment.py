"""Validate state/action chronology without inventing missing evidence."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from .schemas import AlignmentReceipt, AlignmentWarning, DomModelState


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value if "://" in value else f"https://{value}")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, "", ""))


def validate_alignment(
    *, task_id: str, initial_url: str, actions: list[dict], states: list[DomModelState]
) -> AlignmentReceipt:
    if len(states) != len(actions) + 1:
        raise ValueError(
            f"N actions require N+1 states: actions={len(actions)}, states={len(states)}"
        )
    if [state.index for state in states] != list(range(len(states))):
        raise ValueError("DOM-model state ordinals are not contiguous")
    warnings: list[AlignmentWarning] = []
    if states[0].url and normalize_url(states[0].url) != normalize_url(initial_url):
        task_url = urlsplit(normalize_url(initial_url))
        state_url = urlsplit(normalize_url(states[0].url))
        if (
            task_url.scheme == state_url.scheme
            and task_url.netloc == state_url.netloc
            and task_url.path == "/"
        ):
            warnings.append(
                AlignmentWarning(
                    "initial_url_same_origin_redirect",
                    f"initial URL resolved from {initial_url!r} to {states[0].url!r}",
                    state_index=0,
                )
            )
        else:
            raise ValueError(
                f"Initial URL differs: task={initial_url!r}, dom_model0={states[0].url!r}"
            )
    if not states[0].url:
        warnings.append(AlignmentWarning("missing_initial_state_url", "dom_model0 has no URL", state_index=0))
    transitions: list[dict] = []
    normalized_actions: list[dict] = []
    for ordinal, action in enumerate(actions, start=1):
        args = action.get("arguments") or {}
        if not isinstance(args, dict):
            raise ValueError(f"Action {ordinal} arguments must be an object")
        name = str(args.get("action") or action.get("action") or "")
        if not name:
            raise ValueError(f"Action {ordinal} has no action name")
        record = {
            "ordinal": ordinal,
            "name": name,
            "arguments": args,
            "observed_after_url": str(action.get("url") or ""),
        }
        normalized_actions.append(record)
        before = states[ordinal - 1]
        after = states[ordinal]
        observed = str(action.get("url") or "")
        if observed and after.url and normalize_url(observed) != normalize_url(after.url):
            warnings.append(
                AlignmentWarning(
                    "post_action_url_mismatch",
                    f"logged URL {observed!r} differs from state URL {after.url!r}",
                    action_ordinal=ordinal,
                    state_index=ordinal,
                )
            )
        ref = args.get("ref")
        if ref is not None and before.control_refs and str(ref) not in before.control_refs:
            warnings.append(
                AlignmentWarning(
                    "target_ref_not_found_in_pre_state",
                    f"ref {ref!r} is not exposed by dom_model{ordinal - 1}",
                    action_ordinal=ordinal,
                    state_index=ordinal - 1,
                )
            )
        transitions.append(
            {
                "from_state": ordinal - 1,
                "action_ordinal": ordinal,
                "to_state": ordinal,
                "before_sha256": before.sha256,
                "after_sha256": after.sha256,
                "before_url": before.url,
                "after_url": after.url,
            }
        )
    for state in states:
        for code in state.warnings:
            warnings.append(AlignmentWarning(code, f"dom_model{state.index}: {code}", state_index=state.index))
    return AlignmentReceipt(
        task_id=task_id,
        action_count=len(actions),
        state_count=len(states),
        initial_state=0,
        final_state=len(states) - 1,
        actions=tuple(normalized_actions),
        transitions=tuple(transitions),
        warnings=tuple(warnings),
    )
