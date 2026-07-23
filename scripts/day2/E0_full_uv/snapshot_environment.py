"""Create the E0 reproducibility snapshot without exposing credentials."""

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone

from e0_common import ENVIRONMENT_ROOT, PROJECT_ROOT, ensure_output_dirs, write_json


def command_output(command: list[str]) -> str:
    return subprocess.check_output(command, cwd=PROJECT_ROOT, text=True).strip()


def main() -> None:
    ensure_output_dirs()
    fara_commit = command_output(["git", "-C", "repo/fara", "rev-parse", "HEAD"])
    pip_freeze = command_output([sys.executable, "-m", "pip", "freeze"])
    (ENVIRONMENT_ROOT / "git_commit.txt").write_text(fara_commit + "\n", encoding="utf-8")
    (ENVIRONMENT_ROOT / "python_version.txt").write_text(
        f"Python {platform.python_version()}\n", encoding="utf-8"
    )
    (ENVIRONMENT_ROOT / "pip_freeze.txt").write_text(pip_freeze + "\n", encoding="utf-8")
    write_json(
        ENVIRONMENT_ROOT / "judge_config_sanitized.json",
        {
            "provider": "openai",
            "judge_model": "gpt-5.2",
            "action_rubric_model": "o4-mini",
            "config_path": "endpoint_configs/openai/canonical",
            "config_files": ["openai_gpt5_2.json", "openai_o4_mini.json"],
            "credential_source": "ignored .env loaded into child process",
            "credentials_present": True,
            "secrets_stored": False,
            "distinct_model_roles": True,
        },
    )
    config = json.loads((PROJECT_ROOT / "config/day2/E0_full_uv.json").read_text(encoding="utf-8"))
    config["started_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(ENVIRONMENT_ROOT / "execution_config.json", config)
    print(json.dumps({"fara_commit": fara_commit, "environment_snapshot": "complete"}))


if __name__ == "__main__":
    main()
