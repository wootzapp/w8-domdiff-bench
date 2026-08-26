"""Controlled HTMLBench-derived runtime profiles for recorder experiments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


HTMLCURE_COMMIT = "18d68e8f1e5c2bcef7f3c00bcab3147e2a99d4db"

# The runtime already supplies --no-sandbox and --disable-gpu.
HTMLBENCH_EXTRA_BROWSER_ARGS = (
    "--disable-dev-shm-usage",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
    "--use-angle=swiftshader",
    "--autoplay-policy=no-user-gesture-required",
    "--use-fake-ui-for-media-stream",
    "--blink-settings=imagesEnabled=false",
)

PAGE_SAFETY_SCRIPT = r"""
(() => {
  if (window.__htmlbenchEvalPageSafetyInstalled) return;
  Object.defineProperty(window, '__htmlbenchEvalPageSafetyInstalled', {
    configurable: false, enumerable: false, value: true,
  });
  const noop = () => {};
  const makeParam = (value) => ({
    value,
    setValueAtTime: noop,
    linearRampToValueAtTime: noop,
    exponentialRampToValueAtTime: noop,
    cancelScheduledValues: noop,
  });
  const makeNode = () => ({
    connect() { return this; },
    disconnect: noop, start: noop, stop: noop,
    addEventListener: noop, removeEventListener: noop,
    gain: makeParam(1), frequency: makeParam(440), detune: makeParam(0),
    Q: makeParam(1), playbackRate: makeParam(1), buffer: null, loop: false,
  });
  class SilentAudioContext {
    constructor() {
      this.state = 'running';
      this.currentTime = 0;
      this.sampleRate = 44100;
      this.destination = makeNode();
    }
    createOscillator() { return makeNode(); }
    createGain() { return makeNode(); }
    createBufferSource() { return makeNode(); }
    createBiquadFilter() { return makeNode(); }
    createAnalyser() { return makeNode(); }
    createStereoPanner() { return makeNode(); }
    createDynamicsCompressor() { return makeNode(); }
    createDelay() { return makeNode(); }
    createConvolver() { return makeNode(); }
    createPeriodicWave() { return {}; }
    createWaveShaper() { return makeNode(); }
    createScriptProcessor() { return makeNode(); }
    createBuffer(channels, length, sampleRate) {
      return {
        numberOfChannels: channels, length, sampleRate,
        getChannelData() { return new Float32Array(length); },
      };
    }
    resume() { this.state = 'running'; return Promise.resolve(); }
    suspend() { this.state = 'suspended'; return Promise.resolve(); }
    close() { this.state = 'closed'; return Promise.resolve(); }
  }
  try {
    Object.defineProperty(window, 'AudioContext', {
      configurable: true, writable: true, value: SilentAudioContext,
    });
    Object.defineProperty(window, 'webkitAudioContext', {
      configurable: true, writable: true, value: SilentAudioContext,
    });
  } catch (_) {}
  try {
    if (window.HTMLMediaElement && window.HTMLMediaElement.prototype) {
      window.HTMLMediaElement.prototype.play = function play() {
        return Promise.resolve();
      };
    }
  } catch (_) {}
})();
""".strip()

CANVAS_FOCUS_SCRIPT = r"""
(() => {
  if (window.__htmlbenchEvalCanvasFocusInstalled) return;
  Object.defineProperty(window, '__htmlbenchEvalCanvasFocusInstalled', {
    configurable: false, enumerable: false, value: true,
  });
  const setupCanvas = () => {
    document.querySelectorAll('canvas').forEach((canvas) => {
      if (!canvas.hasAttribute('tabindex')) canvas.setAttribute('tabindex', '0');
      canvas.style.outline = 'none';
    });
  };
  const focusFirstCanvas = () => {
    setupCanvas();
    const canvas = document.querySelector('canvas');
    if (canvas && document.activeElement !== canvas) canvas.focus();
  };
  document.addEventListener('click', (event) => {
    setupCanvas();
    const clicked = event.target && event.target.closest
      ? event.target.closest('canvas') : null;
    const canvas = clicked || document.querySelector('canvas');
    if (canvas && document.activeElement !== canvas) canvas.focus();
  }, true);
  const begin = () => {
    setupCanvas();
    setTimeout(focusFirstCanvas, 500);
    const root = document.documentElement || document.body;
    if (root && window.MutationObserver) {
      new MutationObserver(setupCanvas).observe(root, {childList: true, subtree: true});
    }
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', begin, {once: true});
  } else {
    begin();
  }
})();
""".strip()


@dataclass(frozen=True)
class HTMLBenchProfile:
    name: str
    description: str
    port_offset: int
    extra_browser_args: tuple[str, ...] = ("--lang=en-US",)
    page_safety: bool = False
    canvas_focus: bool = False

    @property
    def init_script_names(self) -> tuple[str, ...]:
        names: list[str] = []
        if self.page_safety:
            names.append("page_safety")
        if self.canvas_focus:
            names.append("canvas_focus")
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
        ("--lang=en-US", *HTMLBENCH_EXTRA_BROWSER_ARGS),
    ),
    "htmlbench-scripts": HTMLBenchProfile(
        "htmlbench-scripts",
        "HTMLBench audio/media shim and automatic canvas focus only.",
        3,
        page_safety=True,
        canvas_focus=True,
    ),
    "htmlbench-full": HTMLBenchProfile(
        "htmlbench-full",
        "Combined HTMLBench flags, audio/media shim, and canvas focus.",
        4,
        ("--lang=en-US", *HTMLBENCH_EXTRA_BROWSER_ARGS),
        page_safety=True,
        canvas_focus=True,
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
    if profile.page_safety:
        scripts.append(("page_safety", PAGE_SAFETY_SCRIPT))
    if profile.canvas_focus:
        scripts.append(("canvas_focus", CANVAS_FOCUS_SCRIPT))
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
        "CHROMIUM_HEADLESS": "0",
        "VNC_SCREEN": "1365x768x24",
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
        "runtime_environment": {
            key: os.environ.get(key)
            for key in (
                "COMPOSE_PROJECT_NAME", "CONTAINER_NAME", "CDP_HOST_PORT",
                "NOVNC_HOST_PORT", "VNC_HOST_PORT", "CHROMIUM_HEADLESS",
                "CHROMIUM_RESET_PROFILE",
            )
        },
        "preserved_recorder_conditions": {
            "headed": True,
            "viewport": "1365x768",
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
            "synthetic_interaction_helpers": (
                "agent-browser already performs native actions"
            ),
            "window_probe": "ChromiumRL is the authoritative DOM evidence source",
        },
    }
