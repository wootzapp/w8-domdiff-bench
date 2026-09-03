"""Create a detailed evidence-item review workspace from existing outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from .evidence_error_audit import write_json
from .evidence_item_audit import build_item_review_template


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve(strict=True)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "evidence_error_audit"
    audit, review = build_item_review_template(run_dir)
    write_json(output_dir / "criterion_audit.json", audit)
    write_json(output_dir / "evidence_item_review.json", review)
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
