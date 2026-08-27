"""Controlled profiles loaded from the pinned official HTMLCure checkout."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HTMLCURE_COMMIT = "18d68e8f1e5c2bcef7f3c00bcab3147e2a99d4db"
ROOT = Path(__file__).resolve().parent
DEFAULT_HTMLCURE_ROOT = ROOT / ".runtime" / "HTMLCure"


def official_htmlcure_root() -> Path:
    """Return the local checkout selected for exact official feature loading."""
    return Path(
        os.environ.get("HTMLCURE_OFFICIAL_ROOT", str(DEFAULT_HTMLCURE_ROOT))
    ).resolve()


def _official_constants() -> tuple[tuple[str, ...], int, int, str, str]:
    """Import browser settings and scripts from the pinned official source."""
    source_root = official_htmlcure_root()
    if not (source_root / "htmleval").is_dir():
        raise RuntimeError(
            f"official HTMLCure checkout is missing at {source_root}"
        )
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    from htmleval.concurrency.browser_pool import (  # type: ignore[import-not-found]
        VIEWPORT_H,
        VIEWPORT_W,
        _BROWSER_ARGS,
    )
    from htmleval.core.page_safety import (  # type: ignore[import-not-found]
        PAGE_SAFETY_INIT_SCRIPT,
    )
    from htmleval.phases.extract import (  # type: ignore[import-not-found]
        _INTERACTION_HELPER,
    )

    return (
        tuple(_BROWSER_ARGS),
        VIEWPORT_W,
        VIEWPORT_H,
        PAGE_SAFETY_INIT_SCRIPT,
        _INTERACTION_HELPER,
    )


def _interaction_helper_javascript(helper_html: str) -> str:
    """Run the unchanged body-end helper when a live page's DOM is ready."""
    open_end = helper_html.find(">")
    close_start = helper_html.rfind("</script>")
    if (
        not helper_html.lstrip().startswith('<script data-eval-helper="interaction">')
        or open_end < 0
        or close_start <= open_end
    ):
        raise RuntimeError("official HTMLCure interaction helper has an unexpected form")
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


def official_browser_settings() -> tuple[tuple[str, ...], int, int]:
    """Expose the exact official arguments and default viewport."""
    args, width, height, _, _ = _official_constants()
    return args, width, height


@dataclass(frozen=True)
class HTMLBenchProfile:
    name: str
    description: str
    port_offset: int
    extra_browser_args: tuple[str, ...] = ("--lang=en-US",)
    page_safety: bool = False
    interaction_helper: bool = False
    headless: bool = False
    screen: str = "1365x768x24"
    window_width: int = 1366
    window_height: int = 900

    @property
    def init_script_names(self) -> tuple[str, ...]:
        names: list[str] = []
        if self.page_safety:
            names.append("page_safety")
        if self.interaction_helper:
            names.append("interaction_helper")
        return tuple(names)


_PROFILES = {
    "baseline": HTMLBenchProfile(
        "baseline",
        "Current recorder runtime with no HTMLBench-derived changes.",
        0,
    ),
    "images-disabled": HTMLBenchProfile(
        "images-disabled",
        "Baseline plus only Blink image loading/rendering disablement.",
        1,
        ("--lang=en-US", "--blink-settings=imagesEnabled=false"),
    ),
    "htmlbench-flags": HTMLBenchProfile(
        "htmlbench-flags",
        "HTMLBench launch flags, preserving the recorder's headed viewport.",
        2,
        ("--lang=en-US", *_official_constants()[0][2:]),
    ),
    "htmlbench-scripts": HTMLBenchProfile(
        "htmlbench-scripts",
        "HTMLBench audio/media shim and automatic canvas focus only.",
        3,
        page_safety=True,
        interaction_helper=True,
    ),
    "htmlbench-full": HTMLBenchProfile(
        "htmlbench-full",
        "Combined HTMLBench flags, audio/media shim, and canvas focus.",
        4,
        ("--lang=en-US", *_official_constants()[0][2:]),
        page_safety=True,
        interaction_helper=True,
    ),
    "htmlcure-helper": HTMLBenchProfile(
        "htmlcure-helper",
        "Exact official interaction helper only, with the current headed runtime.",
        5,
        interaction_helper=True,
    ),
    "htmlcure-headed": HTMLBenchProfile(
        "htmlcure-headed",
        "Exact official flags and scripts, with the current headed screen.",
        6,
        ("--lang=en-US", *_official_constants()[0][2:]),
        page_safety=True,
        interaction_helper=True,
    ),
    "htmlcure-runtime": HTMLBenchProfile(
        "htmlcure-runtime",
        "Official flags and scripts with Wootz headless 1280x720 runtime settings.",
        7,
        ("--lang=en-US", *_official_constants()[0][2:]),
        page_safety=True,
        interaction_helper=True,
        headless=True,
        screen=f"{_official_constants()[1]}x{_official_constants()[2]}x24",
        window_width=_official_constants()[1],
        window_height=_official_constants()[2],
    ),
}


def profile_names() -> tuple[str, ...]:
    """Return stable CLI choices, baseline first and full treatment last."""
    return tuple(_PROFILES)


def get_profile(name: str) -> HTMLBenchProfile:
    """Resolve a declared experiment profile or fail with a useful message."""
    try:
        return _PROFILES[name]
    except KeyError as error:
        choices = ", ".join(profile_names())
        raise ValueError(
            f"unknown HTMLBench profile {name!r}; choose one of: {choices}"
        ) from error


def init_scripts_for_profile(name: str) -> tuple[tuple[str, str], ...]:
    """Return page initialization scripts in deterministic installation order."""
    profile = get_profile(name)
    scripts: list[tuple[str, str]] = []
    _, _, _, page_safety_script, interaction_helper = _official_constants()
    if profile.page_safety:
        scripts.append(("page_safety", page_safety_script))
    if profile.interaction_helper:
        scripts.append(
            (
                "interaction_helper",
                _interaction_helper_javascript(interaction_helper),
            )
        )
    return tuple(scripts)


def apply_profile_environment(name: str) -> dict[str, str]:
    """Apply isolated Compose/browser settings after the user's base env loads."""
    profile = get_profile(name)
    cdp_port = 49345 + profile.port_offset
    novnc_port = 16192 + profile.port_offset
    vnc_port = 15912 + profile.port_offset
    slug = profile.name.replace("_", "-")
    values = {
        "HTMLBENCH_EVAL_PROFILE": profile.name,
        "COMPOSE_PROJECT_NAME": f"htmlbench-eval-{slug}",
        "CONTAINER_NAME": f"htmlbench-eval-{slug}-browser",
        "CDP_HOST_PORT": str(cdp_port),
        "NOVNC_HOST_PORT": str(novnc_port),
        "VNC_HOST_PORT": str(vnc_port),
        "RUNNER_CDP_URL": f"http://127.0.0.1:{cdp_port}",
        "RUNNER_NOVNC_URL": (
            f"http://127.0.0.1:{novnc_port}/vnc.html"
            "?resize=scale&autoconnect=1&path=websockify"
        ),
        "CHROMIUM_EXTRA_ARGS": " ".join(profile.extra_browser_args),
        "CHROMIUM_HEADLESS": "1" if profile.headless else "0",
        "VNC_SCREEN": profile.screen,
        "CHROMIUM_WINDOW_WIDTH": str(profile.window_width),
        "CHROMIUM_WINDOW_HEIGHT": str(profile.window_height),
        "CHROMIUM_RESET_PROFILE": "1",
    }
    os.environ.update(values)
    return values


def profile_manifest(name: str) -> dict[str, Any]:
    """Describe the treatment and explicitly non-applicable HTMLCure features."""
    profile = get_profile(name)
    return {
        "profile": profile.name,
        "description": profile.description,
        "htmlcure_commit": HTMLCURE_COMMIT,
        "browser_extra_args": list(profile.extra_browser_args),
        "runtime_supplied_browser_args": ["--no-sandbox", "--disable-gpu"],
        "page_init_scripts": list(profile.init_script_names),
        "fresh_profile_per_run": True,
        "same_browser_image_as_baseline": True,
        "official_source_root": str(official_htmlcure_root()),
        "runtime_environment": {
            key: os.environ.get(key)
            for key in (
                "COMPOSE_PROJECT_NAME", "CONTAINER_NAME", "CDP_HOST_PORT",
                "NOVNC_HOST_PORT", "VNC_HOST_PORT", "CHROMIUM_HEADLESS",
                "CHROMIUM_RESET_PROFILE", "CHROMIUM_WINDOW_WIDTH",
                "CHROMIUM_WINDOW_HEIGHT",
            )
        },
        "preserved_recorder_conditions": {
            "headed": not profile.headless,
            "screen": profile.screen.rsplit("x", 1)[0],
            "window_size": f"{profile.window_width}x{profile.window_height}",
            "capture": "ChromiumRL plus direct CDP screenshot",
        },
        "not_applied": {
            "playwright_font_wait_override": (
                "recorder does not use Playwright screenshots"
            ),
            "playwright_browser_pool": (
                "recorder manages a persistent Wootz Chromium service"
            ),
            "html_rewrite": (
                "live sites receive CDP init scripts; source HTML is not rewritten"
            ),
            "frozen_htmlbench_cases": (
                "released cases target generated HTMLBench pages, not these live tasks"
            ),
        },
    }
