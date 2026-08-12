from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import runner  # noqa: E402


class FragmentNavigationDiffTests(unittest.TestCase):
    def snapshot(self, url: str, *, target_in_viewport: bool) -> dict:
        return {
            "url": url,
            "roots": ["root"],
            "nodes": [
                {
                    "ref": "root",
                    "tag": "html",
                    "childRefs": ["intro", "target"],
                    "sourceOrder": 1,
                    "visible": True,
                    "inViewport": True,
                    "hitTestable": True,
                    "bounds": {"x": 0, "y": 0, "width": 800, "height": 2000},
                },
                {
                    "ref": "intro",
                    "parentRef": "root",
                    "tag": "p",
                    "directText": "Introduction",
                    "childRefs": [],
                    "sourceOrder": 2,
                    "visible": True,
                    "inViewport": not target_in_viewport,
                    "hitTestable": not target_in_viewport,
                    "bounds": {"x": 20, "y": -600 if target_in_viewport else 100, "width": 400, "height": 30},
                },
                {
                    "ref": "target",
                    "parentRef": "root",
                    "tag": "p",
                    "directText": "Target section exact evidence",
                    "childRefs": [],
                    "sourceOrder": 3,
                    "visible": True,
                    "inViewport": target_in_viewport,
                    "hitTestable": target_in_viewport,
                    "bounds": {"x": 20, "y": 100 if target_in_viewport else 800, "width": 400, "height": 30},
                },
            ],
        }

    def test_fragment_only_url_change_uses_viewport_diff(self) -> None:
        before = self.snapshot("https://example.test/docs", target_in_viewport=False)
        after = self.snapshot("https://example.test/docs#target", target_in_viewport=True)

        record = runner.dom_diff_record(before, after, action_type="click")

        self.assertNotEqual(record["status"], "document_replaced")
        self.assertEqual(record["status"], "viewport_content_changed")
        self.assertIn(
            "Target section exact evidence",
            record["diff"]["viewport_delta"]["visible_text_entered"],
        )

    def test_query_change_remains_document_replacement(self) -> None:
        before = self.snapshot("https://example.test/docs?q=old", target_in_viewport=False)
        after = self.snapshot("https://example.test/docs?q=new", target_in_viewport=True)

        record = runner.dom_diff_record(before, after, action_type="click")

        self.assertEqual(record["status"], "document_replaced")


if __name__ == "__main__":
    unittest.main()
