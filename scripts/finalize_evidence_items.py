"""Validate reviewed evidence items and emit classifications and metrics."""

from __future__ import annotations

import argparse
from pathlib import Path

from .evidence_error_audit import load_json, write_json
from .evidence_item_audit import (
    calculate_item_metrics,
    finalize_item_review,
    render_item_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, help="criterion_audit.json")
    parser.add_argument("--review", required=True, help="completed evidence_item_review.json")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    item_audit = finalize_item_review(load_json(args.audit), load_json(args.review))
    metrics = calculate_item_metrics(item_audit)
    write_json(output_dir / "evidence_item_audit.json", item_audit)
    write_json(output_dir / "evidence_error_metrics.json", metrics)
    (output_dir / "evidence_error_report.md").write_text(
        render_item_markdown(item_audit, metrics), encoding="utf-8"
    )
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
