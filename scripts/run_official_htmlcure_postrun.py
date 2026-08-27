#!/usr/bin/env python3
"""Run the pinned official HTMLCure verifier pieces after a recorded task."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urldefrag


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HTMLCURE_ROOT = ROOT / ".runtime" / "HTMLCure"
EXPECTED_COMMIT = "18d68e8f1e5c2bcef7f3c00bcab3147e2a99d4db"

OFFICIAL_FILES = (
    "htmleval/concurrency/browser_pool.py",
    "htmleval/core/page_safety.py",
    "htmleval/core/screenshot.py",
    "htmleval/phases/extract.py",
    "htmleval/phases/static_analysis/analyzer.py",
    "htmleval/phases/render_test/renderer.py",
    "htmleval/phases/render_test/probes.py",
    "htmleval/phases/render_test/structural_probe.py",
    "htmleval/phases/render_test/js_snapshot.py",
    "htmleval/phases/render_test/evidence.py",
    "htmleval/phases/render_test/frame_types.py",
    "htmleval/phases/render_test/keyframe_selector.py",
    "htmleval/phases/render_test/census.py",
    "htmleval/phases/test_runner/schema.py",
    "htmleval/phases/test_runner/actions.py",
    "htmleval/phases/test_runner/executor.py",
)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def source_identity(source_root: Path) -> dict:
    commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    if commit != EXPECTED_COMMIT:
        raise RuntimeError(
            f"official HTMLCure checkout is {commit}, expected {EXPECTED_COMMIT}"
        )
    status = subprocess.run(
        ["git", "-C", str(source_root), "status", "--porcelain"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("official HTMLCure checkout has local modifications")
    hashes = {}
    for relative in OFFICIAL_FILES:
        path = source_root / relative
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"commit": commit, "clean": True, "sha256": hashes}


def recorded_final_url(run_dir: Path, manifest: dict) -> str:
    candidates = []
    steps = manifest.get("steps")
    if isinstance(steps, list):
        for step in reversed(steps):
            if not isinstance(step, dict):
                continue
            try:
                number = int(step["step"])
            except (KeyError, TypeError, ValueError):
                continue
            candidates.append(run_dir / "steps" / f"step_{number:03d}" / "after" / "dom.json")
    candidates.append(run_dir / "initial" / "dom.json")
    for path in candidates:
        if not path.exists():
            continue
        value = read_json(path)
        snapshot = value.get("result", {}).get("snapshot", {})
        url = snapshot.get("url") if isinstance(snapshot, dict) else None
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
    raise RuntimeError("recorded run has no final HTTP(S) URL")


def normalized_url(url: str) -> str:
    return urldefrag(url.strip())[0].rstrip("/")


async def select_recorded_page(browser, expected_url: str):
    pages = [
        page
        for context in browser.contexts
        for page in context.pages
        if not page.is_closed()
    ]
    exact = [page for page in pages if normalized_url(page.url) == normalized_url(expected_url)]
    if len(exact) == 1:
        return exact[0], {
            "method": "exact_recorded_url",
            "candidate_count": len(pages),
            "url": exact[0].url,
        }
    if len(pages) == 1:
        return pages[0], {
            "method": "only_open_page",
            "candidate_count": 1,
            "url": pages[0].url,
            "recorded_url": expected_url,
        }
    raise RuntimeError(
        f"cannot select recorded page: {len(pages)} open pages and "
        f"{len(exact)} exact URL matches"
    )


def helper_javascript(helper_html: str) -> str:
    open_end = helper_html.find(">")
    close_start = helper_html.rfind("</script>")
    if (
        not helper_html.lstrip().startswith('<script data-eval-helper="interaction">')
        or open_end < 0
        or close_start <= open_end
    ):
        raise RuntimeError("official interaction helper has an unexpected form")
    official_javascript = helper_html[open_end + 1 : close_start].strip()
    return (
        "(() => {\n"
        "  const installOfficialHTMLCureHelper = () => {\n"
        "    if (window.__probe && window.__probe.snapshot) return;\n"
        f"{official_javascript}\n"
        "  };\n"
        "  if (document.readyState === 'loading') {\n"
        "    document.addEventListener("
        "'DOMContentLoaded', installOfficialHTMLCureHelper, {once: true});\n"
        "  } else {\n"
        "    installOfficialHTMLCureHelper();\n"
        "  }\n"
        "})();"
    )


def generic_page_health_cases() -> list[dict]:
    """Cases exercise official actions but do not claim task completion."""
    return [
        {
            "id": "page_loaded",
            "name": "Page loaded and produced a non-blank frame",
            "steps": [
                {"action": "wait_for", "selector": "body"},
                {"action": "assert_visible", "selector": "body"},
                {"action": "assert_count", "selector": "html", "eq": 1},
                {"action": "assert_screenshot_not_blank"},
            ],
        },
        {
            "id": "document_health",
            "name": "Generic document and accessibility checks",
            "steps": [
                {
                    "action": "assert_js_value",
                    "expression": (
                        "() => document.readyState === 'complete' || "
                        "document.readyState === 'interactive'"
                    ),
                    "expected": True,
                },
                {"action": "assert_no_horizontal_scroll"},
                {"action": "assert_a11y_basic"},
            ],
        },
        {
            "id": "scroll_change",
            "name": "Scrolling produces measurable visual evidence",
            "steps": [
                {"action": "screenshot", "label": "before_scroll"},
                {"action": "scroll", "direction": "down", "amount": 300},
                {"action": "wait", "ms": 250},
                {"action": "assert_screenshot_changed", "threshold": 0.99},
            ],
        },
        {
            "id": "responsive_health",
            "name": "Mobile viewport remains usable",
            "steps": [
                {"action": "resize", "width": 375, "height": 667},
                {"action": "assert_visible", "selector": "body"},
                {"action": "assert_no_horizontal_scroll"},
                {"action": "resize", "width": 1280, "height": 720},
            ],
        },
    ]


async def run(args: argparse.Namespace) -> dict:
    run_dir = args.run_dir.resolve()
    source_root = args.htmlcure_root.resolve()
    identity = source_identity(source_root)
    manifest = read_json(run_dir / "manifest.json")
    expected_url = recorded_final_url(run_dir, manifest)
    output_dir = run_dir / "htmlcure_official"
    render_dir = output_dir / "render_test"
    test_dir = output_dir / "test_runner"
    render_dir.mkdir(parents=True, exist_ok=False)
    test_dir.mkdir(parents=True, exist_ok=False)

    sys.path.insert(0, str(source_root))
    import htmleval
    from htmleval.core.config import EvalConfig
    from htmleval.core.page_safety import install_page_safety
    from htmleval.core.screenshot import _capture_via_cdp
    from htmleval.phases.extract import _INTERACTION_HELPER
    from htmleval.phases.render_test.renderer import RenderTestPhase
    from htmleval.phases.static_analysis.analyzer import analyse_html
    from htmleval.phases.test_runner.executor import execute_test_case
    from htmleval.phases.test_runner.schema import parse_test_cases
    from playwright.async_api import async_playwright

    started = time.monotonic()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(args.cdp_url)
        page, page_selection = await select_recorded_page(browser, expected_url)
        await install_page_safety(page)
        helper_before_install = await page.evaluate(
            "() => Boolean(window.__probe && window.__probe.snapshot)"
        )
        await page.add_init_script(helper_javascript(_INTERACTION_HELPER))

        await page.goto(
            expected_url,
            wait_until="domcontentloaded",
            timeout=15_000,
        )
        current_html = await page.content()
        static_data = analyse_html(current_html)
        render_data = {
            "rendered": False,
            "page_title": "",
            "console_errors": [],
            "page_errors": [],
            "resource_error": False,
        }
        screenshots: list[str] = []
        phase = RenderTestPhase(EvalConfig())
        await phase._drive_page(
            page,
            expected_url,
            render_dir,
            render_data,
            screenshots,
            static_data,
        )
        helper_after_render = await page.evaluate(
            "() => Boolean(window.__probe && window.__probe.snapshot)"
        )
        cdp_capture_path = output_dir / "direct_cdp_capture.png"
        cdp_capture = await _capture_via_cdp(
            page,
            path=cdp_capture_path,
            timeout_ms=5_000,
            disable_animations=False,
            capture_beyond_viewport=False,
        )

        cases = parse_test_cases(generic_page_health_cases())
        results = []
        for case in cases:
            case_dir = test_dir / case.id
            case_dir.mkdir(parents=True, exist_ok=False)
            result, page = await execute_test_case(
                page,
                case,
                case_dir,
                game_url=None,
                retry_on_page_failure=False,
            )
            results.append(result)
        probe_available = await asyncio.wait_for(
            page.evaluate(
                "() => Boolean(window.__probe && window.__probe.snapshot)"
            ),
            timeout=3,
        )
        browser_version = browser.version

    screenshot_paths = [Path(path) for path in screenshots if Path(path).exists()]
    test_payload = {
        "scope": "generic page health and interaction; not task completion",
        "execution_adapter": (
            "official execute_test_case on the loaded live page; "
            "no between-case local-game reload"
        ),
        "results": [asdict(result) for result in results],
        "tests_total": len(results),
        "tests_passed": sum(1 for result in results if result.passed),
    }
    write_json(output_dir / "static_analysis.json", static_data)
    write_json(output_dir / "render_test.json", render_data)
    write_json(output_dir / "test_runner.json", test_payload)

    summary = {
        "official_source": identity,
        "playwright_version": importlib.metadata.version("playwright"),
        "htmlcure_version": htmleval.__version__,
        "wootz_browser_version": browser_version,
        "recorded_url": expected_url,
        "page_selection": page_selection,
        "official_helper_present_before_postrun_install": helper_before_install,
        "official_helper_available_after_render": helper_after_render,
        "official_helper_available_after_tests": probe_available,
        "playwright_font_wait_disabled": True,
        "direct_cdp_capture_bytes": len(cdp_capture),
        "duration_seconds": round(time.monotonic() - started, 3),
        "static_analysis_input": "page.content() after loading the recorded final URL",
        "static_html_chars": len(current_html),
        "render_data_bytes": (output_dir / "render_test.json").stat().st_size,
        "official_visible_text_chars": len(str(render_data.get("visible_text") or "")),
        "total_frames_captured": render_data.get("total_frames_captured", 0),
        "keyframes_selected": render_data.get("keyframes_selected", 0),
        "keyframe_png_bytes": sum(path.stat().st_size for path in screenshot_paths),
        "probe_errors": render_data.get("probe_errors", []),
        "generic_tests_total": test_payload["tests_total"],
        "generic_tests_passed": test_payload["tests_passed"],
        "feature_scope": {
            "applied": [
                "official static analysis",
                "official page-safety init script",
                "official interaction helper",
                "official RenderTest probe registry",
                "official Playwright screenshot and CDP fallback",
                "official SSIM frame differences",
                "official evidence aggregation and keyframe selection",
                "official generic test-runner actions",
            ],
            "not_task_scored": [
                "released frozen cases target different HTMLBench prompts",
                "AgentTest is another model-driven task agent",
                "VisionEval is a model-driven visual-design scorer",
            ],
        },
    }
    write_json(output_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--htmlcure-root",
        type=Path,
        default=DEFAULT_HTMLCURE_ROOT,
    )
    return parser.parse_args()


def main() -> int:
    summary = asyncio.run(run(parse_args()))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
