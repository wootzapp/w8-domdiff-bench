from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from htmlbench_profiles import (  # noqa: E402
    apply_profile_environment,
    get_profile,
    init_scripts_for_profile,
    profile_manifest,
)


class HTMLBenchProfileTests(unittest.TestCase):
    def test_baseline_is_isolated_without_htmlbench_treatment(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            values = apply_profile_environment("baseline")
        self.assertEqual(values["CONTAINER_NAME"], "htmlbench-eval-baseline-browser")
        self.assertEqual(values["RUNNER_CDP_URL"], "http://127.0.0.1:49345")
        self.assertEqual(values["CHROMIUM_EXTRA_ARGS"], "--lang=en-US")
        self.assertEqual(values["CHROMIUM_RESET_PROFILE"], "1")
        self.assertEqual(values["CHROMIUM_HEADLESS"], "0")
        self.assertEqual(init_scripts_for_profile("baseline"), ())

    def test_full_profile_contains_flags_and_both_scripts(self) -> None:
        profile = get_profile("htmlbench-full")
        self.assertIn("--blink-settings=imagesEnabled=false", profile.extra_browser_args)
        self.assertIn("--use-angle=swiftshader", profile.extra_browser_args)
        self.assertEqual(
            [name for name, _source in init_scripts_for_profile("htmlbench-full")],
            ["page_safety", "interaction_helper"],
        )
        helper = dict(init_scripts_for_profile("htmlbench-full"))["interaction_helper"]
        self.assertIn("window.__probe", helper)
        self.assertIn("window.__drag", helper)
        self.assertNotIn("<script", helper)
        manifest = profile_manifest("htmlbench-full")
        self.assertTrue(manifest["same_browser_image_as_baseline"])
        self.assertEqual(
            manifest["runtime_supplied_browser_args"],
            ["--no-sandbox", "--disable-gpu"],
        )

    def test_profiles_use_different_containers_and_ports(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            baseline = apply_profile_environment("baseline")
            full = apply_profile_environment("htmlbench-full")
        self.assertNotEqual(baseline["CONTAINER_NAME"], full["CONTAINER_NAME"])
        self.assertNotEqual(baseline["CDP_HOST_PORT"], full["CDP_HOST_PORT"])


if __name__ == "__main__":
    unittest.main()
