#!/usr/bin/env python3
"""Generate catalog rubric drafts, review their hashes, then freeze approved rubrics.

Without --execute every stage is an offline, read-only preflight. Draft execution
uses the unchanged screenshot-verifier rubric/dependency prompts. Review and
freeze are offline, and frozen rubrics are shared across arms and trials.
"""

from __future__ import annotations

import hashlib

import argparse
import asyncio
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from w8bench.verifier.clients.retry import GracefulRetryClient
from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent, MMRubricAgentConfig
from .instrumentation import instrument_client_calls, usage_dict
from .rubric_scoring import FARA_ACTION_DEFINITIONS, get_init_url_context

from .common import (
    CANONICAL_RUBRIC_MODEL,
    canonical_sha256,
    ensure_under,
    load_env_file,
    require_openai_key,
    validate_endpoint_configs,
    validate_rubric,
    write_json,
)
from .package_manifests import require_local_packages
from w8bench.task_recorder.task_cli import (catalog_task_instruction, parse_task_catalog,
    safe_task_id, validate_task_definition)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPOSITORY_ROOT / "config"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-file", type=Path, required=True)
    parser.add_argument("--draft-dir", type=Path, required=True)
    parser.add_argument("--rubric-dir", type=Path, required=True)
    parser.add_argument("--stage", choices=["draft", "review", "freeze"], required=True)
    parser.add_argument("--metrics-file", type=Path)
    parser.add_argument("--eval-config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--env-file", default=str(REPOSITORY_ROOT / ".env"))
    parser.add_argument("--execute", action="store_true",
        help="Authorize draft-generation calls, review writes, or offline approved freezing")
    return parser.parse_args(argv)


def _workflow_paths(args: argparse.Namespace, catalog: Path) -> tuple[Path, Path, Path, Path, Path]:
    drafts = ensure_under(args.draft_dir, REPOSITORY_ROOT, label="draft directory")
    frozen = ensure_under(args.rubric_dir, REPOSITORY_ROOT, label="frozen rubric directory")
    if drafts == frozen or drafts in frozen.parents or frozen in drafts.parents:
        raise ValueError("Draft and frozen rubric directories must be separate")
    review_path = drafts.parent / "review.json"
    markdown_path = review_path.with_suffix(".md")
    metrics_path = ensure_under(args.metrics_file or drafts.parent / ("generation.json" if args.stage == "draft" else "freeze.json"),
        REPOSITORY_ROOT, label="workflow metrics")
    if (metrics_path in {catalog, review_path, markdown_path} or metrics_path.is_relative_to(drafts)
            or metrics_path.is_relative_to(frozen)):
        raise ValueError("Workflow metrics must not overwrite catalog, review, draft or frozen artifacts")
    return drafts, frozen, review_path, markdown_path, metrics_path


def _catalog_tasks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = []
    for row in rows:
        identity = str(row["task_id"])
        safe_task_id(identity)
        definition = validate_task_definition(catalog_task_instruction(row), str(row.get("start_url", "")))
        tasks.append({"task_id": identity, **definition})
    return tasks


def _rubric_agent(args: argparse.Namespace, clients: dict, calls: dict) -> MMRubricAgent:
    model = CANONICAL_RUBRIC_MODEL
    clients[model] = GracefulRetryClient.from_path(path=args.eval_config,
        logger=logging.getLogger("generate_frozen_rubric"), eval_model=model, evidence_mode='screenshot_verifier')
    calls[model] = instrument_client_calls(clients[model], receipt=True)
    return MMRubricAgent(config=MMRubricAgentConfig(
        action_client=clients[CANONICAL_RUBRIC_MODEL], judge_client=clients[CANONICAL_RUBRIC_MODEL],
        action_definitions=FARA_ACTION_DEFINITIONS, majority_vote_instances=1, redo_eval=True))


def _generate_draft(args: argparse.Namespace, task: dict, expected: dict, draft_path: Path, receipt_path: Path, receipt: dict, workflow: dict, metrics_path: Path) -> None:
    clients = {}
    calls = {}
    agent = None
    try:
        agent = _rubric_agent(args, clients, calls)
        rubric = asyncio.run(agent._generate_rubric(task["instruction"],
            get_init_url_context(task["start_url"])))
        denominator = validate_rubric(rubric)
        write_json(draft_path, {**expected, "precomputed_rubric": rubric})
        receipt.update(status="complete", rubric_sha256=canonical_sha256(rubric),
            draft_sha256=hashlib.sha256(draft_path.read_bytes()).hexdigest(),
            criterion_count=len(rubric["items"]), criterion_denominator=denominator)
    except BaseException as error:
        receipt.update(status="interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "error",
            error_type=type(error).__name__)
        raise
    finally:
        receipt.update(call_metrics=calls, token_usage={model: usage_dict(client) for model, client in clients.items()},
            rubric_generation_calls=sum(value["logical_calls"] for value in calls.values()),
            generation_trace=getattr(agent, "rubric_generation_trace", []))
        write_json(receipt_path, receipt)
        workflow["tasks"].append({"task_id": task["task_id"], "status": receipt["status"],
            "receipt": os.path.relpath(receipt_path, REPOSITORY_ROOT)})
        workflow["status"] = "running" if receipt["status"] == "complete" else receipt["status"]
        write_json(metrics_path, workflow)


def _draft_task(args: argparse.Namespace, task: dict, catalog_hash: str, drafts: Path, workflow: dict, metrics_path: Path) -> None:
    draft_path = drafts / f"{task['task_id']}.json"
    receipt_path = drafts / f"{task['task_id']}.metrics.json"
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    expected = {**task, "catalog_sha256": catalog_hash}
    if previous and previous.get("task_binding") != expected:
        raise ValueError(f"Draft receipt task changed: {task['task_id']}")
    if draft_path.exists():
        payload = json.loads(draft_path.read_text())
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Draft task changed: {task['task_id']}")
        validate_rubric(payload.get("precomputed_rubric"))
        if not previous or previous.get("status") != "complete":
            raise ValueError(f"Draft has no completed generation receipt: {task['task_id']}")
        workflow["tasks"].append({"task_id": task["task_id"], "status": "cached",
            "receipt": os.path.relpath(receipt_path, REPOSITORY_ROOT)})
        write_json(metrics_path, workflow)
        return
    receipt = {"task_binding": expected, "status": "running", "origin": "screenshot_generate_rubric",
        "attempt_history": ([*previous.get("attempt_history", []),
            {key: value for key, value in previous.items() if key != "attempt_history"}] if previous else [])}
    write_json(receipt_path, receipt)
    _generate_draft(args, task, expected, draft_path, receipt_path, receipt, workflow, metrics_path)


def _draft_catalog(args: argparse.Namespace, tasks: list, catalog_hash: str, drafts: Path, frozen: Path, metrics_path: Path, preflight: dict) -> int:
    if any(frozen.glob("*.json")):
        raise ValueError("Frozen rubrics exist; choose a distinct rubric version before drafting")
    load_env_file(args.env_file)
    require_openai_key()
    workflow = {**preflight, "status": "running", "tasks": []}
    write_json(metrics_path, workflow)
    for task in tasks:
        _draft_task(args, task, catalog_hash, drafts, workflow, metrics_path)
    workflow["status"] = "complete"
    write_json(metrics_path, workflow)
    print(json.dumps(workflow, ensure_ascii=False, indent=2))
    return 0


def _generation_summary(generation: dict, receipt_path: Path) -> dict:
    return {
        "generation_receipt": os.path.relpath(receipt_path, REPOSITORY_ROOT),
        "generation_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "generation_usage": generation.get("token_usage", {}),
        "generation_calls": generation.get("rubric_generation_calls"),
        "generation_calls_all_attempts": (sum(attempt["rubric_generation_calls"]
            for attempt in [*generation.get("attempt_history", []), generation])
            if all(isinstance(attempt.get("rubric_generation_calls"), int)
                for attempt in [*generation.get("attempt_history", []), generation]) else None),
        "generation_calls_known_lower_bound": sum(attempt.get("rubric_generation_calls") or 0
            for attempt in [*generation.get("attempt_history", []), generation]),
        "prior_attempt_usage": [{key: attempt.get(key) for key in
            ("status", "rubric_generation_calls", "token_usage")}
            for attempt in generation.get("attempt_history", [])],
        "dependency_checks": [{key: value for key, value in trace.items() if key != "messages"}
            for trace in generation.get("generation_trace", []) if trace.get("stage") == "dependency_check"],
        "generation_cost": {"estimated_usd": None, "status": "unknown_no_trusted_price_configuration"},
    }


def _review_entry(task: dict, catalog_hash: str, drafts: Path, previous_tasks: dict) -> tuple[dict, dict]:
    draft_path = drafts / f"{task['task_id']}.json"
    receipt_path = drafts / f"{task['task_id']}.metrics.json"
    payload = json.loads(draft_path.read_text())
    expected = {**task, "catalog_sha256": catalog_hash}
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Draft/catalog binding differs: {task['task_id']}")
    rubric = payload.get("precomputed_rubric")
    validate_rubric(rubric)
    generation = json.loads(receipt_path.read_text())
    if generation.get("status") != "complete" or generation.get("task_binding") != expected:
        raise ValueError(f"Draft generation did not complete for this task: {task['task_id']}")
    entry = {"task_id": task["task_id"], "task_sha256": canonical_sha256(expected),
        "draft_sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
        "rubric_sha256": canonical_sha256(rubric), "criteria": rubric["items"],
        **_generation_summary(generation, receipt_path),
        "review_checks": ["Covers the expanded task, stopping condition and constraints",
            "Checkable from within-run observations/final answer without prohibited actions",
            "Same criteria/weights for both arms and every trial",
            "No actor-specific targeting requirement or visual-only answer",
            "Mutable values use run-time evidence and observation date, not frozen answers",
            "No redundant, ambiguous or out-of-scope criteria"],
        "approved": False, "review_notes": ""}
    old = previous_tasks.get(task["task_id"], {})
    if all(old.get(key) == entry[key] for key in ("task_sha256", "draft_sha256", "rubric_sha256", "generation_receipt_sha256")):
        entry.update(approved=old.get("approved") is True, review_notes=old.get("review_notes", ""))
    return entry, payload


def _catalog_review(tasks: list, catalog_hash: str, drafts: Path, frozen: Path, review_path: Path) -> tuple[dict, list, dict]:
    previous_review = json.loads(review_path.read_text()) if review_path.exists() else {}
    review = {"schema_version": "catalog-rubric-review/v1", "catalog_sha256": catalog_hash,
        "approved_by": previous_review.get("approved_by", ""),
        "approval_date": previous_review.get("approval_date", ""), "tasks": []}
    previous_tasks = {item["task_id"]: item for item in previous_review.get("tasks", [])}
    outputs = []
    for task in tasks:
        entry, payload = _review_entry(task, catalog_hash, drafts, previous_tasks)
        review["tasks"].append(entry)
        outputs.append((frozen / f"{task['task_id']}.json", payload))
    return review, outputs, previous_review


def _review_lines(tasks: list, review: dict) -> list[str]:
    lines = ["# Rubric review", "",
        "Review the drafts and this checklist, then set each approved field and review notes in review.json.",
        "Set approved_by and approval_date only after approval. Freeze refuses changed task or draft hashes.", ""]
    for task, entry in zip(tasks, review["tasks"]):
        lines.extend([f"## {task['task_id']}", "", task["instruction"], "", f"Start URL: {task['start_url']}",
            "", "| Criterion | Description | Points |",
            "| --- | --- | --- |"])
        for item in entry["criteria"]:
            lines.append("| " + " | ".join(str(item[key]).replace("|", "\\|").replace("\n", " ")
                for key in ("criterion", "description", "max_points")) + " |")
        lines.extend(["", "### Preparation receipt", "",
            f"Receipt: `{entry['generation_receipt']}`.",
            f"Logical calls: {entry['generation_calls']} latest attempt; {entry['generation_calls_all_attempts']} across all attempts "
                f"(unknown when an attempt lacks a receipt count; known lower bound {entry['generation_calls_known_lower_bound']}).",
            "Estimated USD cost: unknown; no trusted price configuration is supplied. Usage is retained per model.",
            "", "```json", json.dumps({"latest_attempt_usage": entry["generation_usage"],
                "prior_attempt_usage": entry["prior_attempt_usage"]}, ensure_ascii=False, indent=2), "```", "",
            "### Dependency checking", "", "```json",
            json.dumps(entry["dependency_checks"], ensure_ascii=False, indent=2), "```", "",
            *[f"- [ ] {check}" for check in entry["review_checks"]], ""])
    return lines


def _review_stage(args: argparse.Namespace, preflight: dict, tasks: list, review: dict, previous_review: dict, review_path: Path, markdown_path: Path) -> int:
    if not args.execute:
        print(json.dumps({**preflight, "drafts_validated": len(tasks), "review": review},
            ensure_ascii=False, indent=2))
        return 0
    if previous_review and previous_review != review:
        archive = review_path.parent / "review_history" / f"{canonical_sha256(previous_review)}.json"
        if not archive.exists():
            write_json(archive, previous_review)
    write_json(review_path, review)
    lines = _review_lines(tasks, review)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "review_required", "task_count": len(tasks),
        "review_file": str(review_path), "markdown": str(markdown_path)}, indent=2))
    return 0


def _freeze_catalog(args: argparse.Namespace, preflight: dict, tasks: list, catalog_hash: str, review_path: Path, previous_review: dict, review: dict, outputs: list, metrics_path: Path) -> int:
    if not previous_review or previous_review.get("catalog_sha256") != catalog_hash or previous_review != review:
        raise ValueError("Review is missing or task/draft hashes changed; regenerate and approve the review")
    if not isinstance(review["approved_by"], str) or not review["approved_by"].strip() or any(
        item["approved"] is not True or not isinstance(item["review_notes"], str) or not item["review_notes"].strip()
        for item in review["tasks"]):
        raise ValueError("Every rubric requires explicit approval and review notes, plus approved_by/approval_date")
    try:
        date.fromisoformat(review["approval_date"])
    except (TypeError, ValueError):
        raise ValueError("approval_date must be an ISO calendar date (YYYY-MM-DD)") from None
    approval_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
    frozen_payloads = [(path, {**payload, "rubric_approval_sha256": approval_hash}) for path, payload in outputs]
    for path, payload in frozen_payloads:
        if path.exists() and json.loads(path.read_text()) != payload:
            raise ValueError(f"Refusing to change an existing frozen rubric: {path}")
    if not args.execute:
        print(json.dumps({**preflight, "approved_rubrics_validated": len(tasks)},
            ensure_ascii=False, indent=2))
        return 0
    for path, payload in frozen_payloads:
        if not path.exists():
            write_json(path, payload)
    result = {"status": "frozen", "task_count": len(tasks), "rubrics": [
            {"task_id": payload["task_id"], "path": os.path.relpath(path, REPOSITORY_ROOT)}
            for path, payload in frozen_payloads]}
    write_json(metrics_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packages = require_local_packages()
    catalog = args.catalog_file.resolve(strict=True)
    catalog_bytes = catalog.read_bytes()
    catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
    rows = parse_task_catalog(catalog_bytes.decode("utf-8"), source=str(catalog))
    drafts, frozen, review_path, markdown_path, metrics_path = _workflow_paths(args, catalog)
    endpoint_receipt = validate_endpoint_configs(args.eval_config)
    tasks = _catalog_tasks(rows)
    preflight = {"status": "ready", "stage": args.stage, "task_count": len(tasks),
        "models": [CANONICAL_RUBRIC_MODEL],
        "paid_calls_authorized": bool(args.execute and args.stage == "draft"),
        "writes_authorized": bool(args.execute), "endpoint_config": endpoint_receipt,
        "verifier_packages": packages,
        "draft_directory": os.path.relpath(drafts, REPOSITORY_ROOT),
        "frozen_directory": os.path.relpath(frozen, REPOSITORY_ROOT),
        "review_file": os.path.relpath(review_path, REPOSITORY_ROOT)}
    if not args.execute and args.stage == "draft":
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return 0
    if args.stage == "draft":
        return _draft_catalog(args, tasks, catalog_hash, drafts, frozen, metrics_path, preflight)
    review, outputs, previous_review = _catalog_review(tasks, catalog_hash, drafts, frozen, review_path)
    if args.stage == "review":
        return _review_stage(args, preflight, tasks, review, previous_review, review_path, markdown_path)
    return _freeze_catalog(args, preflight, tasks, catalog_hash, review_path, previous_review, review, outputs, metrics_path)


if __name__ == "__main__":
    raise SystemExit(main())
