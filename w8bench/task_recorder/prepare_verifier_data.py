"""Validate paired recordings while proving each actor uses only its permitted input."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .recorder_support import write_json, write_json_lines


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSONL objects: {path}")
    return rows


def _inspect_state(source: Path, mode: str, steps: list, index: int, state: dict, allowed: set, manifest: dict) -> None:
    if (source / state.get("directory", "") / "action.json").is_file() != (index <= len(steps)):
        raise ValueError("action file chronology differs from executed action records")
    if state.get("state") != index or state.get("directory") != f"steps/step_{index:03d}":
        raise ValueError("state sequence is not contiguous")
    expected = f"{state['directory']}/" + ("dom_model.txt" if mode == "dom" else "screenshot.png")
    if state.get("observation") != expected:
        raise ValueError("observation path does not match its mode/state")
    path = (source / expected).resolve(strict=True)
    if not path.is_relative_to(source):
        raise ValueError("observation escapes its run")
    if hashlib.sha256(path.read_bytes()).hexdigest() != state.get("observation_sha256"):
        raise ValueError("observation digest changed")
    artifacts = state["artifacts"]
    for name, asset in artifacts.items():
        path = (source / asset["path"]).resolve(strict=True)
        if name not in allowed or path != source / state["directory"] / name:
            raise ValueError("forbidden artifact path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError("artifact digest changed")
    paired_names = {"dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt", "screenshot.png"}
    if state["capture"]["paired_complete"] and not paired_names <= artifacts.keys():
        raise ValueError("paired capture is missing artifacts")
    if state["capture"] != read_object(source / state["directory"] / "capture.json"):
        raise ValueError("capture metadata disagrees")
    if "screenshot.png" in artifacts:
        from PIL import Image
        with Image.open(source / artifacts["screenshot.png"]["path"]) as image:
            if list(image.size) != manifest["controls"]["viewport"]:
                raise ValueError("screenshot dimensions differ from the coordinate space")
            image.verify()
    for asset in (source / state["directory"]).iterdir():
        if (not asset.is_file() or asset.name not in allowed or not asset.resolve().is_relative_to(source)
                or asset.name != "action.json" and asset.name not in artifacts):
            raise ValueError(f"forbidden {mode} state artifact: {asset.name}")


def _inspect_actions(source: Path, states: list, steps: list, manifest: dict, final: dict, mode: str) -> list:
    decisions = read_events(source / "decisions.jsonl")
    if [row.get("model_turn") for row in decisions] != list(range(1, len(decisions) + 1)):
        raise ValueError("actor turns are not uniquely sequential")
    if manifest.get("model_turns") != len(decisions) or final.get("model_turns") != len(decisions):
        raise ValueError("actor call counts disagree")
    if final.get("run_status") in {"completed", "turn_limit", "captured"} and len(states) != len(steps) + 1:
        raise ValueError("a normally finalized run needs N+1 states for N actions")
    if len(states) > len(steps) + 1:
        raise ValueError("extra states are not attributable to executed actions")
    if final.get("recorded_steps") != len(steps):
        raise ValueError("executed action count disagrees")
    action_turns = [step.get("model_turn") for step in steps]
    if action_turns != sorted(set(action_turns)):
        raise ValueError("multiple actions refer to one model turn, or action order changed")
    for number, step in enumerate(steps, 1):
        if step.get("state") != number or number > len(states):
            raise ValueError("action state sequence is invalid")
        if read_object(source / states[number - 1]["directory"] / "action.json") != step:
            raise ValueError("action file differs from the manifest")
        turn = step.get("model_turn")
        if not isinstance(turn, int) or not 1 <= turn <= len(decisions) or not decisions[turn - 1].get("accepted"):
            raise ValueError("action does not reference an accepted model turn")
        if mode == "screenshot" and (step["action"].get("id") is not None or "target" in step):
            raise ValueError("screenshot action contains DOM target information")
    return decisions


def _inspect_actor_request(source: Path, task: dict, manifest: dict, states: list, row: dict, memory: str, dom_prompt: str, screenshot_prompt: str, action_schema: dict) -> tuple:
    mode = manifest["observation_mode"]
    turn = row["model_turn"]
    directory = source / "turns" / f"turn_{turn:06d}"
    if row.get("request") != f"turns/turn_{turn:06d}/request.json":
        raise ValueError("turn request path is not local to the turn")
    if row.get("response") and row["response"] != f"turns/turn_{turn:06d}/response.json":
        raise ValueError("turn response path is not local to the turn")
    if not 1 <= row.get("state", 0) <= len(states):
        raise ValueError("model turn refers to a nonexistent state")
    if read_object(directory / "result.json") != row:
        raise ValueError("turn result differs from decision log")
    state = states[row["state"] - 1]
    artifact = row.get("model_input", {}).get("observation", {})
    if artifact.get("sha256") != state["observation_sha256"]:
        raise ValueError("model turn refers to a different observation digest")
    request = read_object(directory / "request.json")
    content = request["contents"][0]["parts"]
    if row.get("task_memory_before") != memory:
        raise ValueError("actor memory does not match established actor history")
    expected_instructions = dom_prompt if mode == "dom" else screenshot_prompt
    controls = manifest["controls"]
    if (set(request) != {"model", "systemInstruction", "contents", "generationConfig"}
            or request.get("systemInstruction") != {"parts": [{"text": expected_instructions}]}
            or request.get("model") != task["model"]
            or request.get("generationConfig") != {"maxOutputTokens": controls["max_output_tokens"],
                "thinkingConfig": {"thinkingLevel": controls["reasoning_effort"].upper()},
                "mediaResolution": "MEDIA_RESOLUTION_HIGH", "responseMimeType": "application/json",
                "responseJsonSchema": action_schema}
            or len(request["contents"]) != 1 or set(request["contents"][0]) != {"role", "parts"}
            or request["contents"][0].get("role") != "user"):
        raise ValueError("actor request settings or instructions differ from its frozen policy")
    _inspect_request_observation(source, mode, state, directory, content, controls.get("media_resolution", "HIGH"))
    return state, content


def _inspect_request_observation(source: Path, mode: str, state: dict, directory: Path, content: list, media_resolution: str) -> None:
    if mode == "dom":
        if len(content) != 1 or set(content[0]) != {"text"}:
            raise ValueError("DOM actor request contains an image or extra observation")
    else:
        image_keys = {"inlineData", "mediaResolution"} if media_resolution == "ULTRA_HIGH" else {"inlineData"}
        if len(content) != 2 or set(content[0]) != {"text"} or set(content[1]) != image_keys:
            raise ValueError("screenshot actor request lacks its image or has an unexpected media policy")
        artifact = content[1]["inlineData"]["artifact"]
        image = (directory / artifact["path"]).resolve(strict=True)
        expected_image = {"inlineData": {"mimeType": "image/png", "artifact": artifact}}
        if media_resolution == "ULTRA_HIGH":
            expected_image["mediaResolution"] = {"level": "MEDIA_RESOLUTION_ULTRA_HIGH"}
        if (image != source / state["observation"] or artifact["sha256"] != state["observation_sha256"]
                or content[1] != expected_image):
            raise ValueError("model request references a different screenshot")


def _expected_actor_text(source: Path, task: dict, controls: dict, state: dict, turn: int, memory: str, recent: list, evidence_for_model) -> str:
    mode = task["observation_mode"]
    budget = controls["max_turns"]
    expected = (f"task:\n{task['instruction']}\n\nstep: {turn} of {budget}\n"
        f"model_turn: {turn}\nturns_remaining_including_current: {budget-turn+1}\n"
        f"turns_remaining_after_this_call: {budget-turn}\nhuman_intervention_available: false\n"
        f"{'viewport_css_pixels' if mode == 'dom' else 'screenshot_pixels'}: {controls['viewport'][0]} x {controls['viewport'][1]}\n\n"
        f"task_memory_from_prior_steps:\n{memory or '(none)'}\n\n"
        f"current_document_url: {state['capture']['url_after']}\n\n")
    if mode == "dom":
        refs = state["artifacts"]["agent_browser_actions.txt"]["path"]
        dom = state["artifacts"]["dom_model.txt"]["path"]
        expected += (f"current_agent_browser_snapshot:\n{(source / refs).read_text(encoding='utf-8')}\n\n"
            f"current_chromiumrl_evidence:\n{evidence_for_model((source / dom).read_text(encoding='utf-8'))}")
    expected += (f"\n\nrecent_action_outcomes:\n{json.dumps(recent[-6:], ensure_ascii=False)}\n\n"
        "Use the recorded observation-change signals. If an action made no observable change, "
        "change strategy instead of assuming it worked. Return one JSON action and "
        "wait for the harness to execute it and supply the next observation.")
    return expected


def _record_actor_history(source: Path, mode: str, states: list, steps_by_turn: dict, row: dict, memory: str, recent: list) -> str:
    turn = row["model_turn"]
    state = states[row["state"] - 1]
    if not row.get("accepted"):
        recent.append({"model_turn": turn, "rejected_action": row.get("decision"),
            "reason": row.get("rejection_reason") or row.get("error"), "delivery_status": "not_executed"})
    else:
        step = steps_by_turn.get(turn)
        if step and "progress" in step:
            from .capture import CaptureBundle, action_progress
            after = states[step["next_state"]-1]
            evidence = []
            for captured in (state, after):
                files = captured["artifacts"]
                evidence.append(CaptureBundle(observation_mode=mode,
                    document_url=captured["capture"]["url_after"],
                    screenshot_path=(source / captured["observation"]) if mode == "screenshot" else None,
                    model_text=(source / files["dom_model.txt"]["path"]).read_text(encoding="utf-8") if mode == "dom" else "",
                    agent_browser_action_text=(source / files["agent_browser_actions.txt"]["path"]).read_text(encoding="utf-8") if mode == "dom" else ""))
            if step["progress"] != action_progress(*evidence):
                raise ValueError("actor observation-change signals contain passive evidence or differ from saved observations")
            if step["action_succeeded"]:
                candidate = (row.get("decision") or {}).get("memory")
                memory = candidate.strip() if isinstance(candidate, str) and candidate.strip() else memory
            recent.append({"model_turn": turn, "action": step["action"],
                "action_succeeded": step["action_succeeded"],
                "delivery_status": "delivered" if step["action_succeeded"] else "failed",
                "progress": step["progress"]})
    return memory


def _recording_coverage(states: list, steps: list) -> dict:
    expected_ids = list(range(1, len(steps) + 2))
    coverage = {"expected_state_ids": expected_ids,
        "format_gaps": {"screenshot": [], "dom_model": []},
        "navigation_states": [], "audit_eligible_states": [], "states": [],
        "observed_url_timeline": []}
    for state_id in expected_ids:
        state = states[state_id - 1] if state_id <= len(states) else None
        artifacts = state["artifacts"] if state else {}
        capture = state["capture"] if state else {}
        for mode_name, filename in (("screenshot", "screenshot.png"), ("dom_model", "dom_model.txt")):
            if filename not in artifacts:
                coverage["format_gaps"][mode_name].append(state_id)
        navigation = capture.get("navigation_during_capture") is True
        if navigation:
            coverage["navigation_states"].append(state_id)
        complete = capture.get("paired_complete") is True and all(name in artifacts for name in
            ("dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt", "screenshot.png"))
        verified = capture.get("url_metadata_complete") is True and bool(capture.get("url_after"))
        eligible = complete and not navigation
        reasons = ([] if complete else ["incomplete_paired_capture"]) + (["navigation_during_capture"] if navigation else [])
        metadata_warnings = [] if verified else ["observed_url_metadata_missing"]
        if eligible:
            coverage["audit_eligible_states"].append(state_id)
        coverage["observed_url_timeline"].append({"state": state_id,
            "url": capture.get("url_after") if verified else None, "verified": verified})
        coverage["states"].append({"state": state_id, "source_index": state_id,
            "eligible": eligible, "reasons": reasons, "metadata_warnings": metadata_warnings, "artifacts": artifacts,
            "navigation_during_capture": navigation, "capture": capture})
    coverage["eligible_fraction"] = len(coverage["audit_eligible_states"]) / len(expected_ids)
    coverage["reason"] = None if coverage["audit_eligible_states"] else "no_eligible_paired_states"
    return coverage


def inspect_recording(source: Path) -> dict[str, Any]:
    """Validate actor isolation, provenance, counters, and evidence availability."""
    from .prompts import DOM_PROMPT, SCREENSHOT_PROMPT
    from .runner import ACTION_SCHEMA, SCREENSHOT_ACTION_SCHEMA, chromiumrl_evidence_for_model
    source = source.resolve(strict=True)
    task, manifest, final = [read_object(source / name) for name in ("task.json", "manifest.json", "final.json")]
    mode = manifest.get("observation_mode")
    if mode not in {"dom", "screenshot"} or task.get("observation_mode") != mode:
        raise ValueError("expected an independent DOM or screenshot run")
    if manifest.get("status") == "running" or manifest.get("final") != final:
        raise ValueError("recording is unfinished or final metadata disagrees")
    if any(task.get(key) != manifest.get(key) for key in ("task_id", "source_task_id", "instruction", "start_url", "model")):
        raise ValueError("task and manifest identity differ")
    allowed = {"dom.json", "dom_full.txt", "dom_model.json", "dom_model.txt",
        "screenshot.png", "capture.json", "action.json"}
    if mode == "dom":
        allowed.add("agent_browser_actions.txt")
    states = manifest.get("states", [])
    steps = manifest.get("steps", [])
    for index, state in enumerate(states, 1):
        _inspect_state(source, mode, steps, index, state, allowed, manifest)
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("recordings must be self-contained, without symlinks")
    decisions = _inspect_actions(source, states, steps, manifest, final, mode)
    steps_by_turn = {step["model_turn"]: step for step in steps}
    recent = []
    memory = ""
    for row in decisions:
        state, content = _inspect_actor_request(source, task, manifest, states, row, memory, DOM_PROMPT, SCREENSHOT_PROMPT,
            SCREENSHOT_ACTION_SCHEMA if mode == "screenshot" else ACTION_SCHEMA)
        expected = _expected_actor_text(source, task, manifest["controls"], state, row["model_turn"], memory, recent, chromiumrl_evidence_for_model)
        if content[0] != {"text": expected}:
            raise ValueError(f"{mode} actor text contains an unapproved observation source")
        memory = _record_actor_history(source, mode, states, steps_by_turn, row, memory, recent)
    files = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file() and path.name not in {"completion.json", "completion_actor_native.json"}}
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    coverage = _recording_coverage(states, steps)
    return {"source": str(source), "task": task, "manifest": manifest, "final": final,
        "decisions": decisions, "files": files, "recording_sha256": fingerprint, "coverage": coverage}


def _evaluation_context(recording: dict, task: dict, manifest: dict, mode: str, task_id: str) -> dict:
    # One receipt binds both evidence projections to one immutable actor run.
    created_at = manifest.get("created_at") or task.get("created_at")
    if not isinstance(created_at, str):
        raise ValueError("recording needs a creation timestamp to freeze task-validity date")
    validity_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
    context = {"schema_version": "same-run-evidence/v1", "recording_sha256": recording["recording_sha256"],
        "task_id": task_id, "actor_arm": mode, "trial_id": str(task.get("run_name") or manifest["run_name"]),
        "validity_date": validity_date, "run_status": recording["final"]["run_status"],
        "source_files_sha256": recording["files"], **recording["coverage"]}
    return context


def _verifier_events(manifest: dict) -> list:
    from .trajectory import websurfer_action
    events = []
    for step in manifest["steps"]:
        name, arguments, _ = websurfer_action(step)
        arguments = {key: value for key, value in arguments.items()
            if key in {"action", "url", "id", "ref", "coordinate", "x", "y", "text", "key", "keys", "pixels", "seconds"}
            and value is not None}
        arguments["thoughts"] = ""  # Required parser field; actor notes are not shared verifier evidence.
        if "id" in arguments:
            ref = str(arguments.pop("id")).lstrip("@")
            arguments["ref"] = ref if ref.startswith("e") else f"e{ref}"
        if "x" in arguments and "y" in arguments:
            arguments["coordinate"] = [arguments.pop("x"), arguments.pop("y")]
        events.append({"source": "WebSurfer", "action": name, "arguments": arguments,
            "model_turn": step["model_turn"], "state": step["state"], "next_state": step.get("next_state"),
            "execution_status": "success" if step["action_succeeded"] else "failure"})
    return events


def _stage_projection(source: Path, staging: Path, task_id: str, manifest: dict, task_data: list, events: list, answer: dict, folder: str, filename: str, stem: str) -> dict:
    root = staging / folder / task_id
    root.mkdir(parents=True)
    write_json(root / "task_data.json", task_data)
    write_json_lines(root / "web_surfer.log", events)
    names = []
    for state in manifest["states"]:
        artifact = state["artifacts"].get(filename)
        if artifact is None:
            continue
        original = source / artifact["path"]
        if hashlib.sha256(original.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("source evidence changed during export")
        name = f"{stem}{state['state']}{original.suffix}"
        shutil.copyfile(original, root / name)
        names.append(name)
    write_json(root / "final_answer.json", {**answer, **({"screenshots": names} if folder == "data-ss" else {})})
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()}


def prepare_recording(recording: dict[str, Any], output: Path) -> dict[str, Any]:
    source = Path(recording["source"])
    task, manifest = recording["task"], recording["manifest"]
    mode, task_id = task["observation_mode"], task["source_task_id"]
    destination = output / str(task.get("run_name") or manifest["run_name"]) / mode / task_id / recording["recording_sha256"]
    if destination.resolve().is_relative_to(source):
        raise ValueError("export output must be outside the source recording")
    if destination.exists():
        raise ValueError(f"output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    context = _evaluation_context(recording, task, manifest, mode, task_id)
    events = _verifier_events(manifest)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        staging = Path(temp) / "recording"
        answer = {"final_answer": recording["final"]["final_answer"], "env_state_json": "<no_answer>",
            "env_state_raw": "<no_answer>", "is_aborted": recording["final"]["run_status"] != "completed",
            "is_rel_paths": True, "token_usage": {}}
        task_data = [{"task_id": task_id, "confirmed_task": task["instruction"], "website": task["start_url"],
            "level": task.get("difficulty") or task.get("category") or "recorded_browser_task", "evaluation_context": context}]
        projected = {}
        for folder, filename, stem in (("data-ss", "screenshot.png", "screenshot"), ("data-dom", "dom_model.txt", "dom_model")):
            projected[folder] = _stage_projection(source, staging, task_id, manifest, task_data, events, answer, folder, filename, stem)
        if inspect_recording(source)["recording_sha256"] != recording["recording_sha256"]:
            raise ValueError("source changed during export")
        write_json(staging / "input_receipt.json", {**context, "projected_files_sha256": projected})
        staging.rename(destination)
    return {"source": str(source), "output": str(destination), "observation_mode": mode,
        "screenshot_task": str(destination / "data-ss" / task_id), "dom_task": str(destination / "data-dom" / task_id),
        "recording_sha256": recording["recording_sha256"], "evaluation_context": context}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recordings", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.recordings.resolve(strict=True)
    if args.output.resolve().is_relative_to(root):
        raise ValueError("export output must be outside its source tree")
    sources = [root] if (root / "task.json").exists() else sorted(p.parent for p in root.rglob("task.json"))
    if not sources:
        raise ValueError("no independent recordings found")
    result = []
    for source in sources:
        recording = inspect_recording(source)
        result.append({"source": str(source), "status": "valid"} if args.dry_run
            else prepare_recording(recording, args.output))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
