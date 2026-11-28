#!/usr/bin/env python3
"""Wait until the public CDP endpoint is reachable."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time


def positive_finite_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be finite and positive") from error
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return number


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=positive_finite_float, default=30.0)
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["python3", "/opt/chromium-runtime/status.py", "--quiet", "--timeout", "2"],
            check=False,
        )
        if result.returncode == 0:
            subprocess.run(["python3", "/opt/chromium-runtime/status.py"], check=False)
            return 0
        time.sleep(0.5)

    subprocess.run(["python3", "/opt/chromium-runtime/status.py"], check=False)
    return 1


if __name__ == "__main__":
    sys.exit(main())
