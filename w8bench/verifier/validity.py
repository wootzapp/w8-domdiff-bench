"""Task-only ambiguity and validity classification with caller-bound prompts and logging."""
import json
import logging
from datetime import datetime, timezone
from string import Template
from typing import Any, Dict, List, Optional
import openai

from .models import TaskAgentResult
from .clients.providers import ChatCompletionClient
from .rubric_scoring import UngradedVerifierError

DEFAULT_SYSTEM_MESSAGES: List[Dict[str, str]] = [
    {"role": "system", "content": "You are a helpful AI assistant."}
]

MAX_LLM_RETRIES = 5

_REQUIRED_FIELDS: Dict[str, type] = {
    "reasoning_is_ambiguous": str,
    "is_ambiguous": bool,
    "ambiguity_codes": list,
    "reasoning_is_invalid": str,
    "is_invalid": bool,
    "invalid_task_codes": list,
}


async def _call_llm(
    messages: list[dict],
    client: Any,
    json_output: bool = False,
) -> str:
    """Return text from a client response."""
    supports_json = True
    fn = getattr(client, "supports_json", None)
    if callable(fn):
        try:
            supports_json = bool(fn())
        except TypeError:
            supports_json = bool(fn)
    try:
        result = await client.create(
            messages=messages,
            json_output=json_output if supports_json else False,
        )
    except openai.AuthenticationError as error:
        raise UngradedVerifierError("authentication", f"{type(error).__name__}: {error}") from error
    except openai.BadRequestError as error:
        if "check-access-response-enc" in str(error):
            raise UngradedVerifierError("authentication", f"{type(error).__name__}: {error}") from error
        raise
    content = result.content
    if hasattr(content, "content"):
        content = content.content
    assert isinstance(content, str), (
        f"Expected str content from client, got {type(content).__name__}: {content!r}"
    )
    return content


def _validate_verification_result(result: dict) -> None:
    """Raise ``ValueError`` if *result* is missing or mis-typed fields."""
    for field, expected_type in _REQUIRED_FIELDS.items():
        if field not in result:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(result[field], expected_type):
            raise ValueError(
                f"{field} must be {expected_type.__name__}, "
                f"got {type(result[field]).__name__}"
            )
    # Reasoning fields must be non-empty strings.
    for rf in ("reasoning_is_ambiguous", "reasoning_is_invalid"):
        if not result[rf]:
            raise ValueError(f"{rf} must be a non-empty string")


def _verification_messages(task, url, apps, date, system_messages, prompt_template):
    if apps is None:
        apps = ["N/A"]
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    apps_str = ", ".join(apps) if apps else "N/A"
    sys_msgs = system_messages if system_messages is not None else DEFAULT_SYSTEM_MESSAGES
    prompt = Template(prompt_template).substitute(
        task_definition=task, url=url or "N/A", apps=apps_str, date=date,
    )
    return list(sys_msgs) + [{"role": "user", "content": prompt}]


def _classification_result(result, logger):
    is_flagged = result.get("is_ambiguous") or result.get("is_invalid")
    logger.info(
        "Task verification result: is_ambiguous=%s, is_invalid=%s",
        result["is_ambiguous"], result["is_invalid"],
    )
    return TaskAgentResult(
        verifier_name="task_verification", score=0.0 if is_flagged else 1.0,
        reasoning="FLAGGED" if is_flagged else "OK", **result,
    )


def _failed_classification(last_error):
    error_msg = f"Failed after {MAX_LLM_RETRIES} attempts. Last error: {last_error}"
    return TaskAgentResult(
        verifier_name="task_verification", score=None, reasoning=error_msg,
        reasoning_is_ambiguous=error_msg, is_ambiguous=None,
        reasoning_is_invalid=error_msg, is_invalid=None,
    )


async def classify_task(
    task: str, url: str, client: ChatCompletionClient, *,
    prompt_template: str, logger: logging.Logger,
    apps: List[str] | None = None, date: str | None = None,
    system_messages: Optional[List[Dict[str, str]]] = None,
) -> TaskAgentResult:
    """Classify task ambiguity and validity without trajectory evidence."""
    messages = _verification_messages(task, url, apps, date, system_messages, prompt_template)
    retries_left = MAX_LLM_RETRIES
    last_error = None
    while retries_left > 0:
        try:
            response_text = await _call_llm(messages, client, json_output=True)
            result = json.loads(response_text)
            _validate_verification_result(result)
            return _classification_result(result, logger)
        except Exception as e:
            if isinstance(e, UngradedVerifierError):
                raise
            last_error = str(e)
            attempt = MAX_LLM_RETRIES - retries_left + 1
            logger.error(f"Error in task verification classification (attempt {attempt}): {e}")
            messages.append({"role": "user", "content": (
                f"Error: {e}. Please ensure your output follows the exact "
                "JSON format specified with all required fields."
            )})
            retries_left -= 1
    logger.warning(
        "Failed task verification classification after %d attempts. Last error: %s",
        MAX_LLM_RETRIES, last_error,
    )
    return _failed_classification(last_error)
