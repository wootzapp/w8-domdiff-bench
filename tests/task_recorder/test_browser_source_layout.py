import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import pytest


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

    def test_browser_build_pin_matches_protocol_and_setup_commands(self) -> None:
        settings = json.loads((REPOSITORY_ROOT / "protocol/browser-build.json").read_text())
        self.assertRegex(settings["overlay_revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(settings["protocol_sha256"], hashlib.sha256(
            (REPOSITORY_ROOT / "protocol/ChromiumRL.pdl").read_bytes()
        ).hexdigest())
        for path in (REPOSITORY_ROOT / "README.md", REPOSITORY_ROOT / "docs/runbook.md"):
            self.assertIn("checkout --detach " + settings["overlay_revision"], path.read_text())
            self.assertIn("src@refs/tags/" + settings["chromium_version"], path.read_text())

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


@pytest.mark.parametrize("mismatch", [None, "revision", "overlay", "protocol", "binary"])
def test_image_builder_checks_provenance_before_docker(tmp_path, mismatch):
    root = tmp_path / "bench"
    overlay = tmp_path / "overlay"
    chromium = tmp_path / "chromium"
    for directory in (root / "scripts", root / "protocol", root / "build",
                      root / "w8bench/task_recorder/agent_browser/runtime", overlay / "src",
                      chromium / "chrome", chromium / "out/Release"):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPOSITORY_ROOT / "scripts/build-browser-image", root / "scripts/build-browser-image")
    protocol_path = Path("third_party/blink/public/devtools_protocol/domains/ChromiumRL.pdl")
    for directory in (overlay / "src" / protocol_path.parent, chromium / protocol_path.parent):
        directory.mkdir(parents=True)
    protocol = b"domain ChromiumRL\n"
    (overlay / "src" / protocol_path).write_bytes(protocol)
    (chromium / protocol_path).write_bytes(protocol)
    (root / "protocol/ChromiumRL.pdl").write_bytes(protocol)
    (chromium / "chrome/VERSION").write_text("MAJOR=152\nMINOR=0\nBUILD=7948\nPATCH=0\n")
    for checkout in (overlay, chromium):
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)
        subprocess.run(["git", "-C", str(checkout), "add", "."], check=True)
        subprocess.run(["git", "-C", str(checkout), "-c", "user.name=Build Test",
                        "-c", "user.email=build-test@example.test", "commit", "-qm", "Source fixture"], check=True)
    revision = subprocess.check_output(["git", "-C", str(overlay), "rev-parse", "HEAD"], text=True).strip()
    settings = {"chromium_version": "152.0.7948.0", "overlay_repository": "https://example.test/browser.git",
                "overlay_revision": revision, "protocol_sha256": hashlib.sha256(protocol).hexdigest()}
    binary = b"#!/bin/sh\nprintf 'Chrome 152.0.7948.0\\n'\n"
    for path in (root / "build/chrome", chromium / "out/Release/chrome"):
        path.write_bytes(binary)
        path.chmod(0o755)
    for name in ("package.json", "package-lock.json"):
        (root / "w8bench/task_recorder/agent_browser/runtime" / name).write_text("{}")
    if mismatch == "revision":
        settings["overlay_revision"] = "0" * 40
    elif mismatch == "overlay":
        (chromium / protocol_path).write_bytes(b"wrong overlay\n")
    elif mismatch == "protocol":
        settings["protocol_sha256"] = "0" * 64
    elif mismatch == "binary":
        (root / "build/chrome").write_bytes(binary + b"# different binary\n")
    (root / "protocol/browser-build.json").write_text(json.dumps(settings))
    tools = tmp_path / "tools"
    tools.mkdir()
    docker = tools / "docker"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$PROVENANCE_TEST_DOCKER_LOG"\n')
    docker.chmod(0o755)
    docker_log = tmp_path / "docker-arguments.txt"
    result = subprocess.run(
        ["bash", str(root / "scripts/build-browser-image"), str(chromium), str(overlay)],
        env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"],
             "IMAGE_VCS_REF": "1" * 40, "PROVENANCE_TEST_DOCKER_LOG": str(docker_log)},
        capture_output=True, text=True, cwd=root,
    )
    if mismatch:
        assert result.returncode != 0
        assert "provenance check failed" in result.stderr
        assert not docker_log.exists()
    else:
        assert result.returncode == 0, result.stderr
        receipt = json.loads((root / "build/browser-build.json").read_text())
        assert receipt["overlay_revision"] == revision
        assert receipt["chrome_sha256"] == hashlib.sha256(binary).hexdigest()
        arguments = docker_log.read_text()
        assert "BROWSER_OVERLAY_REVISION=" + revision in arguments
        assert "BROWSER_PROTOCOL_SHA256=" + settings["protocol_sha256"] in arguments


if __name__ == "__main__":
    unittest.main()
