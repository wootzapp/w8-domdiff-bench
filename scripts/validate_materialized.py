"""Validate materialized Day 1 trajectory folders against the pinned Fara API."""

import json
from pathlib import Path

from PIL import Image
from webeval.trajectory import Trajectory


TRAJ_ROOT = Path("data/materialized/traj")
TASKS_PATH = Path("data/materialized/tasks.json")
OUTPUT_PATH = Path("outputs/day1/trajectory_validation.json")
FORBIDDEN_ANNOTATION_FIELDS = {
    "gpt_eval_json", "uv_rubric_score", "uv_outcome_success", "mm_is_success",
    "verifier_is_success", "final_human_outcome_label", "final_human_process_label",
    "median_human_rubric_score_agnostic", "majority_human_outcome_vote",
}


def main() -> None:
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    task_ids = {str(task["task_id"]) for task in tasks}
    results = []
    for task_dir in sorted(path for path in TRAJ_ROOT.iterdir() if path.is_dir()):
        trajectory = Trajectory.from_folder(task_dir)
        if trajectory is None:
            raise RuntimeError(f"Trajectory.from_folder failed for {task_dir}")
        actions = [event for event in trajectory.events if event.get("action")]
        screenshots = sorted(task_dir.glob("screenshot*.png"))
        if not actions:
            raise RuntimeError(f"No actions parsed for {task_dir.name}")
        if not screenshots:
            raise RuntimeError(f"No screenshots found for {task_dir.name}")
        for screenshot in screenshots:
            with Image.open(screenshot) as image:
                image.verify()
        final_answers = list(task_dir.glob("*_final_answer.json"))
        if len(final_answers) != 1:
            raise RuntimeError(f"Expected one final-answer JSON in {task_dir}, found {final_answers}")
        payload = json.loads(final_answers[0].read_text(encoding="utf-8"))
        if task_dir.name not in task_ids:
            raise RuntimeError(f"{task_dir.name} is absent from {TASKS_PATH}")
        materialized_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [task_dir / "web_surfer.log", final_answers[0]]
        )
        present_forbidden = sorted(
            field for field in FORBIDDEN_ANNOTATION_FIELDS if field in materialized_text
        )
        if present_forbidden:
            raise RuntimeError(f"Human/verifier annotation field leaked into {task_dir}: {present_forbidden}")
        result = {
            "task_id": task_dir.name,
            "event_count": len(trajectory.events),
            "action_count": len(actions),
            "screenshot_count": len(screenshots),
            "final_answer_json_readable": True,
            "task_present_in_tasks_json": True,
            "screenshots_open_successfully": True,
            "forbidden_annotation_fields_present": present_forbidden,
            "status": "valid",
        }
        results.append(result)
        print(json.dumps(result, sort_keys=True))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
