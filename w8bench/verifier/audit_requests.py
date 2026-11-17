"""Audit prompts, provider requests and bounded response validation."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

import httpx
from openai import APIConnectionError, DefaultHttpxClient, OpenAI

from w8bench.model_identity import MODEL_ACCEPTANCE_POLICY, ModelResponseRefusal, response_acceptance
from w8bench.usage import known_token_component

from .audit_evidence import ordered_audit_screenshots, ordered_dom_states, verifier_action_history
from .audit_validation import CITATION_KEYS, validate_audit_response, validate_adjudication_response



GEMINI_API_VERSION = "v1beta"


OPENAI_GENERATION_SETTINGS = {"response_format": {"type": "json_object"}}


GEMINI_GENERATION_SETTINGS = {
    "response_mime_type": "application/json",
    "media_resolution": "MEDIA_RESOLUTION_HIGH",
}


def resolve_provider(model: str, provider: str | None = None) -> str:
    if not isinstance(model, str) or not model.strip():
        raise ValueError("A model ID is required")
    if model.endswith("-latest"):
        raise ValueError("Use an exact model ID, not a -latest alias")
    if provider:
        if provider not in {"openai", "google"}:
            raise ValueError("Provider must be openai or google")
        return provider
    name = model.removeprefix("models/")
    if name.startswith("gemini-"):
        return "google"
    if name.startswith("gpt-") or re.match(r"^o\d", name):
        return "openai"
    raise ValueError("Cannot infer provider; set EVIDENCE_AUDIT_PROVIDER or EVIDENCE_ADJUDICATOR_PROVIDER, or the matching CLI provider flag")


def resolve_audit_config(model=None, adjudicator_model=None, audit_provider=None, adjudicator_provider=None) -> dict:
    config = {}
    for stage, selected, explicit, model_env, provider_env in (
        ("inventory", model, audit_provider, "EVIDENCE_AUDIT_MODEL", "EVIDENCE_AUDIT_PROVIDER"),
        ("adjudication", adjudicator_model, adjudicator_provider, "EVIDENCE_ADJUDICATOR_MODEL", "EVIDENCE_ADJUDICATOR_PROVIDER"),
    ):
        name = (selected if selected is not None else os.environ.get(model_env, "")).strip()
        if not name:
            raise ValueError(f"Set {model_env} or its CLI model flag before running an audit")
        provider = explicit if explicit is not None else os.environ.get(provider_env, "").strip()
        config[stage] = {"model": name, "provider": resolve_provider(name, provider or None)}
    return config


def _transport_request(call, record: dict):
    attempts = record.setdefault("transport_attempts", [])
    for attempt in range(1, 4):
        receipt = {"attempt": attempt, "started_at": datetime.now(timezone.utc).isoformat()}
        attempts.append(receipt)
        started = time.perf_counter()
        try:
            result = call()
            receipt.update(status="accepted", retryable=False, will_retry=False, backoff_seconds=0)
            return result
        except Exception as error:
            code = getattr(error, "status_code", None) or getattr(error, "code", None)
            retryable = isinstance(error, (APIConnectionError, httpx.TransportError, ConnectionError, TimeoutError)) or (
                isinstance(code, int) and (code == 429 or 500 <= code <= 599))
            message = str(error)
            for key, value in os.environ.items():
                if key.endswith("API_KEY") and value:
                    message = message.replace(value, "[REDACTED]")
            retry = retryable and attempt < 3
            delay = 2 ** (attempt - 1) if retry else 0
            receipt.update(status="error", status_code=code if isinstance(code, int) else None,
                           error_type=type(error).__name__, error=message, retryable=retryable,
                           will_retry=retry, backoff_seconds=delay)
            if not retry:
                raise
            time.sleep(delay)
        finally:
            receipt["duration_seconds"] = time.perf_counter() - started


def check_audit_models(config: dict, *, records: list | None = None) -> dict:
    checks = {}
    listings = {}
    for stage, selected in config.items():
        provider, model = selected["provider"], selected["model"]
        if provider not in listings:
            record = {"provider": provider, "requested_at": datetime.now(timezone.utc).isoformat()}
            if records is not None:
                records.append(record)
            if provider == "google":
                from google import genai
                from google.genai import types
                key = os.environ.get("GEMINI_API_KEY", "").strip()
                if not key:
                    raise ValueError("GEMINI_API_KEY is required for Google model checks")
                with genai.Client(api_key=key, http_options=types.HttpOptions(
                    api_version=GEMINI_API_VERSION, retry_options={"attempts": 1},
                )) as client:
                    names = _transport_request(lambda: [item.name.removeprefix("models/") for item in client.models.list() if item.name], record)
            else:
                with OpenAI(max_retries=0) as client:
                    names = _transport_request(lambda: [item.id for item in client.models.list()], record)
            record.update(listed_at=datetime.now(timezone.utc).isoformat(), available_model_ids=sorted(set(names)))
            listings[provider] = record
        listing = listings[provider]
        requested = model.removeprefix("models/") if provider == "google" else model
        if requested not in listing["available_model_ids"]:
            raise ValueError(f"Configured model ID {model!r} was not listed exactly by {provider}; aborting")
        checks[stage] = {**selected, "listed_at": listing["listed_at"], "model_listed": True,
                         "available_model_count": len(listing["available_model_ids"])}
    return {"stages": checks, "listings": listings}


class AuditValidationError(ValueError):
    """A model response remained structurally invalid after bounded retries."""

    __module__ = "w8bench.verifier.evidence_audit"

    def __init__(self, stage: str, attempts: list[dict[str, Any]], last_error: Exception):
        self.stage = stage
        self.attempts = attempts
        self.last_error = str(last_error)
        super().__init__(
            f"{stage} remained invalid after {len(attempts)} attempts: {last_error}"
        )

    def receipt(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "attempt_count": len(self.attempts),
            "last_validation_error": self.last_error,
            "attempts": self.attempts,
        }


SYSTEM_PROMPT = """You are the evidence-inventory stage of a pairwise audit.
For every rubric criterion, compare all supplied screenshot states with all
supplied DOM states, the shared trajectory, and each verifier's output.

For each modality, report whether the criterion-required evidence is COMPLETE,
PARTIAL, or ABSENT. Partial evidence is not complete. Preserve relationships:
labels must remain associated with their values, table cells with their row and
column, ordered events with their chronology, controls with selected state, and
URLs with the page/state they identify. A visible failure or blocker can itself
be criterion evidence. Do not infer hidden information.

Set screenshot_evidence_loss true only when criterion-required information is
missing or disconnected in screenshots but is available in DOM. Set
dom_model_evidence_loss by the exact reverse rule. Shared absence is not a
modality loss. Both flags may be true only when the modalities omit different
required information that the other preserves.

verifier_caught means the existing verifier accurately described both the
available evidence and any material evidence limitation in that modality. It is
not a judgment about whether you agree with the points awarded. Screenshot
claims may use only visible pixels; DOM claims may use only supplied DOM text.
The formatted action history is shared evidence for both modalities and may
prove process, navigation, stopping, and constraint compliance. The final
answer is a shared claim, not proof of page content. Consider the full ordered
trajectory: evidence from an earlier state remains available unless a later
state or action contradicts it. Action intent explains the attempted target but
is not proof of page content or success without execution/state evidence. An
observed URL explicitly present in the formatted action history is available to
both verifiers and can establish page identity. Do not count its absence from
screenshot pixels or DOM text as a modality loss. Navigation arguments show
intent, not an observed destination. Task instructions and the supplied initial
URL are shared context available to both verifiers. Do not count a URL component
already supplied there as missing merely because pixels or formatted history
omit it. The initial URL alone does not prove successful navigation or page
content; require corroborating ordered states or executed history for those
claims. Raw action metadata adds no evidence beyond the formatted history.
Do not invent query strings or fragments absent from all allowed inputs. Cite
every positive modality claim. Return JSON only. Your loss flags are proposals
that a separate adjudicator will review.
"""


ADJUDICATION_SYSTEM_PROMPT = """You are the final evidence-loss adjudicator.
Audit every criterion independently using the raw ordered screenshots, raw
ordered DOM states, normalized shared action history, final-answer claim,
verifier outputs, and the preliminary inventory.

Confirm screenshot evidence loss only when shared evidence plus DOM contains
explicit, cited, decision-essential evidence and shared evidence plus all
screenshots cannot establish the same criterion conclusion or score. Confirm
DOM evidence loss by the exact reverse rule. More explicit, redundant, or
convenient evidence is not loss. Observed URLs explicitly present in the shared
formatted action history count for both verifiers, including page identity.
Their absence from screenshot pixels or DOM text alone is not a loss. Do
not infer a site's omission from absent text unless the source explicitly states
the omission (such as "not listed", "none", or "TBD"). Shared ambiguity is not
loss.

Use temporal continuity across ordered states and the shared actions. An
earlier selected control or state remains evidence when no later action changes
it and the final state is consistent. Shared actions may prove process,
navigation, stopping, and prohibited-action constraints for both modalities.
Action intent identifies an attempted target but needs execution/state evidence
to prove success. Navigation arguments express intent, not an observed page.
Task instructions and the supplied initial URL are shared context for both
verifiers. A URL component already supplied there is not a modality loss merely
because it is absent from pixels or formatted history. The initial URL alone
does not prove successful navigation or page content: check corroborating
ordered states or executed history. Correct use of this context with supporting
state evidence is not a verifier miss. Raw action metadata adds no evidence
beyond the formatted history. Do not invent query strings or fragments absent
from all allowed inputs. Cite the supporting states or shared history when
relying on them, and identify the task context used in the explanation. The final
answer is a claim, not proof of page content.

Confirm a verifier miss only when the corresponding shared-plus-modality input
contains sufficient decisive evidence and that verifier fails to identify it,
misreads it, contradicts it, or materially misuses it. Correct use of shared
action history is not a miss. Each confirmed finding needs a citation from the
modality containing the decisive or missed evidence. Return JSON only.
"""


def _capture_eligibility_text(shared_trajectory: dict[str, Any]) -> str:
    eligibility = shared_trajectory.get("evaluation_context")
    eligibility_text = ""
    if eligibility:
        eligibility_text = (
            "PAIRED CAPTURE ELIGIBILITY: Directional evidence-loss coverage and decisions use ONLY "
            "the SAME original state IDs in both formats: " + json.dumps(eligibility["audit_eligible_states"]) + ". "
            "A state missing either capture or marked navigation-in-capture is unavailable for both "
            "directions of evidence-loss comparison. Do not treat a capture gap as modality loss. "
            "All available own-format states remain supplied for verifier-miss diagnostics; do not "
            "exclude navigation states from those diagnostics. Shared full action history and verified "
            "observed URLs remain shared context for every decision.\n\n"
        )
    return eligibility_text


def _audit_request_text(
    *,
    criteria: list[dict[str, Any]],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
) -> str:
    eligibility_text = _capture_eligibility_text(shared_trajectory)
    return (
        eligibility_text + "RUBRIC CRITERIA:\n"
        + json.dumps(criteria, ensure_ascii=False, indent=2)
        + "\n\nSHARED REPRESENTATION-NEUTRAL TRAJECTORY:\n"
        + json.dumps({key: value for key, value in shared_trajectory.items()
                      if key not in {"actions", "verifier_action_history", "evaluation_context"}}, ensure_ascii=False, indent=2)
        + "\n\nEXISTING SCREENSHOT VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(screenshot_context, ensure_ascii=False, indent=2)
        + "\n\nEXISTING DOM VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(dom_context, ensure_ascii=False, indent=2)
        + "\n\nReturn this exact shape:\n"
        '{"criteria":[{"criterion_index":0,"required_evidence":"what must be observable",'
        '"screenshot":{"coverage":"COMPLETE","available_evidence":["fact"],'
        '"missing_required_evidence":[],"verifier_caught":true,"citations":'
        '[{"source":"screenshot0.png","location":"visible location","quote":"visible text"}]},'
        '"dom_model":{"coverage":"PARTIAL","available_evidence":["fact"],'
        '"missing_required_evidence":["missing relationship"],"verifier_caught":true,'
        '"citations":[{"source":"dom_model0.txt","location":"L1-L2","quote":"exact text"}]},'
        '"screenshot_evidence_loss":false,"dom_model_evidence_loss":true,'
        '"explanation":"brief pairwise, evidence-grounded explanation"}]}\n'
        "Return exactly one row for every criterion index and no additional keys."
    )


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _source_instructions(screenshot_dir: Path, dom_dir: Path) -> str:
    screenshots = [path.name for path in ordered_audit_screenshots(screenshot_dir)]
    dom_states = [path.name for path in ordered_dom_states(dom_dir)]
    histories = {"screenshot": verifier_action_history(screenshot_dir),
                 "dom_model": verifier_action_history(dom_dir)}
    if histories["screenshot"] == histories["dom_model"]:
        histories = {"both verifiers": histories["screenshot"]}
    history_text = "\n".join(
        f"SHARED SOURCE: action_history ({mode})\n" + "\n".join(
            f"L{index:04d}: {line}" for index, line in enumerate(history.splitlines(), start=1)
        ) for mode, history in histories.items()
    )
    return (
        "CITATION SOURCE RULE: use one of these exact filenames.\n"
        f"Screenshot sources: {json.dumps(screenshots)}\n"
        f"DOM sources: {json.dumps(dom_states)}\n"
        f"Citation object keys (all required, no extra keys): {json.dumps(CITATION_KEYS)}\n"
        "source is an exact source name; location is Lx or Lx-Ly for DOM/history, "
        "or a visible image region for screenshots; quote is exact source text.\n"
        "Shared source: action_history; cite Lx or Lx-Ly and an exact quote.\n"
        "DOM and action_history quotes must be literal contiguous source text, "
        "without the supplied L-number prefixes, paraphrases or inserted ellipses. "
        "Prefer short exact excerpts; use separate citations for separate passages.\n"
        "Use only the history shown for the verifier being assessed.\n"
        + history_text + "\n"
    )


def pairwise_messages(
    *,
    screenshot_dir: Path,
    dom_dir: Path,
    criteria: list[dict[str, Any]],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": _source_instructions(screenshot_dir, dom_dir) + "\n" + _audit_request_text(
            criteria=criteria,
            screenshot_context=screenshot_context,
            dom_context=dom_context,
            shared_trajectory=shared_trajectory,
        ),
    }]
    for path in ordered_dom_states(dom_dir):
        numbered = "\n".join(
            f"L{number:04d}: {line}"
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        )
        content.append({"type": "text", "text": f"DOM SOURCE FILE: {path.name}\n{numbered}"})
    screenshots = ordered_audit_screenshots(screenshot_dir)
    if not screenshots:
        raise ValueError("Screenshot audit requires at least one screenshot state")
    for path in screenshots:
        content.append({"type": "text", "text": f"SCREENSHOT SOURCE FILE: {path.name}"})
        content.append(
            {"type": "image_url", "image_url": {"url": _data_url(path), "detail": "high"}}
        )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _adjudication_request_text(
    *,
    criteria: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    preliminary: list[dict[str, Any]],
) -> str:
    finding = (
        '{"confirmed":false,"decisive_evidence":"",'
        '"citations":[],"explanation":"why this is or is not confirmed"}'
    )
    eligibility_text = _capture_eligibility_text(shared_trajectory)
    return (
        eligibility_text + "RUBRIC CRITERIA:\n" + json.dumps(criteria, ensure_ascii=False, indent=2)
        + "\n\nSHARED REPRESENTATION-NEUTRAL TRAJECTORY:\n"
        + json.dumps({key: value for key, value in shared_trajectory.items()
                      if key not in {"actions", "verifier_action_history", "evaluation_context"}}, ensure_ascii=False, indent=2)
        + "\n\nSCREENSHOT VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(screenshot_context, ensure_ascii=False, indent=2)
        + "\n\nDOM VERIFIER OUTPUT (not ground truth):\n"
        + json.dumps(dom_context, ensure_ascii=False, indent=2)
        + "\n\nPRELIMINARY EVIDENCE INVENTORY (not ground truth):\n"
        + json.dumps(preliminary, ensure_ascii=False, indent=2)
        + "\n\nReturn exactly this shape with one row per criterion and no extra keys:\n"
        + '{"criteria":[{"criterion_index":0,'
        + '"screenshot_evidence_loss":' + finding + ','
        + '"dom_model_evidence_loss":' + finding + ','
        + '"screenshot_verifier_miss":' + finding + ','
        + '"dom_model_verifier_miss":' + finding + ','
        + '"explanation":"final criterion-level rationale"}]}\n'
        + "For a false finding, decisive_evidence must be an empty string and citations empty. "
        + "For a true finding, both must be non-empty. "
        + "Screenshot evidence loss requires a decisive DOM citation; DOM evidence loss "
        + "requires a decisive screenshot citation. A verifier miss requires decisive "
        + "evidence from that verifier's own input or its action_history. Citations from "
        + "the counterpart may support a contrast but cannot replace the required "
        + "decisive citation. Every supporting citation must also be valid. Shared "
        + "history alone cannot establish a modality loss."
    )


def adjudication_messages(
    *,
    screenshot_dir: Path,
    dom_dir: Path,
    criteria: list[dict[str, Any]],
    shared_trajectory: dict[str, Any],
    screenshot_context: list[dict[str, Any]],
    dom_context: list[dict[str, Any]],
    preliminary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{
        "type": "text",
        "text": _source_instructions(screenshot_dir, dom_dir) + "\n" + _adjudication_request_text(
            criteria=criteria,
            shared_trajectory=shared_trajectory,
            screenshot_context=screenshot_context,
            dom_context=dom_context,
            preliminary=preliminary,
        ),
    }]
    for path in ordered_dom_states(dom_dir):
        numbered = "\n".join(
            f"L{number:04d}: {line}"
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        )
        content.append({"type": "text", "text": f"DOM SOURCE FILE: {path.name}\n{numbered}"})
    for path in ordered_audit_screenshots(screenshot_dir):
        content.append({"type": "text", "text": f"SCREENSHOT SOURCE FILE: {path.name}"})
        content.append(
            {"type": "image_url", "image_url": {"url": _data_url(path), "detail": "high"}}
        )
    return [
        {"role": "system", "content": ADJUDICATION_SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _audit_http_hooks(record, provider):
    def requested(request):
        record["api_attempts"].append({"status_code": None})
        try:
            payload = json.loads(request.content)
            settings = (
                payload.get("generationConfig", {})
                if provider == "google"
                else {
                    key: payload[key]
                    for key in (
                        "model",
                        "response_format",
                        "temperature",
                        "seed",
                        "reasoning_effort",
                    )
                    if key in payload
                }
            )
            record["api_attempts"][-1]["request_settings"] = settings
        except (ValueError, TypeError, AttributeError):
            pass

    def received(response):
        record["api_attempts"][-1]["status_code"] = response.status_code

    return {"request": [requested], "response": [received]}


def _gemini_parts(body, types):
    parts = []
    for part in [{"type": "text", "text": body}] if isinstance(body, str) else body:
        if part["type"] == "text":
            parts.append(types.Part.from_text(text=part["text"]))
        elif part["type"] == "image_url":
            url = part["image_url"]["url"]
            match = re.fullmatch(r"data:(image/[\w.+-]+);base64,(.*)", url, re.DOTALL)
            if not match:
                raise ValueError("Gemini audit images must be base64 image data URLs")
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(match.group(2), validate=True),
                    mime_type=match.group(1),
                )
            )
        else:
            raise ValueError(f"Unsupported Gemini content type: {part['type']}")
    return parts


def _gemini_messages(messages, types):
    system, contents = [], []
    for message in messages:
        role, body = message["role"], message["content"]
        if role == "system":
            if not isinstance(body, str):
                raise ValueError("Gemini system instructions must be text")
            system.append(body)
            continue
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported Gemini message role: {role}")
        parts = _gemini_parts(body, types)
        contents.append(
            types.Content(role="model" if role == "assistant" else "user", parts=parts)
        )
    return system, contents


def _record_gemini_response(record, response, settings):
    usage = response.usage_metadata
    normalized = None
    if usage is not None:
        prompt = known_token_component(getattr(usage, "prompt_token_count", None))
        thinking = known_token_component(getattr(usage, "thoughts_token_count", None))
        candidates = known_token_component(getattr(usage, "candidates_token_count", None))
        reported_total = known_token_component(getattr(usage, "total_token_count", None))
        completion = candidates + thinking if candidates is not None and thinking is not None else None
        if completion is None and prompt is not None and reported_total is not None and reported_total >= prompt:
            completion = reported_total - prompt
        total = reported_total if reported_total is not None else prompt + completion if prompt is not None and completion is not None else None
        normalized = {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "reasoning_tokens": thinking,
            "cached_input_tokens": known_token_component(getattr(usage, "cached_content_token_count", None)),
            "cache_write_input_tokens": None,
            "total_tokens": total,
        }
        known = [value for value in (prompt, candidates, thinking) if value is not None]
        output_known = [value for value in (candidates, thinking) if value is not None]
        record["usage_lower_bound"] = {"prompt_tokens": prompt,
            "completion_tokens": sum(output_known) if output_known else None,
            "total_tokens": total if total is not None else sum(known) if known else None}
        record["usage_known_calls"] = {key: int(value is not None) for key, value in normalized.items()}
    components = normalized or {}
    record["usage_coverage"] = ("complete" if all(components.get(key) is not None for key in ("prompt_tokens", "completion_tokens"))
        else "partial" if any(value is not None for value in components.values()) else "unknown")
    record.update(
        response_id=response.response_id,
        response_model=response.model_version,
        usage=normalized,
        provider_usage=usage.model_dump() if usage is not None else None,
    )
    finish_reasons = [str(getattr(candidate, "finish_reason", "")).split(".")[-1]
        for candidate in getattr(response, "candidates", None) or []]
    record.update(
        finish_reason=finish_reasons[0] if len(finish_reasons) == 1 else None,
        incomplete=any(reason != "STOP" for reason in finish_reasons),
        requested_reasoning_effort=None,
        requested_temperature=settings.get("temperature"),
        requested_max_output_tokens=settings.get("max_output_tokens"),
    )
    return response.text


def _gemini_completion(model, messages, record, hooks):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY is required for Gemini audit models")
    try:
        from google import genai
        from google.genai import types
    except ImportError as error:
        raise RuntimeError(
            "Install the project dependencies: pip install -e ."
        ) from error
    system, contents = _gemini_messages(messages, types)
    settings = GEMINI_GENERATION_SETTINGS.copy()
    with genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            api_version=GEMINI_API_VERSION,
            retry_options={"attempts": 1},
            client_args={"event_hooks": hooks},
        ),
    ) as client:
        record["generation_settings"] = settings.copy()
        response = _transport_request(
            lambda: client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction="\n\n".join(system), **settings
                ),
            ),
            record,
        )
    return _record_gemini_response(record, response, settings)


def _openai_completion(model, messages, record, hooks):
    settings = OPENAI_GENERATION_SETTINGS.copy()
    with OpenAI(
        max_retries=0, http_client=DefaultHttpxClient(event_hooks=hooks)
    ) as client:
        record["generation_settings"] = settings.copy()
        response = _transport_request(
            lambda: client.chat.completions.create(
                model=model, messages=messages, **settings
            ),
            record,
        )
    record.update(
        response_id=response.id,
        response_model=response.model,
        system_fingerprint=getattr(response, "system_fingerprint", None),
        usage=response.usage.model_dump() if response.usage is not None else None,
    )
    choices = response.choices or []
    choice = choices[0] if len(choices) == 1 else None
    finish_reason = getattr(choice, "finish_reason", None)
    record.update(
        finish_reason=finish_reason,
        incomplete=choice is None or finish_reason not in {None, "stop"},
        requested_reasoning_effort=settings.get("reasoning_effort"),
        requested_temperature=settings.get("temperature"),
        requested_max_output_tokens=settings.get(
            "max_completion_tokens", settings.get("max_tokens")
        ),
    )
    return getattr(getattr(choice, "message", None), "content", None)


def _completion_value(content, record):
    if not content:
        raise ValueError("Evidence auditor returned an empty response")
    try:
        value = json.loads(content)
    except (TypeError, ValueError):
        record["response_text"] = content
        raise
    if not isinstance(value, dict):
        raise ValueError("Evidence auditor response must be a JSON object")
    return value


def _completion(
    model: str,
    messages: list[dict[str, Any]],
    *,
    records: list | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    provider = resolve_provider(model, provider)
    record = {
        "model": model,
        "provider": provider,
        "requested_model": model,
        "response_model": None,
        "api_version": GEMINI_API_VERSION if provider == "google" else None,
        "generation_settings": None,
        "stage": "adjudication"
        if messages[0]["content"] == ADJUDICATION_SYSTEM_PROMPT
        else "inventory",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "api_attempts": [],
        "usage": None,
    }
    if records is not None:
        records.append(record)
    from w8bench.settings import audit_settings
    record["effective_settings"] = audit_settings({record["stage"]: {"model": model, "provider": provider}})["stages"][record["stage"]]
    print(json.dumps({"stage": record["stage"], "model": model}), flush=True)
    started = time.perf_counter()
    hooks = _audit_http_hooks(record, provider)
    try:
        if provider == "google":
            content = _gemini_completion(model, messages, record, hooks)
        else:
            content = _openai_completion(model, messages, record, hooks)
        acceptance = response_acceptance(model, record.get("response_model"), record,
            output_cap=record.get("requested_max_output_tokens"))
        record.update(acceptance_policy_version=MODEL_ACCEPTANCE_POLICY,
            model_id_match=acceptance["model_id_match"], refusal_reason=acceptance["refusal_reason"])
        if not acceptance["accepted"]:
            raise ModelResponseRefusal(acceptance["refusal_reason"])
    except Exception as error:
        record["error_type"] = type(error).__name__
        raise
    finally:
        record["duration_seconds"] = time.perf_counter() - started
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
    return _completion_value(content, record)


def _audit_flags(payload, *, inventory):
    result, seen = {}, set()
    rows = payload.get("criteria", []) if isinstance(payload, dict) else []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or type(row.get("criterion_index")) is not int:
            continue
        index = row["criterion_index"]
        if index in seen:
            result[index] = {}
            continue
        seen.add(index)
        result[index] = {}
        for mode in ("screenshot", "dom_model"):
            for kind in ("evidence_loss", "verifier_miss"):
                field = f"{mode}_{kind}"
                if inventory:
                    modality = row.get(mode)
                    value = (row.get(field) if kind == "evidence_loss"
                             else modality.get("verifier_caught") if isinstance(modality, dict) else None)
                    if type(value) is bool and kind == "verifier_miss":
                        value = not value
                else:
                    value = row.get(field)
                    value = value.get("confirmed") if isinstance(value, dict) else None
                if type(value) is bool:
                    result[index][field] = value
    return result


def _record_retry_flag_changes(invalid_attempts: list, accepted: dict, *, inventory: bool) -> None:
    """Compare observable booleans only; missing/malformed flags stay unknown."""

    final = _audit_flags(accepted, inventory=inventory)
    for receipt in invalid_attempts:
        before = _audit_flags(receipt["raw_response"], inventory=inventory)
        changes, unknown = [], []
        for index in sorted(set(before) | set(final)):
            for field in ("screenshot_evidence_loss", "dom_model_evidence_loss",
                          "screenshot_verifier_miss", "dom_model_verifier_miss"):
                a, b = before.get(index, {}).get(field), final.get(index, {}).get(field)
                if a is None or b is None:
                    unknown.append({"criterion_index": index, "flag": field})
                elif a != b:
                    changes.append({"criterion_index": index, "flag": field,
                                    "failed_value": a, "accepted_value": b})
        receipt.update(flag_flips_detected=bool(changes), flag_flips=changes,
                       uncomparable_flags=unknown)


def _request_validated_audit(
    *,
    model: str,
    messages: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    screenshot_sources: set[str],
    dom_sources: set[str],
    screenshot_root: Path,
    dom_root: Path,
    complete: Callable[[str, list[dict[str, Any]]], dict[str, Any]],
    max_attempts: int = 3,
    invalid_receipts: list | None = None,
    inventory: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    current_messages = list(messages)
    last_error: Exception | None = None
    invalid_attempts: list[dict[str, Any]] = invalid_receipts if invalid_receipts is not None else []
    for attempt in range(1, max_attempts + 1):
        try:
            raw = complete(model, current_messages)
        except ModelResponseRefusal as exc:
            last_error = exc
            invalid_attempts.append({"attempt": attempt, "validation_error": str(exc),
                "refusal_reason": str(exc), "raw_response": None})
            continue
        try:
            validator = validate_audit_response if inventory else validate_adjudication_response
            decisions = validator(
                raw,
                criteria=criteria,
                screenshot_sources=screenshot_sources,
                dom_sources=dom_sources,
                screenshot_root=screenshot_root,
                dom_root=dom_root,
            )
            _record_retry_flag_changes(invalid_attempts, raw, inventory=inventory)
            return decisions, raw, attempt
        except (TypeError, ValueError) as exc:
            last_error = exc
            invalid_attempts.append(
                {"attempt": attempt, "validation_error": str(exc), "raw_response": raw}
            )
            if attempt < max_attempts:
                current_messages = current_messages + [
                    {"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)},
                    {
                        "role": "user",
                        "content": (
                            f"Your JSON failed validation: {exc}. Return a corrected complete JSON "
                            "object using the required schema and the same supplied evidence."
                            if inventory else
                            f"Your adjudication JSON failed validation: {exc}. Return a corrected "
                            "complete JSON object using the required schema and same evidence."
                        ),
                    },
                ]
    raise AuditValidationError(
        "primary evidence inventory" if inventory else "final evidence adjudication",
        invalid_attempts,
        last_error or ValueError("unknown validation error"),
    )
