from __future__ import annotations

import asyncio
import json
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
    def test_runtime_command_uses_structured_model_dom_contract(self) -> None:
        self.assertEqual(capture.MODEL_DOM_COMMAND, "ChromiumRL.getModelDOM")
        self.assertEqual(capture.MODEL_DOM_RENDERER_NAME, "chromiumrl-model-dom")

    async def test_model_dom_accepts_structured_result_and_extra_keys(self) -> None:
        cdp = MagicMock()
        model_dom = {
            "rendererName": capture.MODEL_DOM_RENDERER_NAME,
            "sections": [
                {"name": "header", "lines": ["model-facing DOM"]},
            ],
        }
        cdp.call = AsyncMock(
            return_value={
                "modelDOM": model_dom,
                "futureField": "allowed",
            }
        )
        snapshot = {"snapshotId": "fixture", "nodes": []}

        rendered = await capture.model_dom_from_snapshot(cdp, snapshot)

        self.assertIs(rendered, model_dom)
        cdp.call.assert_awaited_once_with(
            capture.MODEL_DOM_COMMAND,
            {"snapshot": snapshot},
        )

    async def test_model_dom_rejects_unknown_renderer_name(self) -> None:
        cdp = MagicMock()
        cdp.call = AsyncMock(
            return_value={
                "modelDOM": {
                    "rendererName": "unexpected-renderer",
                    "sections": [
                        {"name": "header", "lines": ["model-facing DOM"]},
                    ],
                },
            }
        )

        with self.assertRaisesRegex(
            RunnerError,
            "unexpected ChromiumRL.getModelDOM rendererName",
        ):
            await capture.model_dom_from_snapshot(cdp, {"nodes": []})

    async def test_model_dom_rejects_missing_object(self) -> None:
        cdp = MagicMock()
        cdp.call = AsyncMock(return_value={"futureField": "allowed"})

        with self.assertRaisesRegex(
            RunnerError,
            "unexpected ChromiumRL.getModelDOM response",
        ):
            await capture.model_dom_from_snapshot(cdp, {"nodes": []})

    async def test_capture_call_retries_asyncio_timeout(self) -> None:
        cdp = MagicMock()
        cdp.call = AsyncMock(
            side_effect=[
                asyncio.TimeoutError(),
                {"snapshot": {"nodes": []}},
            ]
        )

        with patch.object(capture.asyncio, "sleep", AsyncMock()) as sleep:
            result = await capture.capture_call(
                cdp,
                "ChromiumRL.captureStructuredSnapshot",
                {},
            )

        self.assertEqual(result, {"snapshot": {"nodes": []}})
        self.assertEqual(cdp.call.await_count, 2)
        sleep.assert_awaited_once_with(0.5)

    async def test_live_materialization_has_no_python_model_fallback(self) -> None:
        cdp = MagicMock()
        snapshot = {"snapshotId": "exact-browser-result", "nodes": []}
        screenshot = {"data": ""}
        model_dom = {
            "rendererName": capture.MODEL_DOM_RENDERER_NAME,
            "sections": [
                {"name": "header", "lines": ["browser model DOM"]},
            ],
        }

        def render_projection(model_dom_path: Path) -> None:
            envelope = json.loads(model_dom_path.read_text(encoding="utf-8"))
            self.assertEqual(envelope, {"result": {"modelDOM": model_dom}})
            model_dom_path.with_suffix(".txt").write_text(
                "browser model DOM\n",
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "capture"
            with (
                patch.object(
                    capture,
                    "model_dom_from_snapshot",
                    AsyncMock(return_value=model_dom),
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
                    "render_model_dom_stored_projection",
                    side_effect=render_projection,
                ) as model_projection,
                patch.object(
                    capture,
                    "render_stored_snapshot",
                    side_effect=AssertionError("legacy model renderer used"),
                ) as legacy_renderer,
            ):
                bundle = await capture.materialize_bundle(cdp, destination, snapshot)

            browser_renderer.assert_awaited_once_with(cdp, snapshot)
            full_renderer.assert_called_once_with(destination / "dom.json")
            model_projection.assert_called_once_with(destination / "dom_model.json")
            legacy_renderer.assert_not_called()
            self.assertEqual(bundle.snapshot, snapshot)
            self.assertEqual(bundle.model_text, "browser model DOM\n")


if __name__ == "__main__":
    unittest.main()
