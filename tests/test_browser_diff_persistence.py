"""Tests for browser-diff persistence adapters."""

from __future__ import annotations

import ast
import json
import tempfile
import unittest

from pathlib import Path

import runner
from recorder_support import RunnerError


ROOT = Path(__file__).resolve().parents[1]
PERSISTED_PREFIX = (
    "source",
    "interval",
    "action_type",
    "geometry_excluded",
    "covers_live_control_state",
    "identity",
    "status",
    "before",
    "after",
    "change_count",
)
PERSISTED_CASES = {
    "changes_present": (
        ROOT
        / "dataset-tasks/task11-arxiv-literature-search-20260812T122858Z"
        / "steps/step_002/dom_diff.json",
        PERSISTED_PREFIX
        + (
            "semantic_change_count",
            "viewport_change_count",
            "totals",
            "emitted_counts",
            "compression",
            "diff",
            "artifact",
        ),
    ),
    "document_replaced": (
        ROOT
        / "dataset-tasks/task1-reddit-ranking-20260812T120158Z"
        / "steps/step_004/dom_diff.json",
        PERSISTED_PREFIX + ("totals", "emitted_counts", "diff", "artifact"),
    ),
    "no_dom_change": (
        ROOT
        / "dataset-tasks/task23-scholar-literature-search-20260812T125558Z"
        / "steps/step_004/dom_diff.json",
        PERSISTED_PREFIX
        + (
            "semantic_change_count",
            "viewport_change_count",
            "totals",
            "emitted_counts",
            "compression",
            "diff",
            "artifact",
        ),
    ),
}


def local_module_path(module: str) -> Path | None:
    """Resolve only repository-local imports; ignore stdlib and dependencies."""
    module_path = ROOT.joinpath(*module.split("."))
    file_candidate = module_path.with_suffix(".py")
    if file_candidate.is_file():
        return file_candidate.resolve()
    package_candidate = module_path / "__init__.py"
    if package_candidate.is_file():
        return package_candidate.resolve()
    return None


def runner_import_graph() -> dict[Path, ast.Module]:
    """Return every local module statically reachable from runner.py imports."""
    pending = [(ROOT / "runner.py").resolve()]
    reached: dict[Path, ast.Module] = {}
    while pending:
        path = pending.pop()
        if path in reached:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        reached[path] = tree
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.append(node.module)
            for module in modules:
                local = local_module_path(module)
                if local is not None and local not in reached:
                    pending.append(local)
    return reached


def called_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Collect direct call names, including attribute calls such as Path.write_text."""
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


class BrowserDiffPersistenceTests(unittest.TestCase):
    def test_manifest_diff_engine_metadata_is_copied(self) -> None:
        manifest = {}
        engine = {
            "name": "ChromiumRL.captureSnapshotDiff",
            "browser_version": "Chrome/152.0.7948.0",
        }
        runner.apply_diff_metadata(manifest, diff_engine=engine)
        self.assertEqual(manifest["dom_diff_engine"], engine)
        self.assertIsNot(manifest["dom_diff_engine"], engine)

    def test_runner_import_graph_allows_only_live_step_diff_writer(self) -> None:
        graph = runner_import_graph()
        self.assertFalse(any(path.name == "backfill.py" for path in graph))
        filesystem_writes = {"write_json", "write_text", "write_bytes", "write_text"}
        forbidden: list[str] = []
        live_writer_callers: list[str] = []
        for path, tree in graph.items():
            module = path.relative_to(ROOT).as_posix()
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                calls = called_names(node)
                qualified = f"{module}:{node.name}"
                if node.name == "write_dom_diff_files":
                    forbidden.append(qualified)
                if "dom_diff_record" in calls and calls & filesystem_writes:
                    forbidden.append(qualified)
                if "dom_diff_text" in calls and calls & filesystem_writes:
                    if qualified != "runner.py:write_browser_dom_diff_files":
                        forbidden.append(qualified)
                if "write_browser_dom_diff_files" in calls:
                    live_writer_callers.append(qualified)
        self.assertEqual(forbidden, [])
        self.assertEqual(live_writer_callers, ["runner.py:run"])

    def test_float_respelling_uses_only_explicit_json_paths(self) -> None:
        count_fields = (
            "added",
            "removed",
            "changed",
            "semantic_changes",
            "removed_nodes",
            "added_nodes",
            "removed_text",
            "added_text",
            "semantic_entry_count",
            "structural_entry_count",
            "viewport_text_changed",
            "changes",
        )
        record = {
            "change_count": 100,
            "identity": {"matched_nodes": 100},
            "totals": {field: 100 for field in count_fields},
            "emitted_counts": {field: 0 for field in count_fields},
            "compression": {"max_collapse_document_percent": 100},
            "diff": {
                "indexes": {
                    "subtrees": [
                        {"document_percent": 0, "descendant_count": 100},
                        {"document_percent": 6.01, "descendant_count": 0},
                    ],
                    "repeated_groups": [
                        {"count": 100, "item_indices": [0, 100]},
                    ],
                },
                "viewport_delta": {
                    "geometry": {
                        "dominant_shift": {
                            "delta_x": 13212.4,
                            "delta_y": 0.6,
                            "share_of_shifted_nodes_percent": 100,
                        }
                    }
                },
            },
        }

        runner._restore_browser_diff_float_fields(record)

        self.assertEqual(record["compression"]["max_collapse_document_percent"], 100.0)
        self.assertIsInstance(record["compression"]["max_collapse_document_percent"], float)
        subtrees = record["diff"]["indexes"]["subtrees"]
        self.assertEqual(subtrees[0]["document_percent"], 0.0)
        self.assertIsInstance(subtrees[0]["document_percent"], float)
        self.assertEqual(subtrees[1]["document_percent"], 6.01)
        self.assertIsInstance(subtrees[1]["document_percent"], float)
        shift = record["diff"]["viewport_delta"]["geometry"]["dominant_shift"]
        self.assertEqual(shift["delta_x"], 13212.4)
        self.assertEqual(shift["delta_y"], 0.6)
        self.assertEqual(shift["share_of_shifted_nodes_percent"], 100.0)
        self.assertIsInstance(shift["share_of_shifted_nodes_percent"], float)

        self.assertIsInstance(record["change_count"], int)
        self.assertIsInstance(record["identity"]["matched_nodes"], int)
        self.assertIsInstance(subtrees[0]["descendant_count"], int)
        repeated = record["diff"]["indexes"]["repeated_groups"][0]
        self.assertIsInstance(repeated["count"], int)
        self.assertTrue(all(type(value) is int for value in repeated["item_indices"]))
        for counts_key in ("totals", "emitted_counts"):
            self.assertEqual(set(record[counts_key]), set(count_fields))
            self.assertTrue(all(type(value) is int for value in record[counts_key].values()))

    def test_reorder_matches_literal_stored_order_for_all_status_shapes(self) -> None:
        for status, (source_path, expected_order) in PERSISTED_CASES.items():
            with self.subTest(status=status):
                stored = json.loads(source_path.read_text(encoding="utf-8"))
                self.assertEqual(tuple(stored), expected_order)
                browser = {
                    key: value
                    for key, value in reversed(tuple(stored.items()))
                    if key != "artifact"
                }
                with tempfile.TemporaryDirectory() as raw_directory:
                    output = Path(raw_directory) / "dom_diff.json"
                    runner.write_browser_dom_diff_files(browser, output)
                    persisted = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(tuple(persisted), expected_order)

    def test_unknown_top_level_browser_key_is_rejected(self) -> None:
        browser = {
            "source": "runner_snapshot_diff",
            "future_evidence": {"must_not_be_dropped": True},
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            output = Path(raw_directory) / "dom_diff.json"
            with self.assertRaisesRegex(RunnerError, "future_evidence"):
                runner.write_browser_dom_diff_files(browser, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
