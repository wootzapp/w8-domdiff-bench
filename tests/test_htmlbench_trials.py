from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_htmlbench_trials import parse_args, resolve_start_url  # noqa: E402


class HTMLCureTrialTests(unittest.TestCase):
    def test_normal_url_is_unchanged(self) -> None:
        self.assertEqual(
            resolve_start_url({"start_url": "https://example.test/task"}),
            "https://example.test/task",
        )

    def test_fixture_url_requires_explicit_environment_value(self) -> None:
        definition = {"start_url": "${HTMLCURE_FIXTURE_URL}"}
        with patch.dict(os.environ, {"HTMLCURE_FIXTURE_URL": "http://fixture/smoke"}):
            self.assertEqual(
                resolve_start_url(definition),
                "http://fixture/smoke",
            )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "HTMLCURE_FIXTURE_URL"):
                resolve_start_url(definition)

    def test_two_repetitions_is_the_default(self) -> None:
        argv = [
            "run_htmlbench_trials.py",
            "--env-file", "example.env",
            "--output-root", "runs",
        ]
        with patch.object(sys, "argv", argv):
            self.assertEqual(parse_args().repetitions, 2)


if __name__ == "__main__":
    unittest.main()
