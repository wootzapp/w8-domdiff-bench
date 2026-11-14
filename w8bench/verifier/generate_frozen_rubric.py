#!/usr/bin/env python3
"""Generate catalog rubric drafts, review their hashes, then freeze approved rubrics.

Without --execute every stage is an offline, read-only preflight. Draft execution
uses the unchanged screenshot-verifier rubric/dependency prompts. Review and
freeze are offline, and frozen rubrics are shared across arms and trials.
"""

from __future__ import annotations

import inspect
import hashlib

import argparse
import asyncio
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from w8bench.verifier.screenshot_verifier.clients.graceful_client import GracefulRetryClient
from w8bench.verifier.screenshot_verifier.rubric_agent import MMRubricAgent, MMRubricAgentConfig
from w8bench.verifier.screenshot_verifier.utils.action_schema import FARA_ACTION_DEFINITIONS

from .common import (
    CANONICAL_ACTION_MODEL,
    CANONICAL_JUDGE_MODEL,
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


def _usage(client: Any) -> dict[str, Any]:
    prompt = completion = 0
    records = []
    for inner in getattr(client, "_clients", []):
        usage = inner.total_usage()
        prompt += int(getattr(usage, "prompt_tokens", 0))
        completion += int(getattr(usage, "completion_tokens", 0))
        records.extend(getattr(inner, "_call_records", []))
    if records:
        inputs = [record["input_tokens"] for record in records if record.get("input_tokens") is not None]
        outputs = [record["output_tokens"] for record in records if record.get("output_tokens") is not None]
        prompt = sum(inputs) if inputs else None
        completion = sum(outputs) if outputs else None
    writes = [record["cache_write_input_tokens"] for record in records if record.get("cache_write_input_tokens") is not None]
    reads = [record["cached_input_tokens"] for record in records if record.get("cached_input_tokens") is not None]
    thinking = [record["reasoning_tokens"] for record in records if record.get("reasoning_tokens") is not None]
    return {
        "prompt_tokens": prompt, "input_tokens": prompt,
        "completion_tokens": completion, "output_tokens": completion,
        "cached_input_tokens": sum(reads) if reads else None,
        "cache_write_input_tokens": sum(writes) if writes else None,
        "reasoning_tokens": sum(thinking) if thinking else None,
        "total_tokens": (prompt or 0) + (completion or 0) if prompt is not None or completion is not None else None,
        "usage_known_calls": {key: sum(record.get("usage_fields_reported", {}).get(key, False) for record in records)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_input_tokens")},
        "cached_input_usage_reported_calls": len(reads), "reasoning_usage_reported_calls": len(thinking),
        "calls_without_reported_usage": sum(not record.get("usage_reported", False) for record in records),
        "cache_write_usage_reported_calls": len(writes),
    }


def _instrument(client: Any) -> dict[str, Any]:
    metrics = {"logical_calls": 0, "endpoint_calls": 0, "api_attempts": 0,
               "http_attempts": 0, "http_attempts_complete": False, "calls": []}
    original_create = client.create

    async def logical(*args: Any, **kwargs: Any) -> Any:
        metrics["logical_calls"] += 1
        stage_path = []
        frame = inspect.currentframe()
        try:
            while frame is not None:
                module = frame.f_globals.get("__name__", "")
                if (module.endswith(".rubric_agent") or module.endswith(".dom_model_agent")) and frame.f_code.co_name != "_call_llm":
                    stage_path.append(f"{module}.{frame.f_code.co_name}")
                frame = frame.f_back
        finally:
            del frame
        stage_tokens = [(endpoint, endpoint._logical_stage.set(tuple(stage_path)))
            for endpoint in getattr(client, "_clients", []) if hasattr(endpoint, "_logical_stage")]
        try:
            return await original_create(*args, **kwargs)
        finally:
            for endpoint, token in stage_tokens:
                endpoint._logical_stage.reset(token)
            endpoints = list(getattr(client, "_clients", []))
            attempts = sum(int(getattr(endpoint, "_http_attempts", 0)) for endpoint in endpoints)
            complete = bool(endpoints) and all(getattr(endpoint, "_http_attempts_observed", False) for endpoint in endpoints)
            records = [dict(record) for endpoint in endpoints for record in getattr(endpoint, "_call_records", [])]
            metrics.update(api_attempts=attempts, http_attempts=attempts, http_attempts_complete=complete,
                calls=records,
                configured_models=sorted({record["configured_model"] for record in records}),
                returned_models=sorted({record["returned_model"] for record in records if record.get("returned_model")}),
                endpoint_retries=max(0, metrics["endpoint_calls"] - metrics["logical_calls"]),
                sdk_http_retries=max(0, attempts - metrics["endpoint_calls"]) if complete else None)

    client.create = logical
    for endpoint in getattr(client, "_clients", []):
        original_endpoint_create = endpoint.create

        async def attempt(*args: Any, _original=original_endpoint_create, **kwargs: Any) -> Any:
            metrics["endpoint_calls"] += 1
            return await _original(*args, **kwargs)

        endpoint.create = attempt
    return metrics



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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packages = require_local_packages()
    catalog = args.catalog_file.resolve(strict=True)
    catalog_bytes = catalog.read_bytes()
    catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
    rows = parse_task_catalog(catalog_bytes.decode("utf-8"), source=str(catalog))
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
    endpoint_receipt = validate_endpoint_configs(args.eval_config)
    tasks = []
    for row in rows:
        identity = str(row["task_id"])
        if safe_task_id(identity) != identity:
            raise ValueError(f"Task ID is not a safe rubric filename: {identity!r}")
        definition = validate_task_definition(catalog_task_instruction(row), str(row.get("start_url", "")))
        tasks.append({"task_id": identity, **definition})
    preflight = {"status": "ready", "stage": args.stage, "task_count": len(tasks),
        "catalog_sha256": catalog_hash, "models": [CANONICAL_JUDGE_MODEL, CANONICAL_ACTION_MODEL],
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
        if any(frozen.glob("*.json")):
            raise ValueError("Frozen rubrics exist; choose a distinct rubric version before drafting")
        load_env_file(args.env_file)
        require_openai_key()
        workflow = {**preflight, "status": "running", "tasks": []}
        write_json(metrics_path, workflow)
        for task in tasks:
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
                continue
            receipt = {"task_binding": expected, "status": "running", "origin": "screenshot_generate_rubric",
                "attempt_history": ([*previous.get("attempt_history", []),
                    {key: value for key, value in previous.items() if key != "attempt_history"}] if previous else [])}
            write_json(receipt_path, receipt)
            clients = {}
            calls = {}
            agent = None
            try:
                for model in (CANONICAL_JUDGE_MODEL, CANONICAL_ACTION_MODEL):
                    clients[model] = GracefulRetryClient.from_path(path=args.eval_config,
                        logger=logging.getLogger("generate_frozen_rubric"), eval_model=model)
                    calls[model] = _instrument(clients[model])
                agent = MMRubricAgent(config=MMRubricAgentConfig(
                    action_client=clients[CANONICAL_ACTION_MODEL], gpt5_client=clients[CANONICAL_JUDGE_MODEL],
                    action_definitions=FARA_ACTION_DEFINITIONS, majority_vote_instances=1, redo_eval=True))
                rubric = asyncio.run(agent._generate_rubric(task["instruction"],
                    MMRubricAgent._get_init_url_context(task["start_url"])))
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
                receipt.update(call_metrics=calls, token_usage={model: _usage(client) for model, client in clients.items()},
                    rubric_generation_calls=sum(value["logical_calls"] for value in calls.values()),
                    generation_trace=getattr(agent, "rubric_generation_trace", []))
                write_json(receipt_path, receipt)
                workflow["tasks"].append({"task_id": task["task_id"], "status": receipt["status"],
                    "receipt": os.path.relpath(receipt_path, REPOSITORY_ROOT)})
                workflow["status"] = "running" if receipt["status"] == "complete" else receipt["status"]
                write_json(metrics_path, workflow)
        workflow["status"] = "complete"
        write_json(metrics_path, workflow)
        print(json.dumps(workflow, ensure_ascii=False, indent=2))
        return 0
    previous_review = json.loads(review_path.read_text()) if review_path.exists() else {}
    review = {"schema_version": "catalog-rubric-review/v1", "catalog_sha256": catalog_hash,
        "approved_by": previous_review.get("approved_by", ""),
        "approval_date": previous_review.get("approval_date", ""), "tasks": []}
    previous_tasks = {item["task_id"]: item for item in previous_review.get("tasks", [])}
    outputs = []
    for task in tasks:
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
        review["tasks"].append(entry)
        outputs.append((frozen / f"{task['task_id']}.json", payload))
    if args.stage == "review":
        if not args.execute:
            print(json.dumps({**preflight, "drafts_validated": len(tasks), "review": review},
                ensure_ascii=False, indent=2))
            return 0
        if previous_review and previous_review != review:
            archive = review_path.parent / "review_history" / f"{canonical_sha256(previous_review)}.json"
            if not archive.exists():
                write_json(archive, previous_review)
        write_json(review_path, review)
        lines = ["# Rubric review", "", f"Catalog SHA-256: `{catalog_hash}`", "",
            "Review the drafts and this checklist, then set each approved field and review notes in review.json.",
            "Set approved_by and approval_date only after approval. Freeze refuses changed task or draft hashes.", ""]
        for task, entry in zip(tasks, review["tasks"]):
            lines.extend([f"## {task['task_id']}", "", task["instruction"], "", f"Start URL: {task['start_url']}",
                f"Draft SHA-256: `{entry['draft_sha256']}`", "", "| Criterion | Description | Points |",
                "| --- | --- | --- |"])
            for item in entry["criteria"]:
                lines.append("| " + " | ".join(str(item[key]).replace("|", "\\|").replace("\n", " ")
                    for key in ("criterion", "description", "max_points")) + " |")
            lines.extend(["", "### Preparation receipt", "",
                f"Receipt: `{entry['generation_receipt']}` (SHA-256 `{entry['generation_receipt_sha256']}`).",
                f"Logical calls: {entry['generation_calls']} latest attempt; {entry['generation_calls_all_attempts']} across all attempts "
                    f"(unknown when an attempt lacks a receipt count; known lower bound {entry['generation_calls_known_lower_bound']}).",
                "Estimated USD cost: unknown; no trusted price configuration is supplied. Usage is retained per model.",
                "", "```json", json.dumps({"latest_attempt_usage": entry["generation_usage"],
                    "prior_attempt_usage": entry["prior_attempt_usage"]}, ensure_ascii=False, indent=2), "```", "",
                "### Dependency checking", "", "```json",
                json.dumps(entry["dependency_checks"], ensure_ascii=False, indent=2), "```", "",
                *[f"- [ ] {check}" for check in entry["review_checks"]], ""])
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps({"status": "review_required", "task_count": len(tasks),
            "review_file": str(review_path), "markdown": str(markdown_path)}, indent=2))
        return 0
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
        print(json.dumps({**preflight, "approved_rubrics_validated": len(tasks),
            "rubric_approval_sha256": approval_hash}, ensure_ascii=False, indent=2))
        return 0
    for path, payload in frozen_payloads:
        if not path.exists():
            write_json(path, payload)
    result = {"status": "frozen", "task_count": len(tasks), "catalog_sha256": catalog_hash,
        "rubric_approval_sha256": approval_hash, "rubrics": [
            {"task_id": payload["task_id"], "path": os.path.relpath(path, REPOSITORY_ROOT),
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
             "rubric_sha256": canonical_sha256(payload["precomputed_rubric"])} for path, payload in frozen_payloads]}
    write_json(metrics_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
