from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import browser_runtime  # noqa: E402


class BrowserRuntimeTests(unittest.TestCase):
    def test_read_env_supports_comments_and_quoted_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text(
                "# comment\nONE=value\nTWO='quoted value'\nTHREE=\"other\"\n",
                encoding="utf-8",
            )
            values = browser_runtime.read_env(env_path)

        self.assertEqual(
            values,
            {"ONE": "value", "TWO": "quoted value", "THREE": "other"},
        )

    def test_configure_creates_isolated_identity_and_selected_ports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            with (
                patch.object(browser_runtime, "runtime_identity", return_value="abc12345"),
                patch.object(
                    browser_runtime,
                    "choose_port",
                    side_effect=[49335, 22001, 15911],
                ),
                patch.object(
                    browser_runtime,
                    "unique_container_name",
                    return_value="w8-core-browser-abc12345",
                ),
            ):
                result = browser_runtime.configure(env_path, refresh_ports=False)

            values = browser_runtime.read_env(env_path)
            mode = env_path.stat().st_mode & 0o777

        self.assertEqual(result, 0)
        self.assertEqual(values["COMPOSE_PROJECT_NAME"], "w8-recorder-abc12345")
        self.assertEqual(values["CONTAINER_NAME"], "w8-core-browser-abc12345")
        self.assertEqual(values["CDP_HOST_PORT"], "49335")
        self.assertEqual(values["NOVNC_HOST_PORT"], "22001")
        self.assertEqual(values["VNC_HOST_PORT"], "15911")
        self.assertIn("127.0.0.1:22001/vnc.html", values["RUNNER_NOVNC_URL"])
        self.assertEqual(mode, 0o600)

    def test_normal_configure_does_not_overwrite_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            original = "OPENAI_API_KEY=keep-this-value\n"
            env_path.write_text(original, encoding="utf-8")
            result = browser_runtime.configure(env_path, refresh_ports=False)
            retained = env_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertEqual(retained, original)

    def test_refresh_ports_preserves_credentials_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "IMAGE=wootzapp/w8-core:fixed",
                        "COMPOSE_PROJECT_NAME=existing-project",
                        "CONTAINER_NAME=existing-container",
                        "OPENAI_API_KEY=secret-value",
                        "OPENAI_MODEL=test-model",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with patch.object(
                browser_runtime,
                "choose_port",
                side_effect=[31001, 31002, 31003],
            ):
                result = browser_runtime.configure(env_path, refresh_ports=True)
            values = browser_runtime.read_env(env_path)

        self.assertEqual(result, 0)
        self.assertEqual(values["IMAGE"], "wootzapp/w8-core:fixed")
        self.assertEqual(values["COMPOSE_PROJECT_NAME"], "existing-project")
        self.assertEqual(values["CONTAINER_NAME"], "existing-container")
        self.assertEqual(values["OPENAI_API_KEY"], "secret-value")
        self.assertEqual(values["OPENAI_MODEL"], "test-model")
        self.assertEqual(values["CDP_HOST_PORT"], "31001")
        self.assertEqual(values["NOVNC_HOST_PORT"], "31002")
        self.assertEqual(values["VNC_HOST_PORT"], "31003")


if __name__ == "__main__":
    unittest.main()
