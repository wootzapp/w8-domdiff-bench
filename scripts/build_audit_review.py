"""Apply confirmed manual decisions to an existing criterion audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from .evidence_error_audit import apply_reviews, load_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    audit = apply_reviews(load_json(args.audit), load_json(args.review))
    output = write_json(Path(args.output), audit)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
