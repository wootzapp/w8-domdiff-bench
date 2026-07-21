"""Sanitized preflight for the released verifier's two judge clients."""

import asyncio
import json
import logging
from pathlib import Path

from PIL import Image

from webeval.oai_clients.graceful_client import GracefulRetryClient
from webeval.oai_clients.messages import UserMessage


CONFIG_DIR = Path("endpoint_configs/judge_active/prod")
OUT_DIR = Path("outputs/day1")
SCREENSHOT = Path("data/materialized/traj/Adidas--11857213/screenshot0.png")
MODELS = {"multimodal_judge": "gpt-4o", "action_rubric_judge": "o4-mini"}


async def preflight_one(name: str, model: str) -> dict[str, object]:
    logger = logging.getLogger(f"judge_preflight.{name}")
    try:
        client = GracefulRetryClient.from_path(CONFIG_DIR, logger=logger, eval_model=model)
        if name == "multimodal_judge":
            with Image.open(SCREENSHOT) as image:
                message = UserMessage(content=["Reply exactly OK.", image.copy()])
            image_included = True
        else:
            message = UserMessage(content="Reply exactly OK.")
            image_included = False
        result = await client.create([message])
        await client.close()
        return {
            "model": model,
            "status": "ok",
            "image_input_tested": image_included,
            "response_received": bool(result.content),
        }
    except Exception as exc:  # Log only class names; exception strings can contain sensitive endpoints.
        return {
            "model": model,
            "status": "error",
            "image_input_tested": name == "multimodal_judge",
            "exception_type": type(exc).__name__,
        }


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    config_files = sorted(path.name for path in CONFIG_DIR.glob("*.json"))
    manifest = {
        "judge_model": MODELS["multimodal_judge"],
        "action_judge_model": MODELS["action_rubric_judge"],
        "config_directory": str(CONFIG_DIR),
        "credential_source": "Azure AD DefaultAzureCredential chain (Azure CLI, managed identity, then default)",
        "credentials_present": None,
        "secrets_stored": False,
        "config_files": config_files,
    }
    results = {
        name: await preflight_one(name, model) for name, model in MODELS.items()
    }
    manifest["credentials_present"] = all(result["status"] == "ok" for result in results.values())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "judge_config_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "logs" / "judge_preflight.log").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    return 0 if manifest["credentials_present"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
