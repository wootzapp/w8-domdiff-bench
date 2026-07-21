"""Record the successful OpenAI-backed Day 1 smoke-test result."""

import json
from pathlib import Path


OUT = Path("outputs/day1")
SCORE_PATH = Path("data/materialized/traj/Adidas--11857213/scores/mmrubric_0.8-5-3.json")


def main() -> None:
    score_payload = json.loads(SCORE_PATH.read_text(encoding="utf-8"))
    details = json.loads(score_payload["gpt_response_text"])
    max_points = details["rubric_total_max_points"]
    earned_points = details["rubric_total_earned_points"]
    taxonomy = details.get("error_taxonomy", {})
    result = {
        "task_id": "Adidas--11857213",
        "status": "ok",
        "source_score_path": str(SCORE_PATH),
        "copied_score_path": str(OUT / "scores" / SCORE_PATH.name),
        "top_level_score": score_payload["score"],
        "rubric_score": earned_points / max_points if max_points else None,
        "rubric_total_max_points": max_points,
        "rubric_total_earned_points": earned_points,
        "rubric_is_success": bool(details["rubric_is_success"]),
        "outcome_success": details["outcome_success"],
        "first_failure_step": taxonomy.get("first_point_of_failure", {}).get("first_failure_step"),
        "is_ambiguous": taxonomy.get("task_verification", {}).get("is_ambiguous"),
        "is_invalid": taxonomy.get("task_verification", {}).get("is_invalid"),
        "note": "The subsequent official invocation reported cached because this real score file already existed.",
    }
    (OUT / "openai_verification_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    summary = f"""# Day 1 Execution Summary

## Goal

Execute Microsoft's released Universal Verifier on a frozen CUAVerifierBench trajectory.

## Repository and data

- Repository: `microsoft/fara` at `9f14b6e34094fe469a54a821e81e013a0739520d`
- Dataset: `microsoft/CUAVerifierBench`, `trajectories`, `fara7b_om2w_browserbase`
- Selected task: `Adidas--11857213` (one trajectory; selected without labels)

## Judge configuration

- Multimodal judge: `gpt-4o`
- Action/rubric judge: `gpt-4o`
- Credential source: ignored local `.env` injected only into the verifier child process
- Secrets stored in experiment artifacts: No

## Validation

- `Trajectory.from_folder()` succeeded.
- Parsed actions: 10.
- Screenshots opened: 11.
- Human/verifier annotation fields in materialized inputs: none.

## Result

- Official score JSON produced: Yes.
- Process rubric score: {result['rubric_score']:.4f} ({earned_points}/{max_points}).
- Process success: {result['rubric_is_success']}.
- Outcome success: {result['outcome_success']}.
- Top-level outcome score: {score_payload['score']}.
- First failure step: {result['first_failure_step']}.
- Task ambiguity verdict: {result['is_ambiguous']}.
- Invalid-task verdict: {result['is_invalid']}.
- Score JSON: `{SCORE_PATH}`.

## Important note

The original Azure attempt remained blocked by placeholder endpoint templates and unavailable Azure authentication. The OpenAI-only retry used the same released `verify_trajectories.py` code and the official score schema. A follow-up invocation was reported as `cached`, confirming that the first OpenAI invocation had already written the real score file.

## Day 1 conclusion

We successfully executed Microsoft's released Universal Verifier end to end on one frozen CUAVerifierBench trajectory. This is a one-trajectory execution smoke test, not a benchmark reproduction.
"""
    (OUT / "execution_summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
