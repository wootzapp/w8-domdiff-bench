from __future__ import annotations

from collections import defaultdict

from .schemas import AriaNode, NodeChange, SemanticDiff, SemanticState


def _node_value(node: AriaNode) -> str:
    states = f" states={','.join(node.states)}" if node.states else ""
    return f"role={node.role} name={node.accessible_name}{states}".strip()


def _match_nodes(
    before: tuple[AriaNode, ...], after: tuple[AriaNode, ...]
) -> tuple[list[tuple[AriaNode, AriaNode]], list[AriaNode], list[AriaNode]]:
    """Conservatively match nodes without assuming raw references survive navigation."""
    after_by_key: defaultdict[str, list[AriaNode]] = defaultdict(list)
    for node in after:
        after_by_key[node.semantic_key].append(node)

    matched: list[tuple[AriaNode, AriaNode]] = []
    removed: list[AriaNode] = []
    used_after: set[int] = set()
    for old in before:
        candidates = after_by_key.get(old.semantic_key, [])
        new = next((item for item in candidates if id(item) not in used_after), None)
        if new is None:
            removed.append(old)
        else:
            used_after.add(id(new))
            matched.append((old, new))
    added = [node for node in after if id(node) not in used_after]

    # A stable raw reference on the same page can expose a name/state update
    # that changed the semantic key. Only use it when role also matches.
    removed_by_ref = {node.raw_reference: node for node in removed if node.raw_reference}
    added_by_ref = {node.raw_reference: node for node in added if node.raw_reference}
    rematched_refs = set(removed_by_ref) & set(added_by_ref)
    for reference in sorted(rematched_refs):
        old = removed_by_ref[reference]
        new = added_by_ref[reference]
        if old.role.casefold() != new.role.casefold():
            continue
        matched.append((old, new))
        removed.remove(old)
        added.remove(new)
    return matched, removed, added


def compare_states(before: SemanticState, after: SemanticState) -> SemanticDiff:
    matched, removed, added = _match_nodes(before.nodes, after.nodes)
    changes: list[NodeChange] = []
    for old, new in matched:
        if _node_value(old) != _node_value(new):
            changes.append(
                NodeChange(
                    kind="updated",
                    semantic_key=new.semantic_key,
                    raw_reference_before=old.raw_reference,
                    raw_reference_after=new.raw_reference,
                    before=_node_value(old),
                    after=_node_value(new),
                )
            )
    changes.extend(
        NodeChange(
            kind="removed",
            semantic_key=node.semantic_key,
            raw_reference_before=node.raw_reference,
            before=_node_value(node),
        )
        for node in removed
    )
    changes.extend(
        NodeChange(
            kind="added",
            semantic_key=node.semantic_key,
            raw_reference_after=node.raw_reference,
            after=_node_value(node),
        )
        for node in added
    )
    changes.sort(key=lambda item: (item.kind, item.semantic_key))
    return SemanticDiff(
        node_changes=tuple(changes),
        url_before=before.page.url,
        url_after=after.page.url,
        title_before=before.page.title,
        title_after=after.page.title,
        scroll_before=(before.page.scroll_x, before.page.scroll_y),
        scroll_after=(after.page.scroll_x, after.page.scroll_y),
    )
