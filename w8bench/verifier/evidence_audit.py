"""Same-run evidence-loss audit and metric assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from typing import Any, Callable

from . import audit_evidence, audit_requests, audit_validation
from .common import CanonicalRubric, canonical_sha256, load_canonical_rubric, load_json


SCHEMA_VERSION = "automated-evidence-audit/v7"


PROMPT_VERSION = "paired-capture-eligible-state-adjudication/v7"


def _criteria_payload(rubric: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "criterion_index": index,
            "criterion": item["criterion"],
            "description": item["description"],
            "max_points": item["max_points"],
        }
        for index, item in enumerate(rubric["items"])
    ]


@dataclass
class _AuditInputs:
    frozen: CanonicalRubric
    criteria: list[dict[str, Any]]
    screenshot_context: list[dict[str, Any]]
    dom_context: list[dict[str, Any]]
    screenshot_root: Path
    dom_root: Path
    shared_trajectory: dict[str, Any]
    screen_sources: set[str]
    dom_sources: set[str]
    screenshot_result: str | Path
    dom_result: str | Path


@dataclass
class _StageJudgment:
    decisions: list[dict[str, Any]]
    raw: dict[str, Any]
    attempts: int
    invalid: list[dict[str, Any]]


def _count_rate(count: int, denominator: int) -> dict[str, Any]:
    return {
        "count": count,
        "denominator": denominator,
        "rate": count / denominator if denominator else None,
    }


def _recovered_misses(criteria, missing: str, available: str) -> int:
    return sum(
        not row[missing]["verifier_caught"]
        and row[available]["verifier_caught"]
        and not row["screenshot_evidence_loss"]
        and not row["dom_model_evidence_loss"]
        for row in criteria
    )


def _inventory_agreement(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    agreement = {}
    for mode in ("screenshot", "dom_model"):
        statuses = {
            key: 0 for key in ("confirmed", "rejected", "added", "not_proposed")
        }
        for row in criteria:
            decision = row.get("loss_agreement", {}).get(mode)
            if decision:
                statuses[decision["status"]] += 1
        comparable = sum(statuses.values())
        same = statuses["confirmed"] + statuses["not_proposed"]
        agreement[mode] = {
            **statuses,
            "compared": comparable,
            "agreement_count": same,
            "disagreement_count": comparable - same,
            "agreement_rate": same / comparable if comparable else None,
        }
    return agreement


def _coverage_conflicts(criteria: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "criteria": sum(bool(row.get("coverage_conflict")) for row in criteria),
        "flags": sum(
            len({item["side"] for item in row.get("coverage_conflicts", [])})
            for row in criteria
        ),
        "details": sum(len(row.get("coverage_conflicts", [])) for row in criteria),
    }


def calculate_metrics(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(criteria)
    if total == 0:
        raise ValueError("Cannot calculate evidence loss with zero criteria")
    screenshot_loss = sum(bool(row["screenshot_evidence_loss"]) for row in criteria)
    dom_loss = sum(bool(row["dom_model_evidence_loss"]) for row in criteria)
    screenshot_misses = sum(
        not row["screenshot"]["verifier_caught"] for row in criteria
    )
    dom_misses = sum(not row["dom_model"]["verifier_caught"] for row in criteria)
    screenshot_recovered = _recovered_misses(criteria, "screenshot", "dom_model")
    dom_recovered = _recovered_misses(criteria, "dom_model", "screenshot")
    agreement = _inventory_agreement(criteria)
    return {
        "total_criteria": total,
        "inventory_adjudication_agreement": agreement,
        "coverage_conflicts": _coverage_conflicts(criteria),
        "requires_human_review": sum(
            bool(
                row["screenshot_evidence_loss"]
                or row["dom_model_evidence_loss"]
                or not row["screenshot"]["verifier_caught"]
                or not row["dom_model"]["verifier_caught"]
            )
            for row in criteria
        ),
        "retry_flag_flips": sum(
            len(row.get("retry_flag_flips", [])) for row in criteria
        ),
        "screenshot_evidence_loss": _count_rate(screenshot_loss, total),
        "dom_model_evidence_loss": _count_rate(dom_loss, total),
        "screenshot_verifier_misses": _count_rate(screenshot_misses, total),
        "dom_model_verifier_misses": _count_rate(dom_misses, total),
        "screenshot_misses_recovered_by_dom": _count_rate(
            screenshot_recovered, screenshot_misses
        ),
        "dom_misses_recovered_by_screenshot": _count_rate(dom_recovered, dom_misses),
    }


def _load_inputs(
    screenshot_dir, dom_dir, rubric_file, screenshot_result, dom_result
) -> _AuditInputs:
    frozen = load_canonical_rubric(rubric_file)
    criteria = _criteria_payload(frozen.rubric)
    screenshot_raw = load_json(screenshot_result)
    dom_raw = load_json(dom_result)
    if (
        screenshot_raw.get("task_id") != frozen.task_id
        or dom_raw.get("task_id") != frozen.task_id
    ):
        raise ValueError("Evidence audit result task IDs differ from the frozen rubric")
    if (
        screenshot_raw.get("rubric_sha256") != frozen.sha256
        or dom_raw.get("rubric_sha256") != frozen.sha256
    ):
        raise ValueError(
            "Evidence audit result rubric hashes differ from the frozen rubric"
        )
    screenshot_context = audit_evidence.extract_verifier_context(
        screenshot_raw, len(criteria)
    )
    dom_context = audit_evidence.extract_verifier_context(dom_raw, len(criteria))
    screenshot_root = Path(screenshot_dir).resolve(strict=True)
    dom_root = Path(dom_dir).resolve(strict=True)
    shared_trajectory = audit_evidence.shared_trajectory_payload(
        screenshot_root, dom_root
    )
    if (
        shared_trajectory.get("evaluation_context")
        and not shared_trajectory["evaluation_context"]["audit_eligible_states"]
    ):
        raise ValueError("No audit-eligible paired states; evidence loss is ungraded")
    screen_sources = {
        path.name for path in audit_evidence.ordered_audit_screenshots(screenshot_root)
    }
    dom_sources = {path.name for path in audit_evidence.ordered_dom_states(dom_root)}
    return _AuditInputs(
        frozen,
        criteria,
        screenshot_context,
        dom_context,
        screenshot_root,
        dom_root,
        shared_trajectory,
        screen_sources,
        dom_sources,
        screenshot_result,
        dom_result,
    )


def _checked_models(config, model_check, complete):
    if model_check is None and complete is None:
        model_check = audit_requests.check_audit_models(config)
    if model_check is not None:
        for stage, selected in config.items():
            checked = model_check.get("stages", {}).get(stage, {})
            if (
                any(checked.get(key) != value for key, value in selected.items())
                or not checked.get("model_listed")
                or not checked.get("listed_at")
            ):
                raise ValueError(f"Model-list check does not match configured {stage}")
    return model_check


def _completion_call(config, records, complete):
    return complete or (
        lambda selected_model, messages: audit_requests._completion(
            selected_model,
            messages,
            records=records,
            provider=config[
                "adjudication"
                if messages[0]["content"] == audit_requests.ADJUDICATION_SYSTEM_PROMPT
                else "inventory"
            ]["provider"],
        )
    )


def _request_inventory(inputs: _AuditInputs, model, call, invalid) -> _StageJudgment:
    decisions, raw, attempts = audit_requests._request_validated_audit(
        model=model,
        messages=audit_requests.pairwise_messages(
            screenshot_dir=inputs.screenshot_root,
            dom_dir=inputs.dom_root,
            criteria=inputs.criteria,
            screenshot_context=inputs.screenshot_context,
            dom_context=inputs.dom_context,
            shared_trajectory=inputs.shared_trajectory,
        ),
        criteria=inputs.criteria,
        screenshot_sources=inputs.screen_sources,
        dom_sources=inputs.dom_sources,
        screenshot_root=inputs.screenshot_root,
        dom_root=inputs.dom_root,
        complete=call,
        invalid_receipts=invalid,
    )
    return _StageJudgment(decisions, raw, attempts, invalid)


def _request_adjudication(
    inputs: _AuditInputs, model, preliminary, call, invalid
) -> _StageJudgment:
    decisions, raw, attempts = audit_requests._request_validated_audit(
        inventory=False,
        model=model,
        messages=audit_requests.adjudication_messages(
            screenshot_dir=inputs.screenshot_root,
            dom_dir=inputs.dom_root,
            criteria=inputs.criteria,
            shared_trajectory=inputs.shared_trajectory,
            screenshot_context=inputs.screenshot_context,
            dom_context=inputs.dom_context,
            preliminary=preliminary,
        ),
        criteria=inputs.criteria,
        screenshot_sources=inputs.screen_sources,
        dom_sources=inputs.dom_sources,
        screenshot_root=inputs.screenshot_root,
        dom_root=inputs.dom_root,
        complete=call,
        invalid_receipts=invalid,
    )
    return _StageJudgment(decisions, raw, attempts, invalid)


def _loss_agreement(decision, adjudication):
    conflicts, agreement = [], {}
    for side, counterpart in (("screenshot", "dom_model"), ("dom_model", "screenshot")):
        proposal = decision[side + "_evidence_loss"]
        final = adjudication[side + "_evidence_loss"]["confirmed"]
        agreement[side] = {
            "inventory_proposed": proposal,
            "adjudicator_confirmed": final,
            "status": ("confirmed" if final else "rejected")
            if proposal
            else ("added" if final else "not_proposed"),
        }
        if final:
            if decision[side]["coverage"] == "COMPLETE":
                conflicts.append(
                    {
                        "side": side,
                        "reason": "loss_confirmed_despite_complete_inventory_coverage",
                        "inventory_coverage": "COMPLETE",
                    }
                )
            if decision[counterpart]["coverage"] == "ABSENT":
                conflicts.append(
                    {
                        "side": side,
                        "reason": "counterpart_inventory_coverage_absent",
                        "counterpart": counterpart,
                        "inventory_coverage": "ABSENT",
                    }
                )
    return conflicts, agreement


def _retry_flips(criterion, inventory: _StageJudgment, adjudication: _StageJudgment):
    return [
        {"stage": stage, "failed_attempt": receipt["attempt"], **change}
        for stage, receipts in (
            ("inventory", inventory.invalid),
            ("adjudication", adjudication.invalid),
        )
        for receipt in receipts
        for change in receipt.get("flag_flips", [])
        if change["criterion_index"] == criterion["criterion_index"]
    ]


def _criterion_row(criterion, decision, adjudication, contexts, stages):
    screen_context, dom_verifier_context = contexts
    screenshot_loss = adjudication["screenshot_evidence_loss"]["confirmed"]
    dom_loss = adjudication["dom_model_evidence_loss"]["confirmed"]
    screenshot_caught = not adjudication["screenshot_verifier_miss"]["confirmed"]
    dom_caught = not adjudication["dom_model_verifier_miss"]["confirmed"]
    screenshot_decision = {
        **decision["screenshot"],
        "verifier_caught": screenshot_caught,
        "verifier_output": screen_context,
    }
    dom_decision = {
        **decision["dom_model"],
        "verifier_caught": dom_caught,
        "verifier_output": dom_verifier_context,
    }
    conflicts, agreement = _loss_agreement(decision, adjudication)
    flips = _retry_flips(criterion, *stages)
    return {
        **criterion,
        "required_evidence": decision["required_evidence"],
        "screenshot": screenshot_decision,
        "dom_model": dom_decision,
        "screenshot_evidence_loss": screenshot_loss,
        "dom_model_evidence_loss": dom_loss,
        "coverage_conflict": bool(conflicts),
        "coverage_conflicts": conflicts,
        "loss_agreement": agreement,
        "retry_flag_flips": flips,
        "requires_human_review": screenshot_loss
        or dom_loss
        or not screenshot_caught
        or not dom_caught,
        "classification": audit_validation.classification(
            screenshot_decision, dom_decision, screenshot_loss, dom_loss
        ),
        "explanation": adjudication["explanation"],
        "adjudication": adjudication,
        "preliminary_inventory": decision,
    }


def _criteria_rows(
    inputs: _AuditInputs, inventory: _StageJudgment, adjudication: _StageJudgment
):
    rows = []
    for criterion, decision, final, screen_context, dom_context in zip(
        inputs.criteria,
        inventory.decisions,
        adjudication.decisions,
        inputs.screenshot_context,
        inputs.dom_context,
    ):
        rows.append(
            _criterion_row(
                criterion,
                decision,
                final,
                (screen_context, dom_context),
                (inventory, adjudication),
            )
        )
    return rows


def _run_manifest(config, model_check, records):
    return {
        "models": {
            stage: {
                "requested_model": selected["model"],
                "provider": selected["provider"],
                "listing_time": (model_check or {})
                .get("stages", {})
                .get(stage, {})
                .get("listed_at"),
                "response_models": sorted(
                    {
                        record["response_model"]
                        for record in records
                        if record.get("stage") == stage and record.get("response_model")
                    }
                ),
            }
            for stage, selected in config.items()
        },
        "response_model_drift": any(
            len(
                {
                    record["response_model"]
                    for record in records
                    if record.get("stage") == stage and record.get("response_model")
                }
            )
            > 1
            for stage in config
        ),
        "transport_policy": {
            "max_attempts": 3,
            "backoff_seconds": [1, 2],
            "retry_statuses": [429, "5xx"],
            "retry_connection_errors": True,
        },
    }


def _report_header(config, models, model_check, records, started_at, run_name):
    model, adjudicator_model = models
    return {
        "schema_version": SCHEMA_VERSION,
        "run_name": run_name,
        "prompt_version": PROMPT_VERSION,
        "audit_method": "automated_llm",
        "audit_model": model,
        "adjudicator_model": adjudicator_model,
        "audit_provider": config["inventory"]["provider"],
        "adjudicator_provider": config["adjudication"]["provider"],
        "run_manifest": _run_manifest(config, model_check, records),
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def _generation_settings(config, records, complete):
    return {
        stage: {
            "requested": (
                audit_requests.GEMINI_GENERATION_SETTINGS
                if config[stage]["provider"] == "google"
                else audit_requests.OPENAI_GENERATION_SETTINGS
            ).copy(),
            "provider": config[stage]["provider"],
            "api_version": audit_requests.GEMINI_API_VERSION
            if config[stage]["provider"] == "google"
            else None,
            "actual": [
                record["generation_settings"]
                for record in records
                if record.get("stage") == stage
                and record.get("generation_settings") is not None
            ],
            "injected_complete": complete is not None,
        }
        for stage in ("inventory", "adjudication")
    }


def _evidence_paths(inputs: _AuditInputs):
    return {
        "screenshots": [
            os.path.relpath(
                inputs.screenshot_root / name, Path(__file__).resolve().parents[2]
            )
            for name in sorted(inputs.screen_sources)
        ],
        "dom_states": [
            os.path.relpath(inputs.dom_root / name, Path(__file__).resolve().parents[2])
            for name in sorted(inputs.dom_sources)
        ],
        "action_history": {
            "screenshot": os.path.relpath(
                inputs.screenshot_root / "web_surfer.log",
                Path(__file__).resolve().parents[2],
            ),
            "dom_model": os.path.relpath(
                inputs.dom_root / "web_surfer.log", Path(__file__).resolve().parents[2]
            ),
        },
    }


def _fingerprints(inputs: _AuditInputs):
    return {
        "frozen_rubric": inputs.frozen.sha256,
        "shared_trajectory": canonical_sha256(inputs.shared_trajectory),
        "screenshot_verifier_result": hashlib.sha256(
            Path(inputs.screenshot_result).read_bytes()
        ).hexdigest(),
        "dom_verifier_result": hashlib.sha256(
            Path(inputs.dom_result).read_bytes()
        ).hexdigest(),
        "screenshot_sources": {
            name: hashlib.sha256(
                (inputs.screenshot_root / name).read_bytes()
            ).hexdigest()
            for name in sorted(inputs.screen_sources)
        },
        "dom_sources": {
            name: hashlib.sha256((inputs.dom_root / name).read_bytes()).hexdigest()
            for name in sorted(inputs.dom_sources)
        },
    }


def _report_evidence(inputs: _AuditInputs, task_alias):
    return {
        "task_id": inputs.frozen.task_id,
        "task_alias": task_alias,
        "frozen_rubric_sha256": inputs.frozen.sha256,
        "evidence_paths": _evidence_paths(inputs),
        "input_fingerprints": _fingerprints(inputs),
        "shared_trajectory": inputs.shared_trajectory,
        **(
            {
                "capture_eligibility": {
                    key: inputs.shared_trajectory["evaluation_context"][key]
                    for key in (
                        "expected_state_ids",
                        "format_gaps",
                        "navigation_states",
                        "audit_eligible_states",
                    )
                }
            }
            if inputs.shared_trajectory.get("evaluation_context")
            else {}
        ),
    }


def _stage_output(stage: _StageJudgment):
    return {
        "attempts": stage.attempts,
        "raw": stage.raw,
        "invalid_attempts": stage.invalid,
    }


def _report_decisions(inventory: _StageJudgment, adjudication: _StageJudgment, rows):
    return {
        "primary_auditor_output": _stage_output(inventory),
        "adjudicator_output": _stage_output(adjudication),
        "criteria": rows,
        "metrics": calculate_metrics(rows),
    }


def run_evidence_audit(
    *,
    screenshot_dir: str | Path,
    dom_dir: str | Path,
    rubric_file: str | Path,
    screenshot_result: str | Path,
    dom_result: str | Path,
    task_alias: str | None = None,
    model: str | None = None,
    adjudicator_model: str | None = None,
    audit_provider: str | None = None,
    adjudicator_provider: str | None = None,
    model_check: dict | None = None,
    complete: Callable[[str, list[dict[str, Any]]], dict[str, Any]] | None = None,
    call_records: list[dict[str, Any]] | None = None,
    run_name: str | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    from w8bench.run_paths import resolve_run_name

    run_name = resolve_run_name(run_name)
    config = audit_requests.resolve_audit_config(
        model, adjudicator_model, audit_provider, adjudicator_provider
    )
    model, adjudicator_model = (
        config["inventory"]["model"],
        config["adjudication"]["model"],
    )
    inputs = _load_inputs(
        screenshot_dir, dom_dir, rubric_file, screenshot_result, dom_result
    )
    records = call_records if call_records is not None else []
    inventory_invalid, adjudication_invalid = [], []
    model_check = _checked_models(config, model_check, complete)
    call = _completion_call(config, records, complete)
    inventory = _request_inventory(inputs, model, call, inventory_invalid)
    adjudication = _request_adjudication(
        inputs, adjudicator_model, inventory.decisions, call, adjudication_invalid
    )
    rows = _criteria_rows(inputs, inventory, adjudication)
    report = _report_header(
        config, (model, adjudicator_model), model_check, records, started_at, run_name
    )
    report["generation_settings"] = _generation_settings(config, records, complete)
    from w8bench.settings import audit_settings
    report["effective_settings"] = audit_settings(config, rubric_hash=inputs.frozen.sha256)
    report["calls"] = records
    report.update(_report_evidence(inputs, task_alias))
    report.update(_report_decisions(inventory, adjudication, rows))
    return report
