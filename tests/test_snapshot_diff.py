from __future__ import annotations

import json
import unittest

import dom_diff


class DomDiffProjectionTests(unittest.TestCase):
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
            self.assertEqual(dom_diff.entry_text_fragment(numeric), fragment)
            self.assertLess(dom_diff.entry_priority(numeric), dom_diff.entry_priority(plain))

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

        summary = dom_diff.bounded_dom_diff_for_model(record)
        payload = json.dumps(summary, ensure_ascii=False)

        self.assertEqual(json.loads(payload), summary)
        self.assertEqual(summary["status"], "document_replaced")
        self.assertEqual(summary["action_type"], "click")
        self.assertLessEqual(
            len(summary["model_evidence"]["entries"]),
            dom_diff.MAX_MODEL_DOM_DIFF_ENTRIES,
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

        history = dom_diff.bounded_dom_diff_history_for_review(records)

        self.assertEqual([row["step"] for row in history], [1, 2, 3])
        self.assertEqual(history[0]["after"]["url"], "https://new.example/0")
        for row in history:
            entries = row["evidence"]["model_evidence"]["entries"]
            self.assertLessEqual(
                len(entries),
                dom_diff.MAX_TERMINATION_REVIEW_DIFF_ENTRIES_PER_STEP,
            )
        self.assertIn("Step 0 evidence", json.dumps(history, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
