from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TASK_RECORDER_ROOT = REPOSITORY_ROOT / "task-recorder"


class BrowserSourceLayoutTest(unittest.TestCase):
    def test_browser_source_is_not_duplicated_in_harness_repository(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "chromium-patch").exists())
        self.assertEqual(list(REPOSITORY_ROOT.rglob("ChromiumRL.pdl")), [])

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

    def test_image_build_inputs_have_one_owner(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "chromium-image-docker").exists())
        self.assertTrue((TASK_RECORDER_ROOT / "Dockerfile").is_file())
        self.assertTrue((TASK_RECORDER_ROOT / "build-browser-image").is_file())
        self.assertTrue(
            (TASK_RECORDER_ROOT / "agent_browser/runtime/package-lock.json").is_file()
        )
        self.assertTrue(
            (TASK_RECORDER_ROOT / "runtime/chromium-runtime-entrypoint").is_file()
        )


if __name__ == "__main__":
    unittest.main()
