from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import capture  # noqa: E402
from recorder_support import RunnerError  # noqa: E402


class ModelDOMProtocolTests(unittest.IsolatedAsyncioTestCase):
    def test_runtime_command_is_declared_snapshot_only_and_versioned(self) -> None:
        protocol = (ROOT / "chromium_files" / "ChromiumRL.pdl").read_text(
            encoding="utf-8"
        )
        command = re.search(
            r"  command getModelDOM\n(?P<body>.*?)(?=\n  command )",
            protocol,
            re.DOTALL,
        )

        self.assertIsNotNone(command)
        self.assertEqual(
            command.group("body").split("\n\n", 1)[0].strip().splitlines(),
            [
                "parameters",
                "      StructuredPageSnapshot snapshot",
                "    returns",
                "      string modelDOM",
                "      string rendererVersion",
            ],
        )
        self.assertEqual(capture.MODEL_DOM_COMMAND, "ChromiumRL.getModelDOM")

    async def test_model_dom_uses_versioned_browser_result(self) -> None:
        cdp = MagicMock()
        cdp.call = AsyncMock(
            return_value={
                "modelDOM": "model-facing DOM\n",
                "rendererVersion": capture.MODEL_DOM_RENDERER_VERSION,
            }
        )
        snapshot = {"snapshotId": "fixture", "nodes": []}

        rendered = await capture.model_dom_from_snapshot(cdp, snapshot)

        self.assertEqual(rendered, "model-facing DOM\n")
        cdp.call.assert_awaited_once_with(
            capture.MODEL_DOM_COMMAND,
            {"snapshot": snapshot},
        )

    async def test_model_dom_rejects_unknown_renderer_version(self) -> None:
        cdp = MagicMock()
        cdp.call = AsyncMock(
            return_value={
                "modelDOM": "model-facing DOM\n",
                "rendererVersion": "unexpected-version",
            }
        )

        with self.assertRaisesRegex(
            RunnerError,
            "unexpected ChromiumRL.getModelDOM rendererVersion",
        ):
            await capture.model_dom_from_snapshot(cdp, {"nodes": []})


    async def test_model_dom_rejects_missing_text(self) -> None:
        cdp = MagicMock()
        cdp.call = AsyncMock(
            return_value={
                "rendererVersion": capture.MODEL_DOM_RENDERER_VERSION,
            }
        )

        with self.assertRaisesRegex(
            RunnerError,
            "unexpected ChromiumRL.getModelDOM response",
        ):
            await capture.model_dom_from_snapshot(cdp, {"nodes": []})

    async def test_live_materialization_has_no_python_model_fallback(self) -> None:
        cdp = MagicMock()
        snapshot = {"snapshotId": "exact-browser-result", "nodes": []}
        screenshot = {"data": ""}
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "capture"
            with (
                patch.object(
                    capture,
                    "model_dom_from_snapshot",
                    AsyncMock(return_value="browser model DOM\n"),
                ) as browser_renderer,
                patch.object(
                    capture,
                    "capture_call",
                    AsyncMock(return_value=screenshot),
                ),
                patch.object(
                    capture,
                    "page_language_state",
                    AsyncMock(return_value=capture.PageLanguageState()),
                ),
                patch.object(capture, "render_full_stored_snapshot") as full_renderer,
                patch.object(
                    capture,
                    "render_stored_snapshot",
                    side_effect=AssertionError("Python model renderer fallback used"),
                ) as legacy_renderer,
            ):
                bundle = await capture.materialize_bundle(cdp, destination, snapshot)

            browser_renderer.assert_awaited_once_with(cdp, snapshot)
            full_renderer.assert_called_once_with(destination / "dom.json")
            legacy_renderer.assert_not_called()
            self.assertEqual(bundle.snapshot, snapshot)
            self.assertEqual(bundle.model_text, "browser model DOM\n")
            self.assertEqual(
                (destination / "dom_model.txt").read_text(encoding="utf-8"),
                "browser model DOM\n",
            )


if __name__ == "__main__":
    unittest.main()
