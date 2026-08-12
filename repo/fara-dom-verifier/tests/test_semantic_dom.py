from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from jsonschema import validate

from fara.browser.semantic_dom import (
    DOMEvidenceFrame,
    DOMTrajectoryManifest,
    EVIDENCE_FRAME_SCHEMA_VERSION,
    REDACTION_MARKER,
    canonicalize_snapshot,
    diff_snapshots,
    persist_diff,
    persist_snapshot,
    redact_secrets,
    redact_text,
    redact_url,
    validate_diff_chain,
)


def _raw_snapshot(*nodes, url="https://example.test/products") -> dict:
    return {
        "url": url,
        "title": "  Example   Store ",
        "nodes": list(nodes),
        "coverage": {
            "nodes_seen": len(nodes),
            "node_limit": 100,
            "text_limit": 1000,
            "same_origin_frames": 1,
        },
    }


def _node(name: str, **overrides) -> dict:
    node = {
        "parent_index": None,
        "frame_path": "main",
        "role": "button",
        "name": name,
        "text": "",
        "value": "",
        "tag": "button",
        "states": {},
    }
    node.update(overrides)
    return node


def test_canonicalization_is_deterministic_and_ordered() -> None:
    raw = _raw_snapshot(
        _node("  Buy\nnow  "),
        _node("Search", role="textbox", tag="input", value="shoes"),
    )

    first = canonicalize_snapshot(raw, ordinal=0, captured_at="2026-01-01T00:00:00Z")
    second = canonicalize_snapshot(raw, ordinal=0, captured_at="2026-01-02T00:00:00Z")

    assert first.hash == second.hash
    assert [node.key for node in first.nodes] == sorted(node.key for node in first.nodes)
    assert {node.name for node in first.nodes} == {"Buy now", "Search"}
    assert first.title == "Example Store"


def test_distinct_nodes_keep_keys_when_dom_order_changes() -> None:
    first = canonicalize_snapshot(
        _raw_snapshot(_node("Alpha"), _node("Beta")), ordinal=0
    )
    second = canonicalize_snapshot(
        _raw_snapshot(_node("Beta"), _node("Alpha")), ordinal=0
    )

    assert {node.name: node.key for node in first.nodes} == {
        node.name: node.key for node in second.nodes
    }


def test_secret_redaction_covers_fields_values_text_and_urls() -> None:
    snapshot = canonicalize_snapshot(
        _raw_snapshot(
            _node(
                "Password",
                role="textbox",
                tag="input",
                value="correct horse battery staple",
                input_type="password",
            ),
            url="https://example.test/callback?token=super-secret&view=orders",
        ),
        ordinal=0,
    )

    password_node = next(node for node in snapshot.nodes if node.name == "Password")
    assert password_node.value == REDACTION_MARKER
    assert "super-secret" not in snapshot.url
    assert f"token={REDACTION_MARKER.replace('<', '%3C').replace('>', '%3E')}" in snapshot.url
    assert REDACTION_MARKER in redact_text("Authorization: Bearer abcdefghijklmnop")
    assert redact_secrets({"api_key": "abcdefgh", "safe": "public"}) == {
        "api_key": REDACTION_MARKER,
        "safe": "public",
    }
    assert "secret" not in redact_url("https://x.test/?access_token=secret")


def test_hash_changes_with_semantic_state_but_not_capture_time() -> None:
    unchecked = canonicalize_snapshot(
        _raw_snapshot(_node("Remember", role="checkbox", states={"checked": False})),
        ordinal=1,
        captured_at="2026-01-01T00:00:00Z",
    )
    checked = canonicalize_snapshot(
        _raw_snapshot(_node("Remember", role="checkbox", states={"checked": True})),
        ordinal=1,
        captured_at="2026-01-01T00:00:01Z",
    )

    assert unchecked.nodes[0].key == checked.nodes[0].key
    assert unchecked.hash != checked.hash


def test_aria_state_changes_are_updated_without_identity_churn() -> None:
    before = canonicalize_snapshot(
        _raw_snapshot(
            _node(
                "Filters",
                states={"expanded": "false", "pressed": "false", "busy": "true"},
            )
        ),
        ordinal=0,
    )
    after = canonicalize_snapshot(
        _raw_snapshot(
            _node(
                "Filters",
                states={"expanded": "true", "pressed": "true", "busy": "false"},
            )
        ),
        ordinal=1,
    )
    diff = diff_snapshots(before, after)

    assert not diff.added and not diff.removed
    assert diff.updated == (
        {
            "key": before.nodes[0].key,
            "changes": {
                "states": {
                    "before": {
                        "busy": "true",
                        "expanded": "false",
                        "pressed": "false",
                    },
                    "after": {
                        "busy": "false",
                        "expanded": "true",
                        "pressed": "true",
                    },
                }
            },
        },
    )


def test_reorder_and_volatile_unmodeled_attributes_are_noop() -> None:
    before = canonicalize_snapshot(
        _raw_snapshot(
            _node("Alpha", semantic_id="testid:alpha", volatile_class="css-123"),
            _node("Beta", semantic_id="testid:beta", react_key="random-1"),
        ),
        ordinal=0,
    )
    after = canonicalize_snapshot(
        _raw_snapshot(
            _node("Beta", semantic_id="testid:beta", react_key="random-999"),
            _node("Alpha", semantic_id="testid:alpha", volatile_class="css-456"),
        ),
        ordinal=1,
    )
    diff = diff_snapshots(before, after)

    assert before.hash == after.hash
    assert not diff.added and not diff.removed and not diff.updated
    assert diff.unchanged_count == 2


def test_navigation_replacement_changes_location_and_replaces_nodes() -> None:
    before = canonicalize_snapshot(
        _raw_snapshot(
            _node("Products", role="heading", tag="h1"),
            url="https://example.test/products",
        ),
        ordinal=0,
    )
    after = canonicalize_snapshot(
        _raw_snapshot(
            _node("Checkout", role="heading", tag="h1"),
            url="https://example.test/checkout",
        ),
        ordinal=1,
    )
    diff = diff_snapshots(before, after)

    assert before.url.endswith("/products")
    assert after.url.endswith("/checkout")
    assert [node["name"] for node in diff.removed] == ["Products"]
    assert [node["name"] for node in diff.added] == ["Checkout"]
    assert before.hash != after.hash


def test_truncation_and_coverage_are_hashed_and_reported() -> None:
    raw = _raw_snapshot(_node("Only captured node"))
    raw["coverage"].update(
        {
            "nodes_seen": 200,
            "node_limit": 1,
            "truncated": True,
            "cross_origin_frames": ["https://payments.test/?token=secret-value"],
            "errors": ["Authorization: Bearer abcdefghijklmnop"],
        }
    )
    snapshot = canonicalize_snapshot(raw, ordinal=0)

    assert snapshot.coverage.status == "truncated"
    assert snapshot.coverage.nodes_captured == 1
    assert snapshot.coverage.nodes_seen == 200
    assert snapshot.coverage.truncated is True
    assert "secret-value" not in snapshot.coverage.cross_origin_frames[0]
    assert REDACTION_MARKER in snapshot.coverage.errors[0]


def test_n_actions_produce_n_plus_one_snapshots_and_n_linked_diffs(tmp_path) -> None:
    action_count = 4
    snapshots = [
        canonicalize_snapshot(
            _raw_snapshot(_node(f"State {ordinal}")), ordinal=ordinal
        )
        for ordinal in range(action_count + 1)
    ]
    diffs = [
        diff_snapshots(snapshots[index - 1], snapshots[index])
        for index in range(1, len(snapshots))
    ]
    for snapshot in snapshots:
        persist_snapshot(tmp_path, snapshot)
    for diff in diffs:
        persist_diff(tmp_path, diff)

    assert len(list(tmp_path.glob("step_*/semantic_dom.json"))) == action_count + 1
    assert len(list(tmp_path.glob("step_*/dom_diff.json"))) == action_count
    assert validate_diff_chain(snapshots, diffs)


def test_diff_reports_added_removed_updated_and_noop_deterministically() -> None:
    before = canonicalize_snapshot(
        _raw_snapshot(
            _node("Remember", role="checkbox", states={"checked": False}),
            _node("Remove me"),
            _node("Unchanged"),
        ),
        ordinal=0,
    )
    after = canonicalize_snapshot(
        _raw_snapshot(
            _node("Remember", role="checkbox", states={"checked": True}),
            _node("Unchanged"),
            _node("Added"),
        ),
        ordinal=1,
    )

    diff = diff_snapshots(before, after)

    assert [node["name"] for node in diff.added] == ["Added"]
    assert [node["name"] for node in diff.removed] == ["Remove me"]
    assert len(diff.updated) == 1
    assert diff.updated[0]["changes"]["states"] == {
        "before": {"checked": False},
        "after": {"checked": True},
    }
    assert diff.unchanged_count == 1
    assert diff == diff_snapshots(before, after)

    noop_after = canonicalize_snapshot(
        _raw_snapshot(
            _node("Remember", role="checkbox", states={"checked": False}),
            _node("Remove me"),
            _node("Unchanged"),
        ),
        ordinal=1,
    )
    noop = diff_snapshots(before, noop_after)
    assert not noop.added and not noop.removed and not noop.updated
    assert noop.unchanged_count == 3
    assert before.hash == noop_after.hash


def test_snapshot_and_diff_conform_to_published_schemas() -> None:
    before = canonicalize_snapshot(_raw_snapshot(_node("Before")), ordinal=0)
    after = canonicalize_snapshot(_raw_snapshot(_node("After")), ordinal=1)
    schema_root = (
        Path(__file__).parents[1] / "src" / "fara" / "browser" / "schemas"
    )
    snapshot_schema = json.loads(
        (schema_root / "semantic_dom_snapshot_v1.schema.json").read_text()
    )
    diff_schema = json.loads((schema_root / "dom_diff_v1.schema.json").read_text())

    validate(json.loads(json.dumps(asdict(before))), snapshot_schema)
    validate(
        json.loads(json.dumps(asdict(diff_snapshots(before, after)))), diff_schema
    )

    manifest = DOMTrajectoryManifest(
        initial_snapshot="evidence/step_0000/semantic_dom.json",
        frames=[
            DOMEvidenceFrame(
                schema_version=EVIDENCE_FRAME_SCHEMA_VERSION,
                action_ordinal=1,
                action_id="action-0001",
                before_snapshot="evidence/step_0000/semantic_dom.json",
                after_snapshot="evidence/step_0001/semantic_dom.json",
                diff="evidence/step_0001/dom_diff.json",
                capture_status="complete",
                coverage_status="complete",
            )
        ],
    )
    manifest_schema = json.loads(
        (schema_root / "dom_trajectory_manifest_v2.schema.json").read_text()
    )
    validate(json.loads(json.dumps(manifest.to_dict())), manifest_schema)
