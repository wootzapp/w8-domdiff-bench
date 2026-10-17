import hashlib
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TASK_RECORDER_ROOT = REPOSITORY_ROOT / "w8bench" / "task_recorder"


class BrowserSourceLayoutTest(unittest.TestCase):
    def test_protocol_has_one_pinned_copy(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "chromium-patch").exists())
        protocol_path = REPOSITORY_ROOT / "protocol" / "ChromiumRL.pdl"
        self.assertEqual(
            list(REPOSITORY_ROOT.rglob("ChromiumRL.pdl")),
            [protocol_path],
        )
        self.assertEqual(
            hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
            "28ff07ce12afbed96b149b589bac4ce503734393b42efdadc2f1812caa93889b",
        )

    def test_runtime_has_one_compose_owner(self) -> None:
        compose_files = sorted(
            path
            for pattern in (
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
            )
            for path in REPOSITORY_ROOT.rglob(pattern)
        )
        self.assertEqual(compose_files, [REPOSITORY_ROOT / "docker-compose.yml"])

    def test_image_build_inputs_have_one_owner(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "chromium-image-docker").exists())
        self.assertTrue((REPOSITORY_ROOT / "Dockerfile").is_file())
        self.assertTrue((REPOSITORY_ROOT / "scripts/build-browser-image").is_file())
        self.assertTrue(
            (TASK_RECORDER_ROOT / "agent_browser/runtime/package-lock.json").is_file()
        )
        self.assertTrue(
            (TASK_RECORDER_ROOT / "runtime/chromium-runtime-entrypoint").is_file()
        )

    def test_runtime_has_only_browser_backed_text_renderers(self) -> None:
        renderer_root = TASK_RECORDER_ROOT / "renderers"
        self.assertTrue(
            (renderer_root / "render_chromiumrl_snapshot_full.py").is_file()
        )
        self.assertTrue(
            (renderer_root / "render_chromiumrl_model_dom.py").is_file()
        )
        self.assertFalse(
            (renderer_root / "render_chromiumrl_snapshot_model.py").exists()
        )


if __name__ == "__main__":
    unittest.main()
