from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import runner  # noqa: E402


class ActionCoordinateTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_get_agent_observation_only_for_coordinate(self) -> None:
        cdp = AsyncMock()
        cdp.call.return_value = {
            "observation": {
                "elements": [
                    {
                        "role": "button",
                        "accessibleName": "Search",
                        "centerX": 1072.6,
                        "centerY": 50.4,
                        "text": "must not become evidence",
                    }
                ]
            }
        }

        result = await runner.chromiumrl_action_coordinate(
            cdp,
            {"ref": "e29", "role": "button", "name": "Search"},
        )

        self.assertEqual(
            result,
            {
                "status": "resolved",
                "source": "ChromiumRL.getAgentObservation",
                "match_method": "exact_role_name",
                "candidate_count": 1,
                "coordinate": [1073, 50],
            },
        )
        cdp.call.assert_awaited_once()
        method, params = cdp.call.await_args.args
        self.assertEqual(method, "ChromiumRL.getAgentObservation")
        self.assertFalse(params["includeContent"])
        self.assertFalse(params["includeDiff"])
        self.assertFalse(params["updateBaseline"])
        self.assertEqual(params["maxContentBlocks"], 0)
        self.assertEqual(params["maxDiffItems"], 0)

    async def test_ambiguous_semantic_target_is_not_guessed(self) -> None:
        cdp = AsyncMock()
        cdp.call.return_value = {
            "observation": {
                "elements": [
                    {
                        "role": "button",
                        "accessibleName": "More",
                        "centerX": 10,
                        "centerY": 10,
                    },
                    {
                        "role": "button",
                        "accessibleName": "More",
                        "centerX": 20,
                        "centerY": 20,
                    },
                ]
            }
        }

        result = await runner.chromiumrl_action_coordinate(
            cdp,
            {"ref": "e2", "role": "button", "name": "More"},
        )

        self.assertEqual(result["status"], "ambiguous")
        self.assertNotIn("coordinate", result)

    async def test_bounds_are_only_a_coordinate_fallback(self) -> None:
        cdp = AsyncMock()
        cdp.call.return_value = {
            "observation": {
                "elements": [
                    {
                        "role": "link",
                        "accessibleName": "Details",
                        "bounds": {"x": 20, "y": 30, "width": 100, "height": 40},
                    }
                ]
            }
        }

        result = await runner.chromiumrl_action_coordinate(
            cdp,
            {"ref": "e3", "role": "link", "name": "Details"},
        )

        self.assertEqual(result["coordinate"], [70, 50])

    def test_labeltext_uses_unique_hit_testable_snapshot_label_bounds(self) -> None:
        snapshot = {
            "nodes": [
                {
                    "tag": "label",
                    "role": "generic",
                    "accessibleName": "Bicycle",
                    "visible": True,
                    "hitTestable": True,
                    "bounds": {"x": 41, "y": 63, "width": 34, "height": 34},
                },
                {
                    "tag": "input",
                    "role": "radio",
                    "accessibleName": None,
                    "visible": True,
                    "hitTestable": False,
                    "bounds": {"x": 8, "y": 63, "width": 13, "height": 13},
                },
            ]
        }

        result = runner.structured_snapshot_action_coordinate(
            snapshot,
            {"ref": "e23", "role": "LabelText", "name": "Bicycle"},
        )

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(
            result["source"],
            "ChromiumRL.captureStructuredSnapshot.bounds",
        )
        self.assertEqual(result["coordinate"], [58, 80])


if __name__ == "__main__":
    unittest.main()
