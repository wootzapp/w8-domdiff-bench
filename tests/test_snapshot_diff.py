from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "snapshot_diff"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import runner  # noqa: E402
from render_chromiumrl_snapshot_model import ModelSnapshotRenderer  # noqa: E402


class SnapshotDiffFixtures(unittest.TestCase):
    def pair(self, name: str) -> tuple[dict, dict]:
        before = runner.load_snapshot_file(FIXTURES / f"{name}_before.json")
        after = runner.load_snapshot_file(FIXTURES / f"{name}_after.json")
        return before, after

    def line_count(self, record: dict) -> int:
        return len(json.dumps(record, ensure_ascii=False, indent=2).splitlines())

    def test_modal_toggle_is_collapsed_and_readable(self) -> None:
        record = runner.dom_diff_record(*self.pair("modal"), action_type="click")
        self.assertEqual(record["status"], "changes_present")
        self.assertIn("Confirm choice", json.dumps(record["diff"], ensure_ascii=False))
        self.assertEqual(record["totals"]["removed"], 0)
        self.assertEqual(record["totals"]["added"], 3)
        self.assertLess(self.line_count(record), 200)
        self.assertLessEqual(record["compression"]["max_collapse_document_percent"], 60)

    def test_navigation_uses_document_shape(self) -> None:
        record = runner.dom_diff_record(*self.pair("navigation"), action_type="click")
        self.assertEqual(record["status"], "document_replaced")
        self.assertEqual(record["diff"]["navigation"]["from"], "https://example.test/old")
        self.assertIn("New document", record["diff"]["text_delta"]["added"])
        self.assertLess(self.line_count(record), 500)

    def test_pure_scroll_is_explicitly_zero_semantic_change(self) -> None:
        record = runner.dom_diff_record(*self.pair("scroll"), action_type="scroll")
        self.assertEqual(record["status"], "no_semantic_change_scroll")
        self.assertEqual(record["change_count"], 0)
        self.assertTrue(record["geometry_excluded"])
        self.assertEqual(
            record["diff"]["viewport_delta"]["geometry"]["dominant_shift"]["delta_y"],
            -600.0,
        )
        self.assertFalse(
            record["diff"]["viewport_delta"]["geometry"]["per_node_geometry_emitted"]
        )

    def test_scroll_emits_compact_text_entering_and_exiting_viewport(self) -> None:
        def snapshot(*, after: bool) -> dict:
            return {
                "url": "https://example.test/job",
                "roots": ["root"],
                "nodes": [
                    {
                        "ref": "root",
                        "tag": "html",
                        "childRefs": ["old", "new"],
                        "sourceOrder": 1,
                        "visible": True,
                        "inViewport": True,
                        "hitTestable": True,
                        "bounds": {"x": 0, "y": 0, "width": 800, "height": 2000},
                    },
                    {
                        "ref": "old",
                        "parentRef": "root",
                        "tag": "p",
                        "directText": "Job number 123",
                        "childRefs": [],
                        "sourceOrder": 2,
                        "visible": True,
                        "inViewport": not after,
                        "hitTestable": not after,
                        "bounds": {"x": 20, "y": -500 if after else 300, "width": 300, "height": 30},
                    },
                    {
                        "ref": "new",
                        "parentRef": "root",
                        "tag": "p",
                        "directText": "Responsibilities include model evaluation",
                        "childRefs": [],
                        "sourceOrder": 3,
                        "visible": True,
                        "inViewport": after,
                        "hitTestable": after,
                        "bounds": {"x": 20, "y": 700 if after else 1500, "width": 500, "height": 30},
                    },
                ],
            }

        record = runner.dom_diff_record(snapshot(after=False), snapshot(after=True), action_type="scroll")
        self.assertEqual(record["status"], "viewport_content_changed")
        self.assertEqual(record["semantic_change_count"], 0)
        self.assertEqual(record["viewport_change_count"], 2)
        self.assertEqual(record["change_count"], 2)
        viewport = record["diff"]["viewport_delta"]
        self.assertEqual(
            viewport["visible_text_entered"],
            ["Responsibilities include model evaluation"],
        )
        self.assertEqual(viewport["visible_text_exited"], ["Job number 123"])
        self.assertEqual(viewport["geometry"]["dominant_shift"]["delta_y"], -800.0)
        self.assertIn(
            "visible_text_entered: \"Responsibilities include model evaluation\"",
            runner.dom_diff_text(record),
        )
        model_summary = runner.bounded_dom_diff_for_model(record)
        self.assertIn(
            "Responsibilities include model evaluation",
            json.dumps(model_summary, ensure_ascii=False),
        )
        self.assertLess(self.line_count(record), 200)

    def test_direct_text_edit_is_preserved(self) -> None:
        record = runner.dom_diff_record(*self.pair("text_edit"), action_type="fill")
        self.assertEqual(record["status"], "changes_present")
        self.assertIn("final copy", json.dumps(record["diff"], ensure_ascii=False))
        self.assertFalse(record["covers_live_control_state"])
        self.assertLess(self.line_count(record), 500)

    def test_truncation_balances_operations_and_ranks_semantic_facts(self) -> None:
        def rows(operation: str) -> list[dict]:
            result = [
                {"kind": "node", "path": f"root/{operation}/wrapper-{index}", "node": {"tag": "div"}}
                for index in range(30)
            ]
            result.append(
                {
                    "kind": "node",
                    "path": f"root/{operation}/important",
                    "node": {"tag": "button", "directText": "Save 42", "actionTypes": ["click"]},
                }
            )
            return result

        added, removed, changed, truncated, dropped = runner.truncate_diff_entries(
            rows("added"), rows("removed"), rows("changed"), max_entries=64
        )
        for emitted in (added, removed, changed):
            self.assertGreater(len(emitted), 0)
            self.assertIn("important", emitted[0]["path"])
        self.assertEqual(sum(map(len, (added, removed, changed))), 64)
        expected_dropped = 3 * 31 - 64
        self.assertEqual(sum(truncated.values()), expected_dropped)
        self.assertEqual(len(dropped), expected_dropped)
        self.assertTrue(all(item["paths"] for item in dropped))

    def test_persisted_diff_emits_all_semantic_entries(self) -> None:
        rows = [
            {
                "kind": "node",
                "path": f"root/item-{index}",
                "node": {"tag": "p", "directText": f"Evidence {index}"},
            }
            for index in range(100)
        ]
        added, removed, changed, truncated, dropped = runner.truncate_diff_entries(
            rows, [], []
        )
        self.assertEqual(len(added), 100)
        self.assertEqual((removed, changed), ([], []))
        self.assertEqual(truncated, {"added": 0, "removed": 0, "changed": 0})
        self.assertEqual(dropped, [])

    def test_numeric_fragments_rank_above_plain_text(self) -> None:
        plain = {
            "kind": "node",
            "path": "root/plain",
            "node": {"directText": "available product"},
        }
        for position, fragment in enumerate(("£19.63", "18 available", "2025-08-07")):
            numeric = {
                "kind": "node",
                "path": f"root/numeric-{position}",
                "node": {"directText": fragment},
            }
            self.assertEqual(runner.entry_text_fragment(numeric), fragment)
            self.assertLess(runner.entry_priority(numeric), runner.entry_priority(plain))

    def test_model_diff_summary_is_bounded_valid_json(self) -> None:
        record = {
            "status": "document_replaced",
            "action_type": "click",
            "totals": {"removed_text": 100, "added_text": 100},
            "emitted_counts": {"removed_text": 100, "added_text": 100},
            "diff": {
                "text_delta": {
                    "removed": [f"Old evidence {index}" for index in range(100)],
                    "added": [f"New evidence £{index}.63" for index in range(100)],
                    "truncated": {"removed": 0, "added": 0},
                }
            },
        }
        summary = runner.bounded_dom_diff_for_model(record)
        payload = json.dumps(summary, ensure_ascii=False)
        self.assertEqual(json.loads(payload), summary)
        self.assertEqual(summary["status"], "document_replaced")
        self.assertEqual(summary["action_type"], "click")
        self.assertLessEqual(
            len(summary["model_evidence"]["entries"]),
            runner.MAX_MODEL_DOM_DIFF_ENTRIES,
        )
        self.assertLess(len(payload), 30000)

    def test_termination_review_history_keeps_every_step_bounded(self) -> None:
        records = []
        for step in range(3):
            records.append(
                {
                    "status": "document_replaced",
                    "action_type": "navigate",
                    "before": {"url": f"https://old.example/{step}"},
                    "after": {"url": f"https://new.example/{step}"},
                    "diff": {
                        "text_delta": {
                            "removed": [],
                            "added": [
                                f"Step {step} evidence {item}"
                                for item in range(20)
                            ],
                        }
                    },
                }
            )

        history = runner.bounded_dom_diff_history_for_review(records)

        self.assertEqual([row["step"] for row in history], [1, 2, 3])
        self.assertEqual(history[0]["after"]["url"], "https://new.example/0")
        for row in history:
            entries = row["evidence"]["model_evidence"]["entries"]
            self.assertLessEqual(
                len(entries),
                runner.MAX_TERMINATION_REVIEW_DIFF_ENTRIES_PER_STEP,
            )
        self.assertIn("Step 0 evidence", json.dumps(history, ensure_ascii=False))

    def test_duplicate_relocation_prefers_nearest_structure(self) -> None:
        old_paths = ["root/section[1]/p[1]", "root/section[9]/p[1]"]
        new_paths = ["root/section[1]/p[2]"]
        self.assertEqual(
            runner.match_relocated_paths(old_paths, new_paths),
            [("root/section[1]/p[1]", "root/section[1]/p[2]")],
        )

    def test_broad_ancestor_does_not_anchor_on_inherited_accessible_name(self) -> None:
        broad = {
            "tag": "div",
            "role": "generic",
            "accessibleName": "Select a branch",
            "childRefs": ["e2"],
            "actionTypes": ["scroll"],
        }
        control = {
            "tag": "button",
            "role": "button",
            "accessibleName": "Select a branch",
            "childRefs": ["e3"],
            "actionTypes": ["click"],
        }
        self.assertEqual(runner.stable_node_anchor(broad), "")
        self.assertEqual(runner.stable_node_anchor(control), "select-a-branch")

    def test_backfill_defaults_to_diff_only_and_opt_in_preserves_renders(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            run_dir = Path(raw_directory)
            step_dir = run_dir / "steps" / "step_001"
            for side, fixture in (("before", "text_edit_before.json"), ("after", "text_edit_after.json")):
                side_dir = step_dir / side
                side_dir.mkdir(parents=True)
                shutil.copy2(FIXTURES / fixture, side_dir / "dom.json")
                (side_dir / "dom_full.txt").write_text(f"{side}-full-sentinel", encoding="utf-8")
                (side_dir / "dom_model.txt").write_text(f"{side}-model-sentinel", encoding="utf-8")
            (step_dir / "action.json").write_text(
                json.dumps({"step": 1, "action": {"action": "fill"}}), encoding="utf-8"
            )
            (step_dir / "dom_diff.json").write_text("{}", encoding="utf-8")
            (run_dir / "manifest.json").write_text(
                json.dumps({"steps": [{"step": 1}]}), encoding="utf-8"
            )

            report = runner.backfill_run(run_dir)
            self.assertEqual(report["rerendered_snapshots"], 0)
            self.assertEqual(
                (step_dir / "before" / "dom_model.txt").read_text(encoding="utf-8"),
                "before-model-sentinel",
            )
            self.assertEqual(report["previous_diff_state_counts"], {"empty_payload": 1})

            rerender_report = runner.backfill_run(run_dir, rerender=True)
            self.assertEqual(rerender_report["rerendered_snapshots"], 2)
            self.assertEqual(
                (step_dir / "before" / "dom_model.original.txt").read_text(encoding="utf-8"),
                "before-model-sentinel",
            )
            self.assertNotEqual(
                (step_dir / "before" / "dom_model.txt").read_text(encoding="utf-8"),
                "before-model-sentinel",
            )

    def test_previous_diff_state_distinguishes_semantic_zero(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "dom_diff.json"
            self.assertEqual(runner.previous_dom_diff_state(path), "missing")
            runner.write_json(path, {"source": runner.DOM_DIFF_SOURCE, "change_count": 0, "diff": {"added": [], "removed": [], "changed": []}})
            self.assertEqual(runner.previous_dom_diff_state(path), "semantic_zero")


class ModelRendererFixtures(unittest.TestCase):
    def test_persisted_artifact_enforces_bytes_and_reports_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dom_diff.json"
            record = runner.write_dom_diff_files(
                FIXTURES / "navigation_before.json",
                FIXTURES / "navigation_after.json",
                output,
                action_type="click",
            )
            self.assertEqual(record["artifact"]["max_json_bytes"], 500 * 1024)
            self.assertEqual(record["artifact"]["json_bytes"], output.stat().st_size)
            self.assertGreater(record["artifact"]["json_lines"], 0)
            self.assertFalse(record["artifact"]["over_size_limit"])

    def render(self, snapshot: dict) -> str:
        return ModelSnapshotRenderer(
            snapshot,
            max_actions=20,
            max_secondary_actions=20,
            max_nested_actions=8,
            max_content_blocks=20,
            max_table_rows=20,
            max_media=20,
            max_scroll_regions=8,
            max_cell_chars=180,
            max_text_chars=700,
            include_refs=False,
            include_secondary=True,
            include_offscreen_content=True,
        ).render()

    def test_richer_subtree_replaces_truncated_direct_text(self) -> None:
        snapshot = {
            "url": "https://example.test/",
            "title": "Fixture",
            "nodes": [
                {
                    "ref": "e1",
                    "tag": "p",
                    "directText": "The event will be",
                    "subtreeText": "The event will be held in the East Gallery.",
                    "truncated": True,
                    "sourceOrder": 1,
                }
            ],
        }
        self.assertIn("East Gallery", self.render(snapshot))

    def test_truncated_ancestor_does_not_suppress_descendant_fact(self) -> None:
        snapshot = {
            "url": "https://example.test/",
            "title": "Fixture",
            "nodes": [
                {
                    "ref": "e1",
                    "tag": "div",
                    "directText": "Introduction",
                    "subtreeText": "Introduction Detailed explanation of the command.",
                    "truncated": True,
                    "childRefs": ["e2"],
                    "sourceOrder": 1,
                },
                {
                    "ref": "e2",
                    "parentRef": "e1",
                    "tag": "p",
                    "directText": "Detailed explanation of the command.",
                    "sourceOrder": 2,
                },
            ],
        }
        self.assertIn("Detailed explanation of the command", self.render(snapshot))

if __name__ == "__main__":
    unittest.main()
