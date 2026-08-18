import unittest

import runner


class TerminationGuardTests(unittest.TestCase):
    def test_resumed_human_intervention_allows_successful_termination(self) -> None:
        recent_actions = [
            {
                "action": {"action": "request_human"},
                "progress": {},
                "action_succeeded": False,
                "human_intervention_status": "resumed",
            }
        ]

        self.assertEqual(
            runner.action_rejection_reason(
                {"action": "terminate", "status": "success"},
                frozenset(),
                recent_actions,
            ),
            "",
        )

    def test_incomplete_human_intervention_blocks_successful_termination(self) -> None:
        for status in ("aborted", "error"):
            with self.subTest(status=status):
                recent_actions = [
                    {
                        "action": {"action": "request_human"},
                        "progress": {},
                        "action_succeeded": False,
                        "human_intervention_status": status,
                    }
                ]

                self.assertIn(
                    "at least one confirmed browser action",
                    runner.action_rejection_reason(
                        {"action": "terminate", "status": "success"},
                        frozenset(),
                        recent_actions,
                    ),
                )

    def test_guard_message_gives_an_actionable_next_step(self) -> None:
        reason = runner.action_rejection_reason(
            {"action": "terminate", "status": "success"},
            frozenset(),
            [],
        )

        self.assertIn(
            "execute one action that brings the requested evidence into the visible viewport",
            reason,
        )


