"""Emit an operational-only assessment of an E0 verifier batch."""

import argparse
import json
from collections import Counter

from e0_common import BATCH_REPORT_ROOT, LOG_ROOT, read_jsonl, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch")
    parser.add_argument("--expect", choices=("ok", "cached"), default=None)
    args = parser.parse_args()
    report_path = BATCH_REPORT_ROOT / f"{args.batch}.jsonl"
    log_path = LOG_ROOT / f"{args.batch}.log"
    rows = read_jsonl(report_path) if report_path.exists() else []
    counts = Counter(row.get("status", "missing_status") for row in rows)
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    lowered = log_text.lower()
    azure_markers = [marker for marker in ("azure.identity", "azure cli", "managedidentity", "az login") if marker in lowered]
    secret_like_markers = [marker for marker in ("sk-proj-", "bearer sk-") if marker in lowered]
    expected_met = args.expect is None or (len(rows) > 0 and set(counts) == {args.expect})
    payload = {
        "batch": args.batch,
        "rows": len(rows),
        "status_counts": dict(counts),
        "expected_status": args.expect,
        "expected_status_met": expected_met,
        "all_score_paths_exist": all(
            row.get("score_path") and __import__("pathlib").Path(row["score_path"]).exists()
            for row in rows if row.get("status") in {"ok", "cached"}
        ),
        "azure_auth_markers": azure_markers,
        "secret_like_markers": secret_like_markers,
        "errors": [
            {"task_id": row.get("task_id"), "status": row.get("status"), "error": row.get("error")}
            for row in rows if row.get("status") not in {"ok", "cached"}
        ],
    }
    write_json(LOG_ROOT / f"{args.batch}_assessment.json", payload)
    print(json.dumps(payload))
    if not expected_met or azure_markers or secret_like_markers or not payload["all_score_paths_exist"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
