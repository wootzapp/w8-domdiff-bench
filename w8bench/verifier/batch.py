"""Durable judge requests, provider batch jobs and response replay."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

import httpx
from .common import canonical_sha256 as _digest

POLICY_VERSION = "judge-batch/v1"
_occurrences = defaultdict(int)


class BatchPending(BaseException):
    """Suspend evaluation without spending a validator or retry attempt."""


class BatchCancelled(BaseException):
    """A cancelled evaluation cannot import responses or write grades."""


def judge_transport():
    value = os.environ.get("JUDGE_TRANSPORT", "batch").strip().lower()
    if value not in {"normal", "batch"}:
        raise ValueError("JUDGE_TRANSPORT must be batch or normal")
    return value


def _save(path, value):
    """Publish complete receipts atomically and durably."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, encoding="utf-8") as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def publication(root=None):
    """Serialize result publication against a collection's cancellation marker."""
    value = str(root) if root is not None else os.environ.get("W8_JUDGE_BATCH_ROOT")
    if not value or root is None and judge_transport() == "normal":
        yield
        return
    root = Path(value)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "publish.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        try:
            if (root / "cancelled.json").exists():
                raise BatchCancelled()
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


@contextmanager
def evaluation_scope(root, identity):
    names = ("W8_JUDGE_BATCH_ROOT", "W8_JUDGE_RUN_ID", "W8_JUDGE_STAGE_ATTEMPT")
    previous = {name: os.environ.get(name) for name in names}
    os.environ.update(W8_JUDGE_BATCH_ROOT=str(Path(root).resolve()), W8_JUDGE_RUN_ID=json.dumps(identity, sort_keys=True))
    os.environ.pop("W8_JUDGE_STAGE_ATTEMPT", None)
    _occurrences.clear()
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def request(body, *, provider, endpoint, stage, model=None, record=None):
    """Return a saved wire response, or queue the unchanged request body."""
    root_value = os.environ.get("W8_JUDGE_BATCH_ROOT")
    identity_value = os.environ.get("W8_JUDGE_RUN_ID")
    if not root_value or not identity_value:
        raise ValueError("Batch judging requires the evaluation command and its durable request directory")
    root = Path(root_value)
    if (root / "cancelled.json").exists():
        raise BatchCancelled()
    identity = json.loads(identity_value)
    if stage.startswith("completion."):
        identity = {**identity, "profile": "common"}
    fingerprint = _digest(body)
    generation = os.environ.get("W8_JUDGE_STAGE_ATTEMPT", "1")
    namespace = _digest({"run": identity, "stage": stage, "generation": generation})[:16]
    counter_key = (str(root), namespace, fingerprint)
    _occurrences[counter_key] += 1
    attempt = _occurrences[counter_key]
    key = f"r{namespace}_c{fingerprint[:24]}_a{attempt}"
    item = {"id": key, "run": identity, "stage": stage, "call_index": fingerprint,
        "attempt": attempt, "evaluation_attempt": generation, "provider": provider,
        "endpoint": endpoint, "model": model or body.get("model"), "body": body,
        "body_sha256": fingerprint, "transport": "batch", "policy_version": POLICY_VERSION}
    path = root / "requests" / f"{key}.json"
    if path.exists():
        if json.loads(path.read_text()) != item:
            raise ValueError("Saved batch request identity or body changed")
    else:
        with publication(root):
            _save(path, item)
    answer = root / "responses" / f"{key}.json"
    if not answer.exists():
        raise BatchPending(key)
    value = json.loads(answer.read_text())
    if record is not None:
        record.update(transport="batch", batch_request_id=key, batch_job_id=value["job_id"],
            batch_policy_version=POLICY_VERSION, batch_evaluation_attempt=generation)
        usage = value["body"].get("usage")
        if "usageMetadata" in value["body"]:
            from .audit_requests import _record_gemini_response
            normalized = {}
            _record_gemini_response(normalized, value["body"], {})
            usage = normalized["usage"]
        record.setdefault("batch_items", []).append({"batch_request_id": key, "batch_job_id": value["job_id"],
            "model": item["model"], "usage": usage, "transport": "batch", "status_code": value["status_code"],
            "returned_model": value["body"].get("modelVersion", value["body"].get("model")),
            "submitted_at": value.get("submitted_at"), "completed_at": value.get("completed_at")})
    return value


def http_transport(provider, stage, record):
    """Intercept the SDK's serialized request without changing its body."""
    def handle(wire):
        endpoint = "/v1/chat/completions"
        model = None
        if ":generateContent" in wire.url.path:
            endpoint = "generateContent"
            model = wire.url.path.split("/models/", 1)[1].split(":", 1)[0]
        value = request(json.loads(wire.content), provider=provider, endpoint=endpoint,
            model=model, stage=stage, record=record)
        return httpx.Response(value["status_code"], json=value["body"], request=wire)
    return httpx.MockTransport(handle)


class BatchJobs:
    """Submit each durable request once and import terminal item responses."""

    def __init__(self, root, *, clients=None):
        self.root = Path(root)
        self.clients = clients or {}

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def _client(self, provider, native=False):
        key = (provider, native)
        if key not in self.clients:
            if provider == "google" and native:
                from google import genai
                self.clients[key] = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"retry_options": {"attempts": 1}})
            else:
                from openai import OpenAI
                self.clients[key] = OpenAI(api_key=os.environ["GEMINI_API_KEY" if provider == "google" else "OPENAI_API_KEY"],
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/" if provider == "google"
                        else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), max_retries=0)
        return self.clients[key]

    def submit(self):
        if (self.root / "cancelled.json").exists():
            raise BatchCancelled()
        jobs = [json.loads(p.read_text()) for p in sorted((self.root / "jobs").glob("*.json"))]
        if any(row["status"] == "submission_uncertain" and not row.get("job_id") for row in jobs):
            raise RuntimeError("Batch submission acknowledgement is uncertain; reconcile its provider job ID before resume. No resubmission was made.")
        assigned = {key for job in jobs if job["status"] not in {"upload_abandoned", "creation_rejected"} for key in job["request_ids"]}
        groups = defaultdict(list)
        for path in sorted((self.root / "requests").glob("*.json")):
            row = json.loads(path.read_text())
            if row["id"] not in assigned and not (self.root / "responses" / f"{row['id']}.json").exists():
                groups[(row["provider"], row["endpoint"], row["model"], row["stage"])].append(path)
        submitted = 0
        for (provider, endpoint, model, stage), rows in groups.items():
            chunk, size = [], 0
            limit = 2_000_000_000 if provider == "google" else 200_000_000
            with tempfile.TemporaryFile() as stream:
                for path in rows:
                    row = json.loads(path.read_text())
                    envelope = ({"key": row["id"], "request": row["body"]} if endpoint == "generateContent" else
                        {"custom_id": row["id"], "method": "POST", "url": endpoint, "body": row["body"]})
                    line = (json.dumps(envelope, ensure_ascii=True) + "\n").encode()
                    if len(line) > limit:
                        raise ValueError("One unchanged judge request exceeds the provider Batch file limit; use normal transport for this stage")
                    if chunk and (size + len(line) > limit or provider == "openai" and len(chunk) >= 50000):
                        stream.seek(0)
                        self._submit_job(provider, endpoint, model, stage, chunk, stream)
                        submitted += 1
                        stream.seek(0)
                        stream.truncate()
                        chunk, size = [], 0
                    stream.write(line)
                    chunk.append(row["id"])
                    size += len(line)
                if chunk:
                    stream.seek(0)
                    self._submit_job(provider, endpoint, model, stage, chunk, stream)
                    submitted += 1
        return submitted

    def _submit_job(self, provider, endpoint, model, stage, keys, content):
        number = max((int(p.stem.split("_")[-1]) for p in (self.root / "jobs").glob("job_*.json")), default=0) + 1
        while (self.root / "inputs" / f"job_{number:06d}.jsonl").exists():
            number += 1
        path = self.root / "jobs" / f"job_{number:06d}.json"
        input_path = self.root / "inputs" / f"job_{number:06d}.jsonl"
        input_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with input_path.open("xb") as destination:
            for piece in iter(lambda: content.read(1024 * 1024), b""):
                destination.write(piece)
                digest.update(piece)
            destination.flush()
            os.fsync(destination.fileno())
        job = {"provider": provider, "endpoint": endpoint, "model": model, "stage": stage,
            "request_ids": keys, "input_sha256": digest.hexdigest(), "transport": "batch",
            "status": "uploading", "job_id": None, "created_at": datetime.now(timezone.utc).isoformat()}
        _save(path, job)
        if provider == "google":
            client = self._client(provider, True)
            uploaded = client.files.upload(file=str(input_path), config={"mime_type": "application/jsonl"})
            file_id = uploaded.name
        else:
            with input_path.open("rb") as stream:
                file_id = self._client(provider).files.create(file=stream, purpose="batch").id
        job.update(input_file_id=file_id, status="submission_uncertain")
        _save(path, job)
        # Creation is deliberately never retried. An uncertain receipt blocks
        # resume until its actual provider ID has been reconciled.
        try:
            if endpoint == "generateContent":
                result = self._client(provider, True).batches.create(model=model, src=file_id,
                    config={"display_name": f"w8-{input_path.stem}"})
                job_id = result.name
            else:
                result = self._client(provider).batches.create(input_file_id=file_id, endpoint=endpoint, completion_window="24h")
                job_id = result.id
        except Exception as error:
            code = getattr(error, "status_code", None) or getattr(error, "code", None)
            if type(code) is int and 400 <= code < 500:
                job.update(status="creation_rejected", creation_status_code=code, error_type=type(error).__name__)
                _save(path, job)
            raise
        if not isinstance(job_id, str) or not job_id.strip():
            raise RuntimeError("Batch creation returned no job ID; reconcile before resubmitting")
        job.update(job_id=job_id, status="submitted", submitted_at=datetime.now(timezone.utc).isoformat())
        _save(path, job)

    def poll(self):
        if (self.root / "cancelled.json").exists():
            raise BatchCancelled()
        active = 0
        for path in sorted((self.root / "jobs").glob("*.json")):
            job = json.loads(path.read_text())
            if job["status"] in {"completed", "failed", "expired", "cancelled", "upload_abandoned", "creation_rejected"}:
                continue
            if not job.get("job_id"):
                if job["status"] == "uploading":
                    # No creation was attempted; an orphan upload is not a model call.
                    job.update(status="upload_abandoned")
                    _save(path, job)
                    continue
                raise RuntimeError("Uncertain batch submission requires provider job-ID reconciliation; refusing to resubmit")
            native = job["endpoint"] == "generateContent"
            client = self._client(job["provider"], native)
            response = client.batches.get(name=job["job_id"]) if native else client.batches.retrieve(job["job_id"])
            data = response.model_dump(mode="json", exclude_none=True) if hasattr(response, "model_dump") else response
            reported_input = data.get("src", {}).get("file_name") if native else data.get("input_file_id")
            if reported_input is not None and reported_input != job["input_file_id"]:
                raise ValueError("Provider batch input file differs from its saved submission")
            if job["status"] == "submission_uncertain":
                job["status"] = "submitted"
            state = data.get("state", data.get("status"))
            state = {"JOB_STATE_SUCCEEDED": "completed", "JOB_STATE_FAILED": "failed", "JOB_STATE_EXPIRED": "expired",
                "JOB_STATE_CANCELLED": "cancelled"}.get(state, state)
            if state not in {"completed", "failed", "expired", "cancelled"}:
                job.update(provider_status=state)
                _save(path, job)
                active += 1
                continue
            output_ids = ([data.get("dest", {}).get("file_name")] if native else
                [data.get("output_file_id"), data.get("error_file_id")])
            imported = set()
            for file_id in filter(None, output_ids):
                if job["provider"] == "google":
                    raw = self._client("google", True).files.download(file=file_id)
                else:
                    raw = client.files.content(file_id).content
                for line in raw.decode().splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    key = row.get("key", row.get("custom_id"))
                    if key not in job["request_ids"] or key in imported:
                        raise ValueError("Batch output has an unknown or duplicate request ID")
                    imported.add(key)
                    result = row.get("response") or {}
                    body = result if native else result.get("body")
                    status = 200 if native and not row.get("error") else result.get("status_code", 503)
                    if row.get("error"):
                        error = row["error"]
                        code = error.get("code") if isinstance(error, dict) else None
                        if isinstance(code, int):
                            status = code if 400 <= code <= 599 else {3: 400, 4: 504, 5: 404, 7: 403,
                                8: 429, 9: 400, 13: 500, 14: 503, 16: 401}.get(code, 500)
                        else:
                            status = {"invalid_request_error": 400, "invalid_prompt": 400,
                                "rate_limit_exceeded": 429, "authentication_error": 401}.get(code, 503)
                        body = {"error": error}
                    self._answer(key, job, status, body or {"error": {"message": "Batch item unavailable"}})
            for key in set(job["request_ids"]) - imported:
                self._answer(key, job, 503, {"error": {"code": f"batch_{state}",
                    "message": f"Batch item has no response after job {state}; retry through the existing request budget"}})
            job.update(status=state, provider_status=state, response_file_ids=list(filter(None, output_ids)))
            _save(path, job)
        return active

    def _answer(self, key, job, status, body):
        if (self.root / "cancelled.json").exists():
            raise BatchCancelled()
        path = self.root / "responses" / f"{key}.json"
        value = {"job_id": job["job_id"], "status_code": status, "body": body, "transport": "batch",
            "submitted_at": job.get("submitted_at"), "completed_at": datetime.now(timezone.utc).isoformat()}
        if path.exists():
            previous = json.loads(path.read_text())
            if any(previous.get(key) != value.get(key) for key in ("job_id", "status_code", "body", "transport")):
                raise ValueError("Batch response changed for an answered request")
            return
        with publication(self.root):
            _save(path, value)

    def records(self, identity, stage_prefix, evaluation_attempt):
        """Read known and unknown current-attempt spending without replaying calls."""
        records = []
        for path in sorted((self.root / "jobs").glob("*.json")):
            job = json.loads(path.read_text())
            if not job["stage"].startswith(stage_prefix) or job["status"] in {"uploading", "upload_abandoned"}:
                continue
            namespace = _digest({"run": identity, "stage": job["stage"], "generation": str(evaluation_attempt)})[:16]
            for key in job["request_ids"]:
                if not key.startswith(f"r{namespace}_"):
                    continue
                response = self.root / "responses" / f"{key}.json"
                value = json.loads(response.read_text()) if response.exists() else {}
                body = value.get("body") or {}
                usage = body.get("usage")
                if "usageMetadata" in body:
                    from .audit_requests import _record_gemini_response
                    normalized = {}
                    _record_gemini_response(normalized, body, {})
                    usage = normalized["usage"]
                records.append({"batch_request_id": key, "batch_job_id": job.get("job_id"),
                    "model": job["model"], "returned_model": body.get("modelVersion", body.get("model")),
                    "stage": job["stage"], "transport": "batch", "usage": usage,
                    "status": "answered" if value else "submission_uncertain" if not job.get("job_id") else "submitted"})
        return records

    def cancel(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "publish.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                _save(self.root / "cancelled.json", {"status": "cancelled", "no_late_writes": True})
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
        errors = []
        for path in sorted((self.root / "jobs").glob("*.json")):
            job = json.loads(path.read_text())
            if job["status"] == "submission_uncertain":
                errors.append({"job_id": None, "reason": "submission_uncertain_requires_provider_reconciliation"})
            if job.get("job_id") and job["status"] not in {"completed", "failed", "expired", "cancelled"}:
                try:
                    if job["provider"] == "google":
                        self._client(job["provider"], True).batches.cancel(name=job["job_id"])
                    else:
                        self._client(job["provider"]).batches.cancel(job["job_id"])
                except Exception as error:
                    errors.append({"job_id": job["job_id"], "error_type": type(error).__name__})
        _save(self.root / "cancellation_receipt.json", {"errors": errors, "late_results_ignored": True})
        return errors


def compare_profiles(runs, output):
    """Compare separately bound native judgments without pairing run evidence."""
    from w8bench.task_recorder.prepare_verifier_data import inspect_recording
    from .run_metrics import _price_stream, _evaluation_streams
    rows, unavailable, evaluation_costs, profile_runs = [], [], [], []
    for run in runs:
        recording = inspect_recording(run)
        task = recording["task"]
        suffix = Path(str(task.get("run_name") or recording["manifest"]["run_name"])) / task["observation_mode"] / task["source_task_id"] / recording["recording_sha256"]
        base = run.parent.parent / "evaluations"
        roots = {"primary": base / "profiles" / "primary" / suffix, "pro": base / "profiles" / "pro" / suffix}
        evaluations = {profile: json.loads((root / "evaluation.json").read_text()) for profile, root in roots.items()}
        bindings = {(value["recording_sha256"], value["rubric_sha256"], value["task_id"], value["actor_arm"], value["trial_id"])
            for value in evaluations.values()}
        if len(bindings) != 1 or next(iter(bindings))[0] != recording["recording_sha256"]:
            raise ValueError("Judge profiles are not bound to the same recording and rubric")
        audits = {profile: json.loads((root / "evidence_audit.json").read_text())
            if evaluations[profile]["stages"].get("audit", {}).get("status") == "complete" else None for profile, root in roots.items()}
        profile_costs = {}
        for profile, value in evaluations.items():
            for mode in ("screenshot_verifier", "dom_model"):
                expected = "gemini-3.5-flash-lite" if profile == "primary" else "gemini-3.1-pro-preview"
                if value["effective_settings"]["stages"][mode]["models"] != [expected, expected]:
                    raise ValueError("Native model profile does not match its output location")
            grade_path = roots[profile] / "paired_completion.json"
            grade = json.loads(grade_path.read_text()) if grade_path.exists() else None
            streams, _ = _evaluation_streams(value["stages"], value, roots[profile] / "evaluation.json", grade, None)
            for stream in streams.values():
                _price_stream(stream)
            native_stages = {mode: value["stages"].get(mode, {})
                for mode in ("screenshot_verifier", "dom_model")}
            native_repairs = sum(attempt.get("validation_repair_events", 0)
                for stage in native_stages.values() for attempt in [*stage.get("attempt_history", []), stage])
            audit_stage = value["stages"].get("audit", {})
            audit_repairs = sum(max(0, sum(call.get("stage") == part for call in attempt.get("calls", [])) - 1)
                for attempt in [*audit_stage.get("attempt_history", []), audit_stage]
                for part in ("inventory", "adjudication"))
            calls = [call for name, stream in streams.items()
                if name not in {"paired_completion", "actor_native_completion", "rubric_import"}
                for call in stream.get("call_records", [])]
            losses_available = audits[profile] is not None and all(
                isinstance(audits[profile].get("metrics", {}).get(key, {}).get("rate"), (int, float))
                and not isinstance(audits[profile]["metrics"][key]["rate"], bool)
                for key in ("screenshot_evidence_loss", "dom_model_evidence_loss"))
            profile_runs.append({"profile": profile, "task_id": task["source_task_id"],
                "arm": task["observation_mode"], "trial": task.get("run_name"),
                "recording_sha256": recording["recording_sha256"],
                "native_statuses": {mode: stage.get("status", "missing") for mode, stage in native_stages.items()},
                "ungraded_native_results": [mode for mode, stage in native_stages.items() if stage.get("status") != "complete"],
                "repair_attempts": native_repairs + audit_repairs,
                "native_validation_repair_events": native_repairs, "audit_repair_attempts": audit_repairs,
                "refusals": sum(bool(call.get("refusal_reason")) or call.get("error_type") == "ModelResponseRefusal" for call in calls),
                "audit_blocked_by_unavailable_native": audit_stage.get("reason") == "verifier_results_unavailable",
                "loss_values_available": losses_available, "audit_status": audit_stage.get("status", "missing")})
            profile_costs[profile] = {name: {"cost": stream["cost"], "usage": stream.get("usage"), "calls": stream.get("calls")}
                for name, stream in streams.items() if name not in {"paired_completion", "actor_native_completion", "rubric_import"}}
        evaluation_costs.append({"task_id": task["source_task_id"], "arm": task["observation_mode"],
            "trial": task.get("run_name"), "recording_sha256": recording["recording_sha256"], "profiles": profile_costs,
            "shared_completion": "One common completion grade, charged once under the primary evaluation."})
        screenshot_only = {profile: None if audit is None else {
            item["criterion_index"] for item in audit.get("criteria", [])
            if item["screenshot"]["coverage"] == "COMPLETE" and item["dom_model"]["coverage"] != "COMPLETE"
            and item["dom_model_evidence_loss"]} for profile, audit in audits.items()}
        both_available = all(value is not None for value in screenshot_only.values())
        screenshot_only.update(union=screenshot_only["primary"] | screenshot_only["pro"] if both_available else None,
            intersection=screenshot_only["primary"] & screenshot_only["pro"] if both_available else None)
        for mode in ("screenshot_verifier", "dom_model"):
            stages = {profile: value["stages"].get(mode, {}) for profile, value in evaluations.items()}
            if any(value.get("status") != "complete" for value in stages.values()):
                unavailable.append({"task_id": task["source_task_id"], "arm": task["observation_mode"],
                    "trial": task.get("run_name"), "format": mode, "reason": "native_profile_ungraded"})
                continue
            criteria = {profile: value["criteria"] for profile, value in stages.items()}
            if len(criteria["primary"]) != len(criteria["pro"]):
                raise ValueError("Native profile criterion lists differ")
            details = []
            costs = {}
            for profile, root in roots.items():
                metrics = json.loads((root / mode / "run_metrics.json").read_text())
                calls = [call for value in metrics["provider_call_metrics"].values() for call in value.get("calls", [])]
                stream = {"calls": metrics["llm_calls"].get("total"), "call_records": calls, "usage_coverage": "complete"}
                _price_stream(stream)
                costs[profile] = {"cost": stream["cost"], "tokens": metrics["token_usage"], "calls": metrics["llm_calls"].get("total")}
            for index, (a, b) in enumerate(zip(criteria["primary"], criteria["pro"])):
                if (a["criterion"], a["max_points"]) != (b["criterion"], b["max_points"]):
                    raise ValueError("Native profile frozen criterion identity differs")
                details.append({"criterion_index": index, "criterion": a["criterion"], "primary_points": a["final_points"],
                    "pro_points": b["final_points"], "agrees": a["final_points"] == b["final_points"],
                    "screenshot_only_evidence": {name: None if indices is None else index in indices
                        for name, indices in screenshot_only.items()}})
            subsets = {}
            for name, indices in screenshot_only.items():
                only = [item for item in details if indices is not None and item["criterion_index"] in indices]
                subsets[name] = {"available": indices is not None,
                    "criterion_indices": sorted(indices) if indices is not None else None,
                    "criteria": len(only) if indices is not None else None,
                    "agreements": sum(item["agrees"] for item in only) if indices is not None else None,
                    "agreement": sum(item["agrees"] for item in only) / len(only) if only else None}
            losses = {profile: None if audit is None else {key: audit["metrics"][key]
                for key in ("screenshot_evidence_loss", "dom_model_evidence_loss")} for profile, audit in audits.items()}
            loss_differences = {key: None if any(value is None for value in losses.values()) else
                losses["primary"][key]["rate"] - losses["pro"][key]["rate"]
                for key in ("screenshot_evidence_loss", "dom_model_evidence_loss")}
            rows.append({"task_id": task["source_task_id"], "arm": task["observation_mode"], "trial": task.get("run_name"),
                "recording_sha256": recording["recording_sha256"], "format": mode,
                "criteria": details, "agreement": sum(item["agrees"] for item in details) / len(details),
                "disagreements": [item for item in details if not item["agrees"]],
                "screenshot_only_subsets": subsets, "losses": losses, "loss_rate_difference_primary_minus_pro": loss_differences,
                "completion_effect": "none; the common completion judge has no native-verifier input and its grade is reused",
                "usage_and_cost": costs})
    quality = {}
    for profile in ("primary", "pro"):
        selected = [row for row in profile_runs if row["profile"] == profile]
        quality[profile] = {"runs": len(selected),
            "ungraded_native_results": sum(len(row["ungraded_native_results"]) for row in selected),
            "repair_attempts": sum(row["repair_attempts"] for row in selected),
            "native_validation_repair_events": sum(row["native_validation_repair_events"] for row in selected),
            "audit_repair_attempts": sum(row["audit_repair_attempts"] for row in selected),
            "refusals": sum(row["refusals"] for row in selected),
            "audits_blocked_by_unavailable_native": sum(row["audit_blocked_by_unavailable_native"] for row in selected),
            "runs_without_loss_values": sum(not row["loss_values_available"] for row in selected),
            "by_arm": {arm: {"runs": sum(row["arm"] == arm for row in selected),
                "ungraded_native_results": sum(len(row["ungraded_native_results"]) for row in selected if row["arm"] == arm),
                "repair_attempts": sum(row["repair_attempts"] for row in selected if row["arm"] == arm),
                "refusals": sum(row["refusals"] for row in selected if row["arm"] == arm),
                "audits_blocked_by_unavailable_native": sum(row["audit_blocked_by_unavailable_native"] for row in selected if row["arm"] == arm),
                "runs_without_loss_values": sum(not row["loss_values_available"] for row in selected if row["arm"] == arm)}
                for arm in ("dom", "screenshot")}}
    report = {"schema_version": "native-profile-comparison/v2", "profiles": {
        "primary": "gemini-3.5-flash-lite", "pro": "gemini-3.1-pro-preview"}, "rows": rows, "unavailable": unavailable, "evaluation_costs": evaluation_costs,
        "screenshot_only_subset": "Each profile's own same-run audit: screenshot COMPLETE, DOM PARTIAL or ABSENT, adjudicated DOM loss; report both subsets, their union and intersection. Judge-defined, not human ground truth. Missing audits give unavailable subsets, not empty ones.",
        "profile_quality": quality, "profile_runs": profile_runs,
        "quality_scope": "Native and audit stages, including recorded prior attempts; shared completion excluded. Repair counts combine observed native validation-repair log events and audit calls beyond the first per stage/attempt. Refusals require an explicit refusal receipt; absence of such a receipt is not proof that none occurred. Categories overlap.",
        "pairing": "Each audit uses only one recording's own formats; the four arm/direction values are reported under their driving arm."}
    output = Path(output)
    number = 2
    target = output
    while target.exists():
        target = output.with_name(f"{output.stem}_{number}{output.suffix}")
        number += 1
    report["output"] = str(target)
    _save(target, report)
    return report


def main(argv=None):
    """Inspect or execute the explicitly gated synthetic provider smoke test."""
    import argparse
    from w8bench.task_recorder.runner import load_env
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("command", choices=("smoke",))
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/judge_batch_smoke"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--execute", action="store_true", help="submit or poll synthetic paid batches only after approval")
    parser.add_argument("--cancel", action="store_true", help="cancel outstanding smoke batches; requires --execute")
    args = parser.parse_args(argv)
    load_env(args.env_file)
    image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg=="
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
    messages = [{"role": "user", "content": [{"type": "text", "text": 'Return only {"ok":true}.'},
        {"type": "image_url", "image_url": {"url": image, "detail": "high"}}]}]
    cases = [
        ("google", "generateContent", "gemini-3.6-flash", "completion", {
            "contents": [{"role": "user", "parts": [{"text": 'Return only {"ok":true}.'},
                {"inlineData": {"mimeType": "image/png", "data": image.split(",", 1)[1]}}]}],
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "MEDIUM"}, "maxOutputTokens": 10000,
                "mediaResolution": "MEDIA_RESOLUTION_HIGH", "responseMimeType": "application/json", "responseJsonSchema": schema}}),
        ("openai", "/v1/chat/completions", "gpt-6.1-sol", "adjudication", {"model": "gpt-6.1-sol", "messages": messages,
            "response_format": {"type": "json_object"}}),
        ("google", "/v1/chat/completions", "gemini-3.5-flash-lite", "native_primary", {"model": "gemini-3.5-flash-lite",
            "messages": messages, "reasoning_effort": "medium", "response_format": {"type": "json_object"}}),
        ("google", "/v1/chat/completions", "gemini-3.1-pro-preview", "native_pro", {"model": "gemini-3.1-pro-preview",
            "messages": messages, "reasoning_effort": "medium", "response_format": {"type": "json_object"}}),
        ("google", "generateContent", "gemini-3.1-pro-preview", "inventory", {"contents": [{"role": "user", "parts": [
            {"text": 'Return only {"ok":true}.'}, {"inlineData": {"mimeType": "image/png", "data": image.split(",", 1)[1]}}]}],
            "generationConfig": {"responseMimeType": "application/json", "mediaResolution": "MEDIA_RESOLUTION_HIGH"}}),
    ]
    if not args.execute:
        print(json.dumps({"status": "offline_preflight", "model_calls": 0, "writes_performed": False,
            "generation_requests_if_approved": {"google": 4, "openai": 1},
            "approval_required": True, "cases": [{"provider": p, "endpoint": e, "model": m, "stage": stage, "body": body}
                for p, e, m, stage, body in cases]}, indent=2))
        return 0
    jobs = BatchJobs(args.output_dir)
    with jobs.locked():
        if args.cancel:
            jobs.cancel()
            return 130
        jobs.poll()
        pending, results = False, []
        from w8bench.model_identity import response_acceptance
        with evaluation_scope(args.output_dir, {"synthetic_smoke": POLICY_VERSION}):
            for provider, endpoint, model, stage, body in cases:
                record = {}
                try:
                    result = request(body, provider=provider, endpoint=endpoint, stage=stage, model=model, record=record)
                except BatchPending:
                    pending = True
                    continue
                raw = result["body"]
                returned = raw.get("modelVersion", raw.get("model"))
                if endpoint == "generateContent":
                    from .audit_requests import _record_gemini_response
                    content = _record_gemini_response(record, raw, {})
                    acceptance_input = record
                elif endpoint == "/v1/chat/completions":
                    choices = raw.get("choices") or []
                    content = (choices[0].get("message") or {}).get("content") if len(choices) == 1 else None
                    acceptance_input = {"incomplete": len(choices) != 1 or
                        (choices[0].get("finish_reason") or choices[0].get("finishReason")) != "stop"}
                else:
                    from w8bench.task_recorder.runner import response_text
                    content, acceptance_input = response_text(raw), raw
                acceptance = response_acceptance(model, returned, acceptance_input)
                valid = result["status_code"] == 200 and acceptance["accepted"] and json.loads(content or "null") == {"ok": True}
                results.append({"provider": provider, "stage": stage, "configured_model": model, "returned_model": returned,
                    "accepted": valid, "acceptance": acceptance, "receipt": record})
        jobs.submit()
        _save(args.output_dir / "smoke.json", {"pending": pending, "results": results})
        print(json.dumps({"pending": pending, "results": results}, indent=2))
        return 75 if pending else 0 if all(row["accepted"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
