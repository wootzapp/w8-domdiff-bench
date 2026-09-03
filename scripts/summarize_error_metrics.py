"""Calculate recovery metrics from a reviewed evidence-error audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from .evidence_error_audit import calculate_metrics, load_json, render_markdown, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, help="Reviewed criterion audit JSON")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    audit = load_json(args.audit)
    metrics = calculate_metrics(audit)
    output_dir = Path(args.output_dir)
    write_json(output_dir / "evidence_error_metrics.json", metrics)
    (output_dir / "evidence_error_report.md").write_text(
        render_markdown(audit, metrics), encoding="utf-8"
    )
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
