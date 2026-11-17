"""Full snapshot traversal preserves hierarchy order and handles deep pages."""

from w8bench.task_recorder.renderers.render_chromiumrl_snapshot_full import FullSnapshotRenderer


OPTIONS = {"max_text_chars": 1200, "text_mode": "deduped", "include_suppressed_text_notes": False,
    "include_action_index": True, "include_child_refs": True, "include_text_nodes": False,
    "include_inert_wrappers": False, "include_diff": False}


def test_snapshot_chain_below_capture_node_limit_renders_every_node():
    nodes = [{"ref": str(index), "tag": "section", "directText": f"Node {index}",
        **({"parentRef": str(index - 1)} if index else {})} for index in range(1100)]
    text = FullSnapshotRenderer({"nodes": nodes, "roots": ["0"]}, **OPTIONS).render()
    assert text.count("- ref=") == 1100
    assert "direct_text: Node 1099" in text
    assert text.index("direct_text: Node 0") < text.index("direct_text: Node 1099")


def test_cycle_and_repeated_roots_keep_the_original_depth_first_text():
    snapshot = {"roots": ["a", "b"], "nodes": [
        {"ref": "a", "parentRef": "b", "tag": "section", "sourceOrder": 0},
        {"ref": "b", "parentRef": "a", "tag": "section", "sourceOrder": 1},
    ]}
    expected = ["=== NODE TREE ===",
        "- ref=a <section> visible=? viewport=? hit=? occluded=? scroll=?",
        "  - ref=b <section> visible=? viewport=? hit=? occluded=? scroll=?",
        "    - ref=a [already shown]", "- ref=b [already shown]"]
    assert FullSnapshotRenderer(snapshot, **OPTIONS).render_tree() == expected


def test_wrapper_collapse_keeps_child_source_order_and_depth():
    snapshot = {"roots": ["root"], "nodes": [
        {"ref": "root", "tag": "div"},
        {"ref": "later", "parentRef": "root", "tag": "button", "sourceOrder": 2, "directText": "Second"},
        {"ref": "first", "parentRef": "root", "tag": "button", "sourceOrder": 1, "directText": "First"},
    ]}
    assert FullSnapshotRenderer(snapshot, **OPTIONS).render_tree() == ["=== NODE TREE ===",
        "- ref=first <button> visible=? viewport=? hit=? occluded=? scroll=?", "  direct_text: First",
        "- ref=later <button> visible=? viewport=? hit=? occluded=? scroll=?", "  direct_text: Second"]
