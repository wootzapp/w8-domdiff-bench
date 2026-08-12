from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import runner  # noqa: E402


class NavigationDiffTextTests(unittest.TestCase):
    def test_navigation_preserves_full_captured_text_rows(self) -> None:
        decisive_tail = "DECISIVE LOCATION AT THE END"
        long_text = ("general event description " * 20) + decisive_tail
        before = {
            "url": "https://example.test/old",
            "roots": ["old"],
            "nodes": [
                {
                    "ref": "old",
                    "tag": "main",
                    "directText": "Old document",
                    "childRefs": [],
                    "sourceOrder": 1,
                    "visible": True,
                }
            ],
        }
        after = {
            "url": "https://example.test/new",
            "roots": ["new"],
            "nodes": [
                {
                    "ref": "new",
                    "tag": "main",
                    "directText": long_text,
                    "childRefs": [],
                    "sourceOrder": 1,
                    "visible": True,
                }
            ],
        }

        record = runner.dom_diff_record(before, after, action_type="click")

        self.assertEqual(record["diff"]["text_delta"]["added"], [long_text])
        self.assertIn(decisive_tail, runner.dom_diff_text(record))

    def test_truncated_direct_text_uses_bounded_complete_subtree_row(self) -> None:
        full_history = (
            "Submission history [v1] Mon, 12 Jun 2017 17:57:34 UTC "
            "[v7] Wed, 2 Aug 2023 00:41:18 UTC"
        )
        rows = runner.visible_document_text(
            {
                "nodes": [
                    {
                        "ref": "history",
                        "tag": "div",
                        "directText": "Submission history [v1] Mon, 12 Jun 2017",
                        "subtreeText": full_history,
                        "truncated": True,
                        "visible": True,
                        "sourceOrder": 1,
                    }
                ]
            }
        )

        self.assertEqual(rows, [full_history])

    def test_truncated_broad_ancestor_does_not_replace_own_text(self) -> None:
        direct = "Page heading and opening sentence"
        enormous_subtree = direct + (" repeated descendant text" * 1000)
        rows = runner.visible_document_text(
            {
                "nodes": [
                    {
                        "ref": "body",
                        "tag": "body",
                        "directText": direct,
                        "subtreeText": enormous_subtree,
                        "truncated": True,
                        "visible": True,
                        "sourceOrder": 1,
                    }
                ]
            }
        )

        self.assertEqual(rows, [direct])


if __name__ == "__main__":
    unittest.main()
