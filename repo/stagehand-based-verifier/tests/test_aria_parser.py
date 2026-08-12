from stagehand_verifier.aria_parser import parse_aria_tree


def test_parser_preserves_semantics_and_unknown_lines() -> None:
    nodes, unknown = parse_aria_tree(
        "[7-1] RootWebArea: Store\n  [7-2] checkbox: Red [checked]\nnot-an-aria-line\n"
    )
    assert [node.role for node in nodes] == ["RootWebArea", "checkbox"]
    assert nodes[1].raw_reference == "7-2"
    assert "checked" in nodes[1].states
    assert unknown == ("not-an-aria-line",)


def test_semantic_keys_are_deterministic() -> None:
    text = "[1] RootWebArea: A\n  [2] button: Continue\n"
    first = parse_aria_tree(text)[0]
    second = parse_aria_tree(text)[0]
    assert first[1].semantic_key == second[1].semantic_key
