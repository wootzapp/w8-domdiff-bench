from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChromiumRLProtocolTests(unittest.TestCase):
    def test_every_runner_chromiumrl_call_is_declared_in_pdl(self) -> None:
        protocol = (ROOT / "chromium_files" / "ChromiumRL.pdl").read_text(encoding="utf-8")
        declared = set(re.findall(r"^  command\s+(\w+)\s*$", protocol, re.MULTILINE))
        runner_source = (ROOT / "runner.py").read_text(encoding="utf-8")
        called = set(re.findall(r'["\']ChromiumRL\.(\w+)["\']', runner_source))

        self.assertTrue(called)
        self.assertEqual(called - declared, set())
        self.assertIn("captureStructuredSnapshot", called)

    def test_structured_snapshot_schema_keeps_required_identity_and_geometry(self) -> None:
        protocol = (ROOT / "chromium_files" / "ChromiumRL.pdl").read_text(encoding="utf-8")
        self.assertIn("command captureStructuredSnapshot", protocol)
        for field in (
            "string ref",
            "optional DOM.NodeId nodeId",
            "optional integer backendNodeId",
            "optional DOM.Rect bounds",
            "optional string accessibleName",
            "array of string actionTypes",
        ):
            self.assertIn(field, protocol)

    def test_coordinate_protocols_are_declared_without_becoming_dom_diff_fields(self) -> None:
        protocol = (ROOT / "chromium_files" / "ChromiumRL.pdl").read_text(encoding="utf-8")
        self.assertIn("command getTouchTraces", protocol)
        self.assertIn("command getAgentObservation", protocol)
        self.assertIn("optional number centerX", protocol)
        self.assertIn("optional number centerY", protocol)
        self.assertIn("number x", protocol)
        self.assertIn("number y", protocol)


if __name__ == "__main__":
    unittest.main()
