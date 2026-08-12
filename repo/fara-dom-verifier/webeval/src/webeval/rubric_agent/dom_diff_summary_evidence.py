"""Load and project recorder-produced DOM-diff summaries only.

Raw ``dom_diff_summary.json`` files remain authoritative.  Each loaded frame
also carries a deterministic compact projection for token-bounded model calls.
No screenshot, raw DOM diff, DOM snapshot, page-state, or verifier-action file
is read by this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from webeval.rubric_agent.dom_diff_summary_compaction import (
    CompactDOMDiffSummaryFrame,
    CompactTrajectoryLedger,
    RenderedSummary,
    TokenEstimator,
    aggregate_compaction_metrics,
    build_trajectory_ledger,
    compact_summary_frame,
    render_compact_frame,
    render_trajectory_ledger,
    source_sha256,
    validate_source_summary,
)


@dataclass(frozen=True)
class DOMDiffSummaryEvidenceFrame:
    action_ordinal: int
    action_id: str
    summary_path: str
    summary: dict[str, Any]
    diff: dict[str, Any]
    compact: CompactDOMDiffSummaryFrame
    source_sha256: str
    source_bytes: int
    schema_version: str
    method: str
    capture_status: str = "complete"
    coverage_status: str = "summary_only"
    verifier_action: None = None
    before_page_state: None = None
    after_page_state: None = None
    before_snapshot: None = None
    snapshot: None = None


def _load(path: str | Path) -> tuple[dict[str, Any], bytes]:
    raw_bytes = Path(path).read_bytes()
    try:
        value = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Malformed DOM diff summary JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"DOM diff summary must be an object: {path}")
    validate_source_summary(value)
    return value, raw_bytes


def load_dom_diff_summary_frames(
    actions: Iterable[dict[str, Any]], *, max_record_chars: int = 600
) -> list[DOMDiffSummaryEvidenceFrame]:
    frames: list[DOMDiffSummaryEvidenceFrame] = []
    previous_url: str | None = None
    previous_title: str | None = None
    for position, action in enumerate(actions, start=1):
        ordinal = int(action.get("dom_action_ordinal") or action.get("id") or 0)
        if ordinal != position:
            raise ValueError(
                f"DOM summary actions must be contiguous: expected {position}, got {ordinal}"
            )
        path = str(action.get("dom_diff_summary_path") or "")
        if not path:
            raise ValueError(f"Action {ordinal} has no dom_diff_summary_path")
        if Path(path).name != "dom_diff_summary.json":
            raise ValueError(
                f"Summary-only evidence path must end with dom_diff_summary.json: {path}"
            )
        summary, raw_bytes = _load(path)
        action_id = str(action.get("dom_action_id") or ordinal)
        compact = compact_summary_frame(
            summary,
            action_ordinal=ordinal,
            action_id=action_id,
            source_path=str(Path(path).resolve(strict=False)),
            source_hash=source_sha256(raw_bytes),
            source_bytes=len(raw_bytes),
            previous_url=previous_url,
            previous_title=previous_title,
            max_record_chars=max_record_chars,
        )
        previous_url = str(summary.get("url", {}).get("after") or previous_url or "")
        previous_title = str(
            summary.get("title", {}).get("after") or previous_title or ""
        )
        frames.append(
            DOMDiffSummaryEvidenceFrame(
                action_ordinal=ordinal,
                action_id=action_id,
                summary_path=path,
                summary=summary,
                diff=summary,
                compact=compact,
                source_sha256=compact.source_sha256,
                source_bytes=compact.source_bytes,
                schema_version=str(summary["schema_version"]),
                method=str(summary["method"]),
                capture_status=str(action.get("dom_capture_status") or "complete"),
            )
        )
    return frames


def render_summary_result(
    frame: DOMDiffSummaryEvidenceFrame,
    *,
    projection: str = "compact",
    token_budget: int = 1500,
    model: str = "gpt-5.2",
) -> RenderedSummary:
    if projection == "compact":
        return render_compact_frame(
            frame.compact, token_budget=token_budget, model=model
        )
    if projection != "raw":
        raise ValueError(f"Unsupported summary projection: {projection!r}")
    header = (
        f"DOM DIFF SUMMARY FRAME {frame.action_ordinal} action_id={frame.action_id}\n"
        f"schema={frame.schema_version}; method={frame.method}; capture={frame.capture_status}\n"
        "This is the complete recorder summary for this action; no retrieval or truncation was applied.\n"
    )
    text = header + json.dumps(
        frame.summary, ensure_ascii=False, sort_keys=True, indent=2
    )
    # Raw mode deliberately preserves the historical unbudgeted S0 baseline.
    estimator = TokenEstimator(model)
    return RenderedSummary(
        text=text,
        estimated_tokens=estimator.count(text),
        tokenizer=estimator.name,
        records_total=1,
        records_rendered=1,
        records_omitted_by_budget=0,
    )


def render_summary(
    frame: DOMDiffSummaryEvidenceFrame,
    *,
    projection: str = "compact",
    token_budget: int = 1500,
    model: str = "gpt-5.2",
) -> str:
    return render_summary_result(
        frame,
        projection=projection,
        token_budget=token_budget,
        model=model,
    ).text


def build_summary_ledger(
    frames: Iterable[DOMDiffSummaryEvidenceFrame],
) -> CompactTrajectoryLedger:
    return build_trajectory_ledger([frame.compact for frame in frames])


def render_summary_ledger(
    frames: Iterable[DOMDiffSummaryEvidenceFrame],
    *,
    token_budget: int = 16000,
    model: str = "gpt-5.2",
) -> RenderedSummary:
    return render_trajectory_ledger(
        build_summary_ledger(frames), token_budget=token_budget, model=model
    )


def summary_compaction_metrics(
    frames: Iterable[DOMDiffSummaryEvidenceFrame],
) -> dict[str, Any]:
    return aggregate_compaction_metrics([frame.compact for frame in frames])

