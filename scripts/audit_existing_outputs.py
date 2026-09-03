"""Create an offline side-by-side audit from an existing comparison run."""

from __future__ import annotations

import argparse
from pathlib import Path

from .evidence_error_audit import (
    calculate_metrics,
    extract_run,
    render_markdown,
    review_template,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Completed task/run directory")
    parser.add_argument("--output-dir", help="Defaults to RUN_DIR/evidence_error_audit")
    parser.add_argument(
        "--review-all",
        action="store_true",
        help="Include agreement criteria in the manual review template",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve(strict=True)
    output_dir = (
        Path(args.output_dir).resolve() if args.output_dir else run_dir / "evidence_error_audit"
    )
    audit = extract_run(run_dir)
    metrics = calculate_metrics(audit)
    write_json(output_dir / "criterion_audit.json", audit)
    write_json(
        output_dir / "disagreement_review.json",
        review_template(audit, include_all=args.review_all),
    )
    write_json(output_dir / "evidence_error_metrics.json", metrics)
    (output_dir / "evidence_error_report.md").write_text(
        render_markdown(audit, metrics), encoding="utf-8"
    )
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
