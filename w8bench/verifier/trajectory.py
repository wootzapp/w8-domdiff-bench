"""Shared trajectory parsing and native answer accounting."""
from pathlib import Path
import json
from dataclasses import asdict
from typing import Any, Dict
import os
from collections import defaultdict
from w8bench.verifier.clients.messages import RequestUsage

class FinalAnswer:
    """Final answer token accounting and serialization."""

    def __post_init__(self):
        if not isinstance(self.token_usage, defaultdict):
            token_usage_dict = self.token_usage if self.token_usage else {}
            self.token_usage = defaultdict(lambda: RequestUsage(prompt_tokens=0, completion_tokens=0))
            for k, v in token_usage_dict.items():
                self.set_token_usage(k, v)

    def set_token_usage(self, key: str, token_usage: RequestUsage | Dict[str, int]):
        if isinstance(token_usage, RequestUsage):
            self.token_usage[key] = token_usage
        else:
            self.token_usage[key] = RequestUsage(**token_usage)

    def add_token_usage(self, key: str, token_usage: RequestUsage | Dict[str, int]):
        if not isinstance(token_usage, RequestUsage):
            token_usage = RequestUsage(**token_usage)
        self.token_usage[key] = self.token_usage[key] + token_usage

    def to_dict(self):
        result = asdict(self)
        if 'token_usage' in result:
            result['token_usage'] = {k: asdict(v) if isinstance(v, RequestUsage) else v for k, v in self.token_usage.items()}
        return result

    def save(self, path: os.PathLike):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8', errors='backslashreplace') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def load_final_answer(path, answer_type):
    with open(path, "r", encoding="utf-8") as stream:
        return answer_type(**json.load(stream))


def remap_action_names(action_name: str) -> str:
    """Map solver stop actions to terminate."""
    if action_name == 'stop_execution':
        return 'terminate'
    elif action_name == 'stop_and_answer_question':
        return 'terminate'
    else:
        return action_name


def parse_text_based_event(event: Dict) -> Dict | None:
    """Parse thought/action messages containing JSON tool arguments."""
    import re
    message = event.get('message', '')
    if 'Thought #' not in message or 'Action #' not in message:
        return None
    try:
        thought_match = re.search('Thought #\\d+:\\s*(.+?)(?=\\nAction #)', message, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else ''
        action_match = re.search('with arguments\\s+(\\{.+\\})', message, re.DOTALL)
        if not action_match:
            return None
        arguments = json.loads(action_match.group(1))
        arguments['thoughts'] = thought
        action_name = arguments.get('action', 'unknown')
        return {'action': action_name, 'arguments': arguments}
    except (json.JSONDecodeError, AttributeError):
        return None


class Trajectory:
    _has_screenshots = False

    def __init__(self, path, skip_web_surfer_log=False):
        self.path = Path(path)
        if skip_web_surfer_log:
            self.events = []
        else:
            with open(self.path / 'web_surfer.log') as stream:
                self.events = [json.loads(line) for line in stream.readlines()]
        if self._has_screenshots:
            self.latest_screenshot = self.path / 'screenshot_scaled.png'
        answer_files = list(self.path.glob('*_answer.json'))
        if len(answer_files) != 1:
            raise ValueError(f"Expected exactly one answer file in {self.path}, found {len(answer_files)}")
        self.answer = self._answer_type.load(answer_files[0])
        if self._has_screenshots:
            if self.answer and self.answer.is_rel_paths:
                self.answer.screenshots = [self.path / filename for filename in self.answer.screenshots]
            self.screenshots = self.answer.screenshots
        self.is_action = False
        metadata_path = self.path / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as stream:
                metadata = json.load(stream)
                self.is_action = metadata.get("is_action", False)
        self._normalize_events()

    def _normalize_events(self):
        has_structured_events = any((e.get('action') is not None for e in self.events))
        if not has_structured_events and self.events:
            parsed_events = []
            for event in self.events:
                parsed = parse_text_based_event(event)
                if parsed:
                    parsed_events.append(parsed)
            self.events = parsed_events
        self.actions = [e['arguments'] for e in self.events if e.get('action', None) is not None]
        self.thoughts = [a['thoughts'] for a in self.actions]
        self.actions = [json.dumps({k: v for k, v in a.items() if k != 'thoughts'}) for a in self.actions]

    @property
    def is_aborted(self):
        return self.answer.is_aborted


def load_trajectory(task_root: str | Path, trajectory_type) -> Trajectory:
    root = Path(task_root).resolve(strict=True)
    trajectory = trajectory_type.from_folder(root)
    if trajectory is None:
        raise ValueError(f"Trajectory parser could not load {root}")
    return trajectory


def action_events(trajectory: Trajectory) -> list[dict[str, Any]]:
    return [dict(event) for event in trajectory.events if event.get("action") is not None]
