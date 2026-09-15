import inspect
import unittest

import runner
from prompts import SYSTEM_PROMPT


class TerminationGuardTests(unittest.TestCase):
    def test_completion_uses_the_action_decision_entrypoint(self) -> None:
        public_async_methods = sorted(
            name
            for name, value in inspect.getmembers(
                runner.ModelClient,
                predicate=inspect.iscoroutinefunction,
            )
            if not name.startswith("_")
        )

        self.assertEqual(public_async_methods, ["decide"])
        self.assertIn("Before choosing terminate", " ".join(SYSTEM_PROMPT.split()))

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


