#!/usr/bin/env python3
"""Matching stages for patched ChromiumRL structured PageNodes.

The functions are safe before the C++/PDL refinement is deployed: nodes that
lack stablePath or fingerprint produce no matches in these stages and fall
through to the existing derived-path matcher.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


def match_repeated_groups_by_fingerprint(
    before_nodes: list[dict[str, Any]],
    after_nodes: list[dict[str, Any]],
    unmatched_before: set[int],
    unmatched_after: set[int],
) -> list[dict[str, Any]]:
    """Match unique fingerprints within the same repeated group.

    This pre-pass must run before positional path matching. Duplicate
    fingerprints are deliberately left unmatched instead of being guessed.
    """

    before_by_group: dict[str, list[int]] = defaultdict(list)
    after_by_group: dict[str, list[int]] = defaultdict(list)
    for index in unmatched_before:
        group = before_nodes[index].get("repeatedGroupId")
        if group:
            before_by_group[str(group)].append(index)
    for index in unmatched_after:
        group = after_nodes[index].get("repeatedGroupId")
        if group:
            after_by_group[str(group)].append(index)

    matched: list[dict[str, Any]] = []
    for group in sorted(set(before_by_group) & set(after_by_group)):
        before_fp: dict[str, list[int]] = defaultdict(list)
        after_fp: dict[str, list[int]] = defaultdict(list)

        for index in before_by_group[group]:
            fingerprint = before_nodes[index].get("fingerprint")
            if fingerprint:
                before_fp[str(fingerprint)].append(index)
        for index in after_by_group[group]:
            fingerprint = after_nodes[index].get("fingerprint")
            if fingerprint:
                after_fp[str(fingerprint)].append(index)

        for fingerprint in sorted(set(before_fp) & set(after_fp)):
            if len(before_fp[fingerprint]) != 1 or len(after_fp[fingerprint]) != 1:
                continue
            before_index = before_fp[fingerprint][0]
            after_index = after_fp[fingerprint][0]
            unmatched_before.discard(before_index)
            unmatched_after.discard(after_index)
            matched.append(
                {
                    "beforeIndex": before_index,
                    "afterIndex": after_index,
                    "strategy": "repeatedGroupFingerprint",
                    "key": f"{group}:{fingerprint}",
                }
            )

    return matched


def native_field_match_stages(
    before_nodes: list[dict[str, Any]],
    after_nodes: list[dict[str, Any]],
    unmatched_before: set[int],
    unmatched_after: set[int],
    unique_stage_matches: Callable[..., list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Match unique native stable paths, followed by native fingerprints."""

    matches: list[dict[str, Any]] = []
    matches.extend(
        unique_stage_matches(
            before_nodes,
            after_nodes,
            unmatched_before,
            unmatched_after,
            lambda node: node.get("stablePath") or None,
            "nativeStablePath",
        )
    )
    matches.extend(
        unique_stage_matches(
            before_nodes,
            after_nodes,
            unmatched_before,
            unmatched_after,
            lambda node: node.get("fingerprint") or None,
            "nativeFingerprint",
        )
    )
    return matches
