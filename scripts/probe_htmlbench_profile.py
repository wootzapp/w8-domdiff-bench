#!/usr/bin/env python3
"""Probe observable HTMLBench profile semantics through the recorder CDP client."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture import CDPClient  # noqa: E402
from htmlbench_profiles import profile_names  # noqa: E402


PROBE_HTML = """<!doctype html>
<html lang="en">
  <body>
    <canvas id="probe-canvas" width="20" height="20"></canvas>
    <img id="probe-image" alt="probe" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='8'%3E%3Crect width='8' height='8' fill='red'/%3E%3C/svg%3E">
    <video id="probe-video"></video>
  </body>
</html>"""


PROBE_EXPRESSION = r"""
(async () => {
  await new Promise((resolve) => setTimeout(resolve, 700));
  const canvas = document.querySelector('#probe-canvas');
  canvas.click();
  await new Promise((resolve) => setTimeout(resolve, 50));
  const image = document.querySelector('#probe-image');
  const video = document.querySelector('#probe-video');
  const mediaPlay = await Promise.race([
    video.play().then(() => 'resolved', (error) => `rejected:${error.name}`),
    new Promise((resolve) => setTimeout(() => resolve('timeout'), 1000)),
  ]);
  const AudioCtor = window.AudioContext || window.webkitAudioContext;
  let audio = null;
  try {
    const context = AudioCtor ? new AudioCtor() : null;
    audio = context ? {
      constructor: context.constructor.name,
      sampleRate: context.sampleRate,
      state: context.state,
    } : null;
    if (context && context.close) await context.close();
  } catch (error) {
    audio = {error: `${error.name}:${error.message}`};
  }
  return {
    url: location.href,
    pageSafetyInstalled: Boolean(window.__htmlbenchEvalPageSafetyInstalled),
    canvasFocusInstalled: Boolean(window.__htmlbenchEvalCanvasFocusInstalled),
    canvasTabIndexAttribute: canvas.getAttribute('tabindex'),
    canvasIsFocused: document.activeElement === canvas,
    imageComplete: image.complete,
    imageNaturalWidth: image.naturalWidth,
    mediaPlay,
    audio,
  };
})()
""".strip()


async def probe(cdp_url: str, profile: str) -> dict[str, object]:
    async with CDPClient(cdp_url, htmlbench_profile=profile) as cdp:
        await cdp.call(
            "Page.navigate",
            {"url": "data:text/html;charset=utf-8," + quote(PROBE_HTML)},
        )
        result = await cdp.call(
            "Runtime.evaluate",
            {
                "expression": PROBE_EXPRESSION,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        exception = result.get("exceptionDetails")
        if exception:
            raise RuntimeError(f"profile probe failed: {exception}")
        value = result.get("result", {}).get("value", {})
        return {
            "profile": profile,
            "browser": cdp.browser_version,
            "init_scripts": cdp.connection_report.get("locale_setup", {}).get(
                "htmlbench_init_scripts", []
            ),
            "observed": value,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp-url", required=True)
    parser.add_argument("--profile", choices=profile_names(), required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(probe(args.cdp_url, args.profile)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
