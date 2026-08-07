#!/usr/bin/env python3
"""Run the normal model loop with diagnostics-only three-method captures.

This wrapper does not modify recorder.py or the runner. It replaces the imported
capture function in memory, calls the original capture unchanged, then records
the three raw ChromiumRL responses at the same before/after boundary.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent_browser import desktop_agent as runner  # noqa: E402


ORIGINAL_CAPTURE = runner.capture_state_with_recovery
OBSERVATION_PARAMS = {
    "includeContent": True,
    "maxElements": 250,
    "maxInteractiveElements": 250,
}
STRUCTURED_PARAMS: dict[str, Any] = {}


async def timed_chromiumrl_call(
    cdp: runner.CDPConnection,
    method: str,
    params: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await runner.chromiumrl_call(
            cdp,
            method,
            params,
            timeout=runner.TIMEOUT_DOM_CAPTURE,
            label=label,
        )
        return {
            "ok": True,
            "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
            "params": params,
            "result": result,
        }
    except Exception as error:
        return {
            "ok": False,
            "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
            "params": params,
            "error": f"{type(error).__name__}: {error}",
        }


async def capture_with_three_methods(
    cdp: runner.CDPConnection,
    directory: Path,
    label: str,
    screenshot_config: runner.ScreenshotConfig,
    **kwargs: Any,
):
    state = await ORIGINAL_CAPTURE(
        cdp,
        directory,
        label,
        screenshot_config,
        **kwargs,
    )

    methods = {}
    for method, params in (
        ("ChromiumRL.saveDOMState", {}),
        ("ChromiumRL.getAgentObservation", OBSERVATION_PARAMS),
        ("ChromiumRL.captureStructuredSnapshot", STRUCTURED_PARAMS),
    ):
        methods[method] = await timed_chromiumrl_call(
            cdp,
            method,
            dict(params),
            label=f"real_comparison:{label}:{method.rsplit('.', 1)[-1]}",
        )

    payload = {
        "schemaVersion": "1.0",
        "capturedAt": runner.utc_now(),
        "phase": label,
        "page": state.page_state,
        "methods": methods,
    }
    if directory.name in {".before_tmp", ".after_tmp"}:
        output = directory.parent / f"capture_{label}.json.gz"
    else:
        output = directory / f"capture_{label}.json.gz"
    runner.write_json_gz(output, payload)
    print(
        "Three-method diagnostic capture:",
        output,
        json.dumps({name: item.get("ok") for name, item in methods.items()}),
        flush=True,
    )
    return state


def main() -> None:
    runner.capture_state_with_recovery = capture_with_three_methods
    args = runner.build_parser().parse_args()
    if args.max_steps <= 0:
        raise SystemExit("--max-steps must be positive")
    try:
        asyncio.run(runner.run(args))
    except runner.RecorderError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
