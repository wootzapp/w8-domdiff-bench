from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TASK_RECORDER_ROOT = REPOSITORY_ROOT / "task-recorder"
CHROMIUMRL_PDL = (
    REPOSITORY_ROOT
    / "chromium-patch/src/third_party/blink/public/devtools_protocol/domains/ChromiumRL.pdl"
)


class BrowserSourceLayoutTest(unittest.TestCase):
    def test_chromiumrl_protocol_has_one_authoritative_source(self) -> None:
        copies = sorted(REPOSITORY_ROOT.rglob("ChromiumRL.pdl"))
        self.assertEqual(copies, [CHROMIUMRL_PDL])

        protocol = CHROMIUMRL_PDL.read_text(encoding="utf-8")
        for command in (
            "captureStructuredSnapshot",
            "compareStructuredSnapshots",
            "captureSnapshotDiff",
            "getModelDOM",
        ):
            self.assertIn(f"  command {command}\n", protocol)

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
        self.assertEqual(compose_files, [TASK_RECORDER_ROOT / "docker-compose.yml"])

    def test_image_build_inputs_do_not_duplicate_runtime_launchers(self) -> None:
        image_root = REPOSITORY_ROOT / "chromium-image-docker"
        self.assertTrue((image_root / "Dockerfile").is_file())
        self.assertTrue((image_root / "scripts/build_image.sh").is_file())
        self.assertTrue((image_root / "agent-browser-runtime/package-lock.json").is_file())
        self.assertFalse((image_root / "scripts/run_local.sh").exists())
        self.assertFalse((image_root / "scripts/stop_local.sh").exists())


if __name__ == "__main__":
    unittest.main()
