"""Guard the retained experiment scope."""

import json
import sys
from pathlib import Path


REGISTRY_PATH = Path("config/experiment_registry.json")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: experiment_guard.py E0")
    experiment_id = sys.argv[1]
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    experiment = registry["day2"]["experiments"].get(experiment_id)
    if experiment is None:
        raise SystemExit(f"Unknown experiment: {experiment_id}")
    if experiment["status"] != "complete" or not experiment["run_authorized"]:
        print(json.dumps({
            "experiment": experiment_id,
            "allowed": False,
            "status": experiment["status"],
            "run_authorized": experiment["run_authorized"],
            "reason": "Only the completed E0 artifact set is retained.",
        }, indent=2))
        return 2
    print(json.dumps({"experiment": experiment_id, "retained": True, "status": "complete"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
