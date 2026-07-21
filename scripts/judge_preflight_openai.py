"""Sanitized OpenAI preflight through the released verifier client classes."""

import asyncio
import json
import logging
from pathlib import Path

from PIL import Image

from webeval.oai_clients.graceful_client import GracefulRetryClient
from webeval.oai_clients.messages import UserMessage


CONFIG_DIR = Path("endpoint_configs/openai/prod")
OUT_DIR = Path("outputs/day1")
SCREENSHOT = Path("data/materialized/traj/Adidas--11857213/screenshot0.png")
MODEL = "gpt-4o"


async def request(kind: str) -> dict[str, object]:
    client = None
    try:
        client = GracefulRetryClient.from_path(
            CONFIG_DIR, logger=logging.getLogger(f"openai_preflight.{kind}"), eval_model=MODEL
        )
        if kind == "multimodal":
            with Image.open(SCREENSHOT) as image:
                message = UserMessage(content=["Reply exactly OK.", image.copy()])
        else:
            message = UserMessage(content="Reply exactly OK.")
        result = await client.create([message])
        return {"model": MODEL, "status": "ok", "response_received": bool(result.content)}
    except Exception as exc:
        return {"model": MODEL, "status": "error", "exception_type": type(exc).__name__}
    finally:
        if client is not None:
            await client.close()


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    results = {"multimodal": await request("multimodal"), "text": await request("text")}
    manifest = {
        "judge_model": MODEL,
        "action_judge_model": MODEL,
        "config_directory": str(CONFIG_DIR),
        "credential_source": "OPENAI_API_KEY loaded from ignored local .env into child process",
        "credentials_present": all(row["status"] == "ok" for row in results.values()),
        "secrets_stored": False,
        "config_files": sorted(path.name for path in CONFIG_DIR.glob("*.json")),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "judge_config_manifest_openai.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "logs" / "judge_preflight_openai.log").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    return 0 if manifest["credentials_present"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
