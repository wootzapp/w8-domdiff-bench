"""Inject OPENAI_API_KEY from the ignored .env file into one child process."""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: run_with_openai_env.py <script-or-command> [args...]")
    env_path = Path(".env")
    values = dotenv_values(env_path)
    key = values.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit(".env does not contain a non-empty OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = key
    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])


if __name__ == "__main__":
    main()
