from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RuntimeImageFilesTest(unittest.TestCase):
    def test_runtime_files(self) -> None:
        expected = {
            "image/usr/local/bin/chromium-runtime-entrypoint",
            "image/opt/chromium-runtime/serve.sh",
            "image/opt/chromium-runtime/status.py",
            "image/opt/chromium-runtime/wait.py",
            "agent-browser-runtime/package.json",
            "agent-browser-runtime/package-lock.json",
        }
        for relative in expected:
            self.assertTrue((ROOT / relative).exists(), relative)

        self.assertFalse((ROOT / "image/opt/chromium-runtime/capture_site.py").exists())
        self.assertFalse((ROOT / "image/opt/chromium-runtime/smoke_cdp.py").exists())

    def test_entrypoint_exposes_lifecycle_only(self) -> None:
        text = (ROOT / "image/usr/local/bin/chromium-runtime-entrypoint").read_text()
        for command in ["serve)", "status)", "wait)", "version)"]:
            self.assertIn(command, text)
        self.assertNotIn("capture)", text)
        self.assertNotIn("smoke)", text)

    def test_dockerfile_includes_browser_and_agent_runtime(self) -> None:
        text = (ROOT / "Dockerfile").read_text()
        self.assertIn("COPY --chown=wootz:wootz build/ /opt/wootzapp/", text)
        self.assertIn("COPY --chmod=0755 image/ /", text)
        self.assertIn("FROM node:24-bookworm-slim AS node-runtime", text)
        self.assertIn(
            "COPY agent-browser-runtime/package.json agent-browser-runtime/package-lock.json ./",
            text,
        )
        self.assertIn("npm ci --omit=dev", text)
        self.assertIn("/usr/local/bin/agent-browser", text)
        self.assertNotIn("agent-browser-core", text)
        self.assertNotIn("OPENAI_", text)
        self.assertNotIn("AI_GATEWAY_", text)
        self.assertNotIn("AGENT_BROWSER_MAX_STEPS", text)
        self.assertNotIn("chmod 0755 /opt/wootzapp/chrome", text)
        self.assertIn('ENTRYPOINT ["/usr/local/bin/chromium-runtime-entrypoint"]', text)
        self.assertIn('CMD ["serve"]', text)
        self.assertIn("HEALTHCHECK", text)

    def test_dockerignore_keeps_context_small(self) -> None:
        text = (ROOT / ".dockerignore").read_text()
        self.assertNotIn("!build/**", text)
        self.assertNotIn("!image/**", text)
        self.assertIn("tests", text)
        self.assertIn("scripts", text)

    def test_agent_browser_package_is_model_agnostic(self) -> None:
        text = (ROOT / "agent-browser-runtime/package.json").read_text()
        self.assertIn('"agent-browser": "0.27.3"', text)
        self.assertNotIn('"openai"', text)
        self.assertNotIn('"anthropic"', text)
        self.assertNotIn('"gemini"', text)

    def test_build_script_uses_only_repository_local_inputs(self) -> None:
        text = (ROOT / "scripts/build_image.sh").read_text()
        self.assertIn('AGENT_BROWSER_DIR="${IMAGE_DIR}/agent-browser-runtime"', text)
        self.assertIn('w8-core:domdiff-bench', text)
        self.assertNotIn("--build-context", text)
        self.assertNotIn("wootzapp-browser", text)

    def test_browser_payload_is_an_untracked_build_input(self) -> None:
        text = (ROOT / ".gitignore").read_text()
        self.assertIn("build/*", text)
        self.assertFalse((ROOT / "compose.yaml").exists())
        self.assertFalse((ROOT / "scripts/run_local.sh").exists())
        self.assertFalse((ROOT / "scripts/stop_local.sh").exists())


if __name__ == "__main__":
    unittest.main()
