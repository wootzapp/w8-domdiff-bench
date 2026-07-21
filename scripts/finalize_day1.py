"""Write final reproducibility artifacts for the completed Day 1 attempt."""

import json
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(".")
OUT = ROOT / "outputs/day1"
ENV = ROOT / "environment"


def main() -> None:
    ENV.mkdir(exist_ok=True)
    OUT.joinpath("logs").mkdir(parents=True, exist_ok=True)
    (ENV / "python_version.txt").write_text(
        f"Python {platform.python_version()}\n", encoding="utf-8"
    )
    (ENV / "system_info.txt").write_text(platform.platform() + "\n", encoding="utf-8")
    freeze = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"], text=True, stderr=subprocess.DEVNULL
    )
    (ENV / "pip_freeze.txt").write_text(freeze, encoding="utf-8")

    validation = json.loads((OUT / "trajectory_validation.json").read_text(encoding="utf-8"))
    report_rows = [
        json.loads(line)
        for line in (OUT / "verify_report.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result = report_rows[0]
    error_type = (result.get("error") or "unknown").split(":", 1)[0]
    (OUT / "logs" / "trajectory_validation.log").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in validation) + "\n",
        encoding="utf-8",
    )
    (OUT / "logs" / "verifier_run.log").write_text(
        "\n".join([
            "Official verifier invocation completed.",
            f"task_id: {result.get('task_id')}",
            f"status: {result.get('status')}",
            f"duration_sec: {result.get('duration_sec')}",
            f"error_type: {error_type}",
            "error_summary: rubric generation exhausted five attempts because Azure AD token acquisition failed.",
            "score_json_generated: false",
            "sanitization: no credential values or endpoint values retained in this log.",
        ]) + "\n",
        encoding="utf-8",
    )
    summary = f"""# Day 1 Execution Summary

## Goal

Execute Microsoft's released Universal Verifier on a frozen CUAVerifierBench trajectory.

## Repository

- Repository: microsoft/fara
- Commit: `9f14b6e34094fe469a54a821e81e013a0739520d`
- Python version: {platform.python_version()}

## Dataset

- Dataset: microsoft/CUAVerifierBench
- Config: trajectories
- Split: fara7b_om2w_browserbase
- Selected task ID: `Adidas--11857213` (dataset index 1; selected for small screenshot count only)

## Judge configuration

- Multimodal judge: `gpt-4o`
- Action/rubric judge: `o4-mini`
- Credentials source: Azure AD DefaultAzureCredential chain
- Secrets stored in artifacts: No
- Preflight result: blocked; no usable Azure credential and the released development configs use placeholder endpoints.

## Validation

- Trajectory successfully loaded: Yes
- Parsed actions: {validation[0]['action_count']}
- Screenshots: {validation[0]['screenshot_count']}
- Final-answer file readable: Yes
- Human/verifier annotations in materialized inputs: No

## Execution command

```bash
repo/fara/.venv/bin/python repo/fara/webeval/scripts/verify_trajectories.py --input data/materialized/traj --task-data data/materialized/tasks.json --task-data-format om2w --eval-config endpoint_configs/judge_active/prod --judge-model gpt-4o --o4mini-model o4-mini --processes 1 --limit 1 --rubric-threshold 0.8 --max-images-per-criterion 5 --mm-keypoint-score-threshold 3 --majority-vote-instances 1 --success outcome --report outputs/day1/verify_report.jsonl
```

## Result

- Runner status: `{result.get('status')}`
- Process rubric score: not produced
- Process success: not produced
- Outcome success: not produced
- First failure step: not produced
- Runtime: {result.get('duration_sec')} seconds
- Score JSON: not produced

## Issues encountered

1. The declared `webeval` dependency set includes the out-of-scope Fara solver stack; the official standalone verifier package was installed editable without those unused solver dependencies.
2. The released Azure development configs contain placeholder endpoint values, and this environment has no Azure CLI session, managed identity, or configured workload/environment credential. Rubric generation failed after five official retry attempts.

## Deviations from the paper

- Only one trajectory was selected.
- Majority voting was disabled.
- No benchmark metrics were calculated.
- No browser agent or live website was executed.
- The standalone verifier did not generate a score because judge endpoint access was unavailable.

## Day 1 conclusion

The repository setup, frozen-dataset acquisition, label-safe materialization, trajectory validation, judge-client initialization, and official verifier invocation were completed. End-to-end paper execution was **not** achieved because a real score JSON could not be generated without usable judge endpoint configuration and credentials.
"""
    (OUT / "execution_summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps({"status": result.get("status"), "score_json_generated": False}, indent=2))


if __name__ == "__main__":
    main()
