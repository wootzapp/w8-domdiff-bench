from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .agent import StagehandVerifier
from .llm import OpenAIJsonJudge
from .runner import load_task_data, preflight_tasks, run_prepared
from .schemas import VerifierConfig
from .usage import UsageLedger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Stagehand semantic trajectories without screenshots"
    )
    parser.add_argument("--input", required=True, help="One task or a directory of tasks")
    parser.add_argument("--task-data", help="Optional JSON task-data file")
    parser.add_argument("--task-data-format", default="json", choices=["json"])
    parser.add_argument("--eval-config", help="OpenAI endpoint JSON (read after preflight)")
    parser.add_argument("--judge-model", default="gpt-5.2")
    parser.add_argument("--o4mini-model", default="o4-mini")
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--output", help="Optional result root; default is each task folder")
    parser.add_argument("--report", help="Run JSONL report path")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--redo-eval", action="store_true")
    parser.add_argument("--rubric-threshold", type=float, default=0.8)
    parser.add_argument("--max-evidence-per-criterion", type=int, default=5)
    parser.add_argument("--min-relevance-score", type=float, default=1.0)
    parser.add_argument("--majority-vote-instances", type=int, default=1)
    parser.add_argument("--success-criterion", choices=["process", "outcome", "both"], default="outcome")
    return parser.parse_args(argv)


def _read_endpoint(path: str | None) -> dict[str, Any]:
    if path is None:
        return {"provider": "openai", "api_key_env": "OPENAI_API_KEY"}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Endpoint configuration must be a JSON object")
    provider = str(payload.get("provider") or payload.get("CHAT_COMPLETION_PROVIDER") or "openai")
    if provider.casefold() != "openai":
        raise ValueError("Only the OpenAI provider is supported")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.judge_model == args.o4mini_model:
        raise ValueError("Judge and action/rubric roles must use distinct models")
    if args.processes != 1:
        raise ValueError("This deterministic reference runner currently requires --processes 1")

    # Required ordering: all dataset and rubric validation completes before any
    # endpoint configuration is read or any paid client is constructed.
    task_data = load_task_data(args.task_data)
    prepared = preflight_tasks(args.input, task_data)
    if args.preflight_only:
        print(json.dumps([item.preflight.to_dict() for item in prepared], indent=2))
        return 0

    endpoint = _read_endpoint(args.eval_config)
    timeout = float(endpoint.get("timeout_seconds") or 180)
    retries = int(endpoint.get("max_retries") or 5)
    config = VerifierConfig(
        judge_model=args.judge_model,
        action_rubric_model=args.o4mini_model,
        rubric_threshold=args.rubric_threshold,
        max_evidence_per_criterion=args.max_evidence_per_criterion,
        min_relevance_score=args.min_relevance_score,
        majority_vote_instances=args.majority_vote_instances,
        success_criterion=args.success_criterion,
        max_retries=retries,
        timeout_seconds=timeout,
        redo_eval=args.redo_eval,
    )
    ledger = UsageLedger()
    judge = OpenAIJsonJudge.from_config(
        endpoint,
        ledger,
        max_retries=config.max_retries,
        timeout_seconds=config.timeout_seconds,
    )
    verifier = StagehandVerifier(judge, config=config, usage=ledger)
    input_root = Path(args.input).resolve()
    output_root = Path(args.output).resolve() if args.output else None
    report = (
        Path(args.report).resolve()
        if args.report
        else (output_root or input_root) / "verify_report_stagehand.jsonl"
    )
    results = run_prepared(prepared, verifier, output_root=output_root, report_path=report)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

