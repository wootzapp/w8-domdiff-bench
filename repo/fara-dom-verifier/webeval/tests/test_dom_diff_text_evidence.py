from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from webeval.rubric_agent.dom_diff_adapter import load_dom_diff_trajectory
from webeval.rubric_agent.dom_diff_text_adapter import (
    build_dom_diff_text_input,
    discover_dom_diff_text_paths,
    preflight_dom_diff_text_bundle,
    reject_forbidden_evidence,
    semantic_action_definitions,
    validate_cross_modality_semantic_pair,
    validate_frozen_rubric,
    validate_text_input_paths,
)
from webeval.rubric_agent.dom_diff_text_evidence import parse_dom_diff_text
from webeval.rubric_agent.dom_diff_text_evidence import load_dom_diff_text_frames


FIXTURES = Path(__file__).parent / "fixtures" / "dom_diff_text"
PROJECT_ROOT = Path(__file__).resolve().parents[2].parent.parent


@pytest.mark.parametrize(
    ("folder", "status", "action_type"),
    [
        ("changes_present", "changes_present", "click"),
        ("document_replaced", "document_replaced", "navigate"),
        ("viewport_content_changed", "viewport_content_changed", "scroll"),
    ],
)
def test_parse_all_statuses(folder: str, status: str, action_type: str) -> None:
    path = FIXTURES / folder / "dom_diff1.txt"
    raw = path.read_bytes()
    frame = parse_dom_diff_text(path, task_id="task", action_ordinal=1)
    assert frame.status == status
    assert frame.action_type == action_type
    assert frame.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert frame.source_bytes == len(raw)
    assert frame.diff == {}
    assert frame.before_snapshot is None
    assert frame.snapshot is None
    assert frame.before_page_state is None
    assert frame.after_page_state is None
    assert frame.verifier_action is None
    assert path.read_bytes() == raw


def test_parse_preserves_direction_state_and_line_provenance() -> None:
    frame = parse_dom_diff_text(
        FIXTURES / "changes_present" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
    )
    operations = {record.operation for record in frame.records}
    assert {"added", "removed", "changed", "viewport_entered", "viewport_exited"} <= operations
    changed = next(record for record in frame.records if record.operation == "changed")
    assert changed.changed_field == "states"
    assert changed.before_value == [{"name": "expanded", "value": "false"}]
    assert changed.after_value == [{"name": "expanded", "value": "true"}]
    assert changed.source_spans[0].compact_ref.startswith("s1:L")
    assert changed.element_context_key.endswith("button[1]")
    repeated = next(record for record in frame.records if record.scope == "repeated_group")
    assert repeated.repeated_group_count == 2
    assert repeated.repeated_group_samples == ("visible_text=Release date 7/6/2022",)
    assert "html[1]" not in repeated.repeated_group_samples[0]
    assert frame.audit.repeated_group_sample_paths == ("html[1]/body[1]/a[1]",)


def test_document_replacement_is_explicit_navigation() -> None:
    frame = parse_dom_diff_text(
        FIXTURES / "document_replaced" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
    )
    assert frame.navigation == (
        "https://example.test/start",
        "https://example.test/result",
    )
    assert "document_replaced" in frame.coverage_warnings
    assert "document_replacement_text_only" in frame.coverage_warnings
    assert [record.text for record in frame.records if record.operation == "added"] == [
        "Published by Microsoft Studios",
        "Release date 7/6/2022",
    ]


def test_source_coverage_limits_are_model_visible_and_audited() -> None:
    frame = parse_dom_diff_text(
        FIXTURES / "changes_present" / "dom_diff1.txt",
        task_id="task",
        action_ordinal=1,
    )
    assert "live_control_state_not_covered" in frame.coverage_warnings
    assert frame.audit.headers["covers_live_control_state"] is False


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda text: text.replace("status: changes_present", "status: unknown"), "Unsupported status"),
        (lambda text: text.replace("source: runner_snapshot_diff\n", ""), "Missing required"),
        (lambda text: text + "mystery_record: {}\n", "Unsupported refined DOM record"),
        (lambda text: text.replace("change_count: 6", "change_count: 99"), "change-count arithmetic"),
        (
            lambda text: text.replace(
                '\"kind\":\"node\",\"node\"',
                '\"kind\":\"node\",\"mystery\":1,\"node\"',
                1,
            ),
            "unsupported v1 keys",
        ),
        (
            lambda text: text.replace(
                "status: changes_present", "status: viewport_content_changed"
            ),
            "invalid for status",
        ),
    ],
)
def test_parser_rejects_critical_schema_drift(tmp_path: Path, mutation, message: str) -> None:
    source = (FIXTURES / "changes_present" / "dom_diff1.txt").read_text()
    path = tmp_path / "dom_diff1.txt"
    path.write_text(mutation(source), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        parse_dom_diff_text(path, task_id="task", action_ordinal=1)


def test_numeric_discovery_and_noncanonical_names(tmp_path: Path) -> None:
    for ordinal in range(1, 11):
        (tmp_path / f"dom_diff{ordinal}.txt").write_text("x", encoding="utf-8")
    paths = discover_dom_diff_text_paths(tmp_path, 10)
    assert [path.name for path in paths] == [f"dom_diff{index}.txt" for index in range(1, 11)]
    (tmp_path / "dom_diff01.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Noncanonical"):
        discover_dom_diff_text_paths(tmp_path, 10)


def _copy_real_task(tmp_path: Path, task_name: str = "task5") -> Path:
    source = PROJECT_ROOT / "data-new-short-dom" / task_name
    target = tmp_path / task_name
    shutil.copytree(source, target)
    return target


def _task_data(path: Path) -> dict:
    value = json.loads((path / "task_data.json").read_text())
    return value[0] if isinstance(value, list) else value


def test_path_bridge_clears_every_alternative_evidence_field(tmp_path: Path) -> None:
    task = _copy_real_task(tmp_path)
    trajectory = load_dom_diff_trajectory(task)
    value = build_dom_diff_text_input(_task_data(task), trajectory)
    validate_text_input_paths(value, 1)
    action = value["dom_actions"][0]
    assert action["dom_diff_text_path"].endswith("dom_diff1.txt")
    for key in (
        "dom_diff_path",
        "dom_diff_summary_path",
        "dom_before_snapshot_path",
        "dom_after_snapshot_path",
        "dom_before_page_state_path",
        "dom_after_page_state_path",
        "dom_verifier_action_path",
    ):
        assert not action.get(key)
    assert value["screenshots_dir"] is None


@pytest.mark.parametrize(
    "relative",
    [
        "screenshot1.png",
        "dom_diff.json",
        "dom_diff_summary.json",
        "before_dom.json",
        "after_page_state.json",
        "verifier_action.json",
        "agent-browser-observation.json",
        "before_snapshot.json",
    ],
)
def test_forbidden_observation_files_are_rejected(tmp_path: Path, relative: str) -> None:
    task = _copy_real_task(tmp_path)
    (task / relative).write_bytes(b"forbidden")
    with pytest.raises(ValueError, match="forbidden"):
        reject_forbidden_evidence(task)


def test_real_dataset_preflight_all_29_frames_without_rubric() -> None:
    root = PROJECT_ROOT / "data-new-short-dom"
    frame_count = 0
    for task in sorted(root.iterdir()):
        if not task.is_dir():
            continue
        _, input_dict, frames = preflight_dom_diff_text_bundle(
            task, _task_data(task), require_frozen_rubric=False
        )
        validate_text_input_paths(input_dict, len(frames))
        frame_count += len(frames)
    assert frame_count == 29


def test_evidence_loader_reads_only_declared_text_paths(
    tmp_path: Path, monkeypatch
) -> None:
    task = _copy_real_task(tmp_path)
    trajectory = load_dom_diff_trajectory(task)
    input_dict = build_dom_diff_text_input(_task_data(task), trajectory)
    declared = {
        str(Path(action["dom_diff_text_path"]).resolve())
        for action in input_dict["dom_actions"]
    }
    opened: list[str] = []
    original_read_bytes = Path.read_bytes

    def tracked_read_bytes(path: Path):
        opened.append(str(path.resolve()))
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", tracked_read_bytes)
    frames = load_dom_diff_text_frames(input_dict["dom_actions"])
    assert len(frames) == len(declared)
    assert set(opened) == declared


def test_missing_text_file_never_falls_back_to_other_evidence(tmp_path: Path) -> None:
    task = _copy_real_task(tmp_path)
    (task / "dom_diff1.txt").unlink()
    (task / "dom_diff.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        preflight_dom_diff_text_bundle(
            task, _task_data(task), require_frozen_rubric=False
        )


def test_all_paired_semantic_trajectories_allow_only_target_representation() -> None:
    dom_root = PROJECT_ROOT / "data-new-short-dom"
    screenshot_root = PROJECT_ROOT / "data-new-screenshot"
    for task in sorted(dom_root.iterdir()):
        if task.is_dir():
            validate_cross_modality_semantic_pair(task, screenshot_root / task.name)


def test_frozen_rubric_allows_blank_placeholders_but_not_scores() -> None:
    task = {
        "precomputed_rubric": {
            "items": [
                {
                    "criterion": "One",
                    "description": "Explicit criterion",
                    "max_points": 7,
                    "earned_points": "",
                    "justification": "",
                },
                {
                    "criterion": "Two",
                    "description": "Second",
                    "max_points": 3,
                    "earned_points": "",
                    "justification": "",
                },
            ]
        }
    }
    digest, denominator = validate_frozen_rubric(task)
    assert len(digest) == 64
    assert denominator == 10
    task["precomputed_rubric"]["items"][0]["earned_points"] = 7
    with pytest.raises(ValueError, match="already scored"):
        validate_frozen_rubric(task)


def test_semantic_action_definitions_are_local_and_target_aware() -> None:
    definitions = semantic_action_definitions()
    assert {"ref", "target"} <= definitions["left_click"]
    assert {"ref", "target"} <= definitions["type"]
    assert {"ref", "target"} <= definitions["scroll"]
    assert "target" not in definitions["visit_url"]
