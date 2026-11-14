"""Validate state/action chronology without inventing missing evidence."""

from __future__ import annotations

from typing import Any
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
    *, task_id: str, initial_url: str, actions: list[dict], states: list[DomModelState],
    evaluation_context: dict[str, Any] | None = None,
) -> AlignmentReceipt:
    context = evaluation_context or {}
    expected = context.get("expected_state_ids", list(range(len(actions) + 1)))
    if len(expected) != len(actions) + 1 or expected != list(range(expected[0], expected[0] + len(expected))):
        raise ValueError("Expected state identities must describe full N+1 chronology")
    gaps = context.get("format_gaps", {}).get("dom_model", [])
    if not set(gaps) <= set(expected):
        raise ValueError("DOM-model gaps outside full state chronology")
    if len(states) != len(expected) - len(gaps):
        raise ValueError(
            f"N actions require N+1 states: actions={len(actions)}, states={len(states)}"
        )
    if [state.index for state in states] != [index for index in expected if index not in gaps]:
        raise ValueError("DOM-model state ordinals are not contiguous")
    warnings: list[AlignmentWarning] = []
    by_index = {state.index: state for state in states}
    for index in gaps:
        warnings.append(AlignmentWarning("missing_recorded_state", "DOM-model capture unavailable", state_index=index))
    initial = by_index.get(expected[0])
    if initial is not None and initial.url and normalize_url(initial.url) != normalize_url(initial_url):
        task_url = urlsplit(normalize_url(initial_url))
        state_url = urlsplit(normalize_url(initial.url))
        if (
            task_url.scheme == state_url.scheme
            and task_url.netloc == state_url.netloc
        ):
            warnings.append(
                AlignmentWarning(
                    "initial_url_same_origin_redirect",
                    f"initial URL resolved from {initial_url!r} to {initial.url!r}",
                    state_index=0,
                )
            )
        elif (
            task_url.scheme in {"http", "https"}
            and task_url.scheme == state_url.scheme
            and task_url.hostname and state_url.hostname
            and (
                task_url.hostname == f"www.{state_url.hostname}"
                or state_url.hostname == f"www.{task_url.hostname}"
            )
            and all(value is None for value in (
                task_url.username, task_url.password, state_url.username, state_url.password
            ))
            and (task_url.port or (443 if task_url.scheme == "https" else 80))
                == (state_url.port or (443 if state_url.scheme == "https" else 80))
            and task_url.path == state_url.path
            and urlsplit(initial_url).query == urlsplit(initial.url).query
        ):
            # Preserve both URLs; a host alias is not proof of a redirect or success.
            warnings.append(
                AlignmentWarning(
                    "initial_url_www_alias",
                    f"Initial URLs differ only by www; no redirect chain is available: "
                    f"task={initial_url!r}, state={initial.url!r}",
                    state_index=0,
                )
            )
        else:
            raise ValueError(
                f"Initial URL differs: task={initial_url!r}, dom_model0={initial.url!r}"
            )
    if initial is not None and not initial.url:
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
        before = by_index.get(expected[ordinal - 1])
        after = by_index.get(expected[ordinal])
        observed = str(action.get("url") or "")
        if observed and after is not None and after.url and normalize_url(observed) != normalize_url(after.url):
            warnings.append(
                AlignmentWarning(
                    "post_action_url_mismatch",
                    f"logged URL {observed!r} differs from state URL {after.url!r}",
                    action_ordinal=ordinal,
                    state_index=ordinal,
                )
            )
        ref = args.get("ref")
        if ref is not None and before is not None and before.control_refs and str(ref) not in before.control_refs:
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
                "from_state": expected[ordinal - 1],
                "action_ordinal": ordinal,
                "to_state": expected[ordinal],
                "before_sha256": before.sha256 if before else None,
                "after_sha256": after.sha256 if after else None,
                "before_url": before.url if before else None,
                "after_url": after.url if after else None,
            }
        )
    for state in states:
        for code in state.warnings:
            warnings.append(AlignmentWarning(code, f"dom_model{state.index}: {code}", state_index=state.index))
    return AlignmentReceipt(
        task_id=task_id,
        action_count=len(actions),
        state_count=len(states),
        initial_state=expected[0],
        final_state=expected[-1],
        actions=tuple(normalized_actions),
        transitions=tuple(transitions),
        warnings=tuple(warnings),
    )
