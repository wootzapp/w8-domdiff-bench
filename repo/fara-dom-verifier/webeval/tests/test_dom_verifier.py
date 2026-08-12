from __future__ import annotations

import asyncio
import hashlib
import json
from string import Template
from types import SimpleNamespace

import pytest

from webeval.rubric_agent.dom_evidence import (
    DOMEvidenceFrame,
    load_dom_frames,
    load_snapshot,
    project_dom_transition_timeline,
    project_frame,
    project_frame_retrieved,
    project_frames,
    project_semantic_transition,
)
from webeval.rubric_agent.mm_rubric_agent import MMRubricAgent, MMRubricAgentConfig
from webeval.rubric_agent import prompts


def _snapshot(ordinal: int = 1) -> dict:
    value = {
        "schema_version": "semantic-dom-snapshot/v1",
        "canonicalizer_version": "v1",
        "snapshot_id": f"snapshot-{ordinal:04d}",
        "ordinal": ordinal,
        "url": "https://example.test/cart",
        "title": "Cart",
        "captured_at": "2026-01-01T00:00:00Z",
        "hash": "",
        "nodes": [
            {
                "key": "node:" + "b" * 24,
                "parent_key": None,
                "frame_path": "main",
                "role": "status",
                "name": "Cart count",
                "text": "1 item",
                "value": "",
                "tag": "div",
                "states": {"live": "polite"},
            }
        ],
        "coverage": {
            "status": "partial",
            "rendered_dom": True,
            "nodes_seen": 2,
            "nodes_captured": 1,
            "node_limit": 5000,
            "text_limit": 1000,
            "truncated": False,
            "same_origin_frames": 1,
            "open_shadow_roots": 0,
            "cross_origin_frames": ["https://payments.example"],
            "canvas_count": 1,
            "image_without_alt_count": 0,
            "unsupported": ["canvas-pixels"],
            "errors": [],
        },
    }
    payload = {
        key: item
        for key, item in value.items()
        if key not in {"snapshot_id", "ordinal", "captured_at", "hash"}
    }
    value["hash"] = "sha256:" + hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return value


def _diff(before: dict | None = None, after: dict | None = None) -> dict:
    before = before or _snapshot(0)
    after = after or _snapshot(1)
    return {
        "schema_version": "semantic-dom-diff/v1",
        "canonicalizer_version": "v1",
        "diff_id": "diff-0001",
        "from_snapshot_id": "snapshot-0000",
        "to_snapshot_id": "snapshot-0001",
        "from_hash": before["hash"],
        "to_hash": after["hash"],
        "added": [],
        "removed": [],
        "updated": [
            {
                "key": "node:" + "b" * 24,
                "changes": {"text": {"before": "0 items", "after": "1 item"}},
            }
        ],
        "unchanged_count": 3,
    }


def _write_frame(tmp_path):
    before_path = tmp_path / "before_semantic_dom.json"
    snapshot_path = tmp_path / "semantic_dom.json"
    diff_path = tmp_path / "dom_diff.json"
    before = _snapshot(0)
    after = _snapshot(1)
    before_path.write_text(json.dumps(before), encoding="utf-8")
    snapshot_path.write_text(json.dumps(after), encoding="utf-8")
    diff_path.write_text(json.dumps(_diff(before, after)), encoding="utf-8")
    frames = load_dom_frames(
        [
            {
                "id": 1,
                "dom_action_ordinal": 1,
                "dom_action_id": "action-0001",
                "dom_before_snapshot_path": str(before_path),
                "dom_after_snapshot_path": str(snapshot_path),
                "dom_diff_path": str(diff_path),
                "dom_capture_status": "captured",
                "dom_coverage_status": "partial",
            }
        ]
    )
    return frames


def test_dom_loading_validation_and_projection(tmp_path):
    frames = _write_frame(tmp_path)
    assert frames[0].snapshot.coverage.status == "partial"

    text = project_frame(frames[0], frame_char_budget=2000)
    assert "coverage=partial" in text
    assert "cross-origin frame(s) excluded" in text
    assert "canvas" in text
    assert "0 items->1 item" in text
    assert text == project_frame(frames[0], frame_char_budget=2000)

    projected = project_frames(
        frames * 2, context_char_budget=300, frame_char_budget=200, top_k=1
    )
    assert len(projected) == 1
    assert len(projected[0]) <= 200


def test_dom_loader_rejects_wrong_schema(tmp_path):
    value = _snapshot()
    value["schema_version"] = "unknown"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(Exception):
        load_snapshot(path)


@pytest.mark.parametrize(
    ("contents", "error"),
    [
        ("{not-json", json.JSONDecodeError),
        (json.dumps([]), ValueError),
    ],
)
def test_dom_loader_rejects_malformed_evidence(tmp_path, contents, error):
    path = tmp_path / "malformed.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(error):
        load_snapshot(path)


def test_dom_loader_rejects_missing_and_hash_mismatched_evidence(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_snapshot(tmp_path / "missing.json")

    value = _snapshot()
    value["title"] = "tampered after hashing"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(Exception, match="snapshot hash mismatch"):
        load_snapshot(path)


def test_dom_loader_rejects_diff_hash_misalignment(tmp_path):
    before = _snapshot(0)
    after = _snapshot(1)
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    diff_path = tmp_path / "diff.json"
    before_path.write_text(json.dumps(before), encoding="utf-8")
    after_path.write_text(json.dumps(after), encoding="utf-8")
    diff = _diff(before, after)
    diff["to_hash"] = "sha256:" + "0" * 64
    diff_path.write_text(json.dumps(diff), encoding="utf-8")

    with pytest.raises(ValueError, match="target hash"):
        load_dom_frames(
            [
                {
                    "id": 1,
                    "dom_action_ordinal": 1,
                    "dom_before_snapshot_path": str(before_path),
                    "dom_after_snapshot_path": str(after_path),
                    "dom_diff_path": str(diff_path),
                }
            ]
        )


def test_projection_preserves_truncation_and_coverage_warning(tmp_path):
    value = _snapshot()
    value["coverage"].update(
        status="truncated",
        truncated=True,
        nodes_seen=999,
        nodes_captured=1,
    )
    payload = {
        key: item
        for key, item in value.items()
        if key not in {"snapshot_id", "ordinal", "captured_at", "hash"}
    }
    value["hash"] = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "truncated.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    snapshot = load_snapshot(path)
    frame = DOMEvidenceFrame(
        action_ordinal=1,
        after_snapshot_path=str(path),
        snapshot=snapshot,
    )
    projected = project_frame(frame, frame_char_budget=600)
    assert "coverage=truncated" in projected
    assert "node/text capture truncated" in projected
    assert "nodes=1/999" in projected


class _DummyClient:
    async def create(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("patched in test")

    def supports_json(self):
        return True


def _agent() -> MMRubricAgent:
    client = _DummyClient()
    return MMRubricAgent(
        config=MMRubricAgentConfig(o4mini_client=client, gpt5_client=client)
    )


def test_dom_relevance_schema_and_prompt_grounding(tmp_path, monkeypatch):
    agent = _agent()
    frames = _write_frame(tmp_path)
    prompts = []

    async def fake_call(messages, client, json_output=False):
        prompts.append(messages[-1]["content"])
        return '{"criterion_0": 8, "criterion_1": 2}'

    monkeypatch.setattr(agent, "_call_llm", fake_call)
    rubric = {
        "items": [
            {"criterion": "Cart updated", "description": "One item", "max_points": 1},
            {"criterion": "Checkout", "description": "Reached checkout", "max_points": 1},
        ]
    }
    result = asyncio.run(
        agent._score_dom_criterion_relevance(frames, rubric, "add item", "")
    )
    assert result[0][0] == 8
    assert result[0][1] == 2
    assert result[0]["evidence_idx"] == 0
    assert "ground truth ONLY" in prompts[0]
    assert "color" in prompts[0] and "canvas" in prompts[0]


def test_output_fields_are_dual_written_and_screenshot_import_regression():
    agent = _agent()
    dom_item = {
        "post_evidence_justification": "Covered DOM confirms cart state.",
        "post_evidence_earned_points": 2,
    }
    agent._dual_write_evidence_fields(dom_item)
    assert dom_item["post_image_justification"] == dom_item[
        "post_evidence_justification"
    ]
    assert dom_item["post_image_earned_points"] == 2

    screenshot_item = {
        "post_image_justification": "Pixels confirm cart state.",
        "post_image_earned_points": 2,
    }
    agent._dual_write_evidence_fields(screenshot_item)
    assert screenshot_item["post_evidence_justification"] == screenshot_item[
        "post_image_justification"
    ]
    assert screenshot_item["post_evidence_earned_points"] == 2

    # Screenshot defaults and legacy scoring remain unchanged.
    assert agent.config.batch_screenshot_analysis is True
    assert agent._compute_final_scores(
        {"items": [{"max_points": 2, "post_image_earned_points": 1}]}
    ) == {"total_max_points": 2.0, "total_earned_points": 1.0}


def test_datapoint_extraction_exposes_dom_paths_and_mode():
    summary = SimpleNamespace(
        index=1,
        action_name="click",
        action_args={},
        user_messages_before=[],
        url="https://example.test",
        state_description="",
        previous_error="",
        screenshot_path="",
        evidence_mode="dom",
        dom_action_ordinal=1,
        dom_action_id="action-0001",
        dom_evidence_schema_version="chromiumrl-dom-step/v1",
        dom_before_snapshot_path="/tmp/before_semantic_dom.json",
        dom_after_snapshot_path="/tmp/semantic_dom.json",
        dom_diff_path="/tmp/dom_diff.json",
        dom_before_page_state_path="/tmp/before_page_state.json",
        dom_after_page_state_path="/tmp/after_page_state.json",
        dom_verifier_action_path="/tmp/verifier_action.json",
        dom_capture_status="captured",
        dom_coverage_status="complete",
    )
    solver_log = SimpleNamespace(
        get_step_summaries=lambda: [summary],
        outcome=None,
    )
    task = SimpleNamespace(
        instruction="click item",
        environment_config={},
        metadata={"evidence_mode": "dom"},
    )
    extracted = MMRubricAgent._extract_input_from_datapoint(
        SimpleNamespace(task=task, solver_log=solver_log),
        screenshots_dir=None,
        redo_eval=False,
    )
    assert extracted["evidence_mode"] == "dom"
    assert extracted["dom_actions"][0]["dom_after_snapshot_path"].endswith(
        "semantic_dom.json"
    )


def test_all_dom_prompt_templates_are_valid_and_coverage_grounded():
    names = [
        name
        for name in dir(prompts)
        if name.startswith("DOM_") and name.endswith("_PROMPT")
    ]
    assert names
    for name in names:
        prompt = getattr(prompts, name)
        prompt_text = prompt.template if isinstance(prompt, Template) else prompt
        assert Template(prompt_text).is_valid(), name
        if name == "DOM_RETRIEVAL_TERMS_PROMPT":
            continue
        assert "ground truth ONLY" in prompt_text, name
        assert "declared coverage" in prompt_text, name

    rescoring_prompt = prompts.DOM_RUBRIC_RESCORING_PROMPT
    rescoring_text = (
        rescoring_prompt.template
        if isinstance(rescoring_prompt, Template)
        else rescoring_prompt
    )
    assert "post_evidence_earned_points" in rescoring_text
    assert "post_image_earned_points" not in rescoring_text


def test_dom_rescoring_accepts_generic_fields_and_writes_aliases(monkeypatch):
    agent = _agent()

    async def fake_call(messages, client, json_output=False):
        assert "post_evidence_earned_points" in messages[-1]["content"]
        return json.dumps(
            {
                "items": [
                    {
                        "criterion_idx": 0,
                        "applicable_evidence": "Semantic DOM frame 1.",
                        "post_evidence_justification": "Covered state confirms it.",
                        "post_evidence_earned_points": 2,
                    }
                ]
            }
        )

    monkeypatch.setattr(agent, "_call_llm", fake_call)
    rubric = {
        "items": [
            {
                "criterion": "Cart updated",
                "description": "One item is in the cart",
                "max_points": 2,
                "earned_points": 1,
                "justification": "Action-only baseline",
            }
        ]
    }
    evidence = {
        0: [
            {
                "evidence_text": "role=status text=1 item",
                "criterion_analysis": "Confirmed",
                "discrepancies": "None",
                "environment_issues_confirmed": False,
                "screenshot_idx": 0,
            }
        ]
    }
    result = asyncio.run(
        agent._rescore_rubric_with_screenshots(
            rubric,
            evidence,
            "add item",
            "",
            "Action 1: click",
            "done",
            total_screenshots=1,
            evidence_mode="dom",
        )
    )
    item = result["items"][0]
    assert item["post_evidence_earned_points"] == 2
    assert item["post_image_earned_points"] == 2


def _raw_transition_frame(ordinal: int, before_value: str, after_value: str):
    def node(value: str):
        return {
            "nodeId": ordinal,
            "tagName": "BUTTON",
            "role": "button",
            "isVisible": True,
            "isInViewport": True,
            "textContent": value,
            "attributes": [
                {"name": "aria-label", "value": f"Current state {value}"},
                {"name": "value", "value": value},
            ],
        }

    before = {
        "url": "https://example.test/state",
        "title": "State",
        "nodes": [node(before_value)],
    }
    after = {
        "url": "https://example.test/state",
        "title": "State",
        "nodes": [node(after_value)],
    }
    diff = {
        "schema_version": "chromiumrl-dom-diff/v1",
        "chromiumrl_result": {
            "summary": {},
            "textChanges": [
                {
                    "nodeId": ordinal,
                    "type": "text",
                    "tagName": "BUTTON",
                    "oldValue": before_value,
                    "newValue": after_value,
                    "nodeDetails": node(after_value),
                }
            ],
            "insertions": [],
            "attributeChanges": [],
            "deletions": [],
            "typeChanges": [],
            "moves": [],
            "layoutChanges": [],
            "styleChanges": [],
        },
    }
    return DOMEvidenceFrame(
        action_ordinal=ordinal,
        action_id=f"action-{ordinal:04d}",
        after_snapshot_path=f"/unused/after-{ordinal}.json",
        before_snapshot=before,
        snapshot=after,
        diff=diff,
        verifier_action={"name": "click", "arguments": {"x": 1, "y": 2}},
    )


def test_retrieved_frame_preserves_unfiltered_semantic_state():
    frame = _raw_transition_frame(1, "zero", "two")
    projected = project_frame_retrieved(
        frame,
        terms=["term-that-does-not-occur"],
        frame_char_budget=5000,
    )
    assert "UNFILTERED WHOLE-FRAME SEMANTIC CONTEXT" in projected
    assert "Current state two" in projected
    assert "zero" in projected and "two" in projected


def test_global_transition_timeline_is_chronological_and_not_term_filtered():
    frames = [
        _raw_transition_frame(2, "one", "two"),
        _raw_transition_frame(1, "zero", "one"),
    ]
    timeline = project_dom_transition_timeline(
        frames, context_char_budget=5000, frame_char_budget=2400
    )
    assert "not task/rubric filtered" in timeline
    assert timeline.index("FRAME 1") < timeline.index("FRAME 2")
    assert "Current state one" in timeline
    assert "Current state zero" in timeline
    assert "Current state two" in timeline
    assert project_semantic_transition(frames[0], char_budget=2000)


def test_dom_side_effect_prompt_receives_global_transition_evidence(monkeypatch):
    agent = _agent()
    prompts_seen = []

    async def fake_call(messages, client, json_output=False):
        prompts_seen.append(messages[-1]["content"])
        return json.dumps(
            {
                "reasoning": "No unrequested material state was represented.",
                "requires_penalty": False,
                "penalty_criteria": [],
            }
        )

    monkeypatch.setattr(agent, "_call_llm", fake_call)
    rubric = {
        "items": [
            {
                "criterion": "Requested state",
                "description": "Reach the requested state",
                "max_points": 1,
                "post_evidence_earned_points": 1,
                "post_evidence_justification": "Confirmed",
            }
        ]
    }
    evidence = {
        0: [
            {
                "evidence_text": "Criterion evidence.",
                "criterion_analysis": "Confirmed.",
                "discrepancies": "None.",
            }
        ]
    }
    result = asyncio.run(
        agent._detect_unsolicited_side_effects(
            rubric,
            evidence,
            "change state",
            "",
            "Action 1: click",
            evidence_mode="dom",
            global_transition_evidence="FRAME 1 explicit state zero->two",
        )
    )
    assert result["requires_penalty"] is False
    assert "Global Chronological State-Transition Evidence" in prompts_seen[0]
    assert "explicit state zero->two" in prompts_seen[0]
