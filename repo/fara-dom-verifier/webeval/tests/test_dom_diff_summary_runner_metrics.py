from __future__ import annotations

import asyncio
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import verify_trajectories_dom_diff_summary as runner


class _Endpoint:
    async def create(self, *args, **kwargs):
        return "ok"


class _RetryingClient:
    def __init__(self) -> None:
        self._clients = [_Endpoint()]

    async def create(self, *args, **kwargs):
        # Simulate one failed/redirected endpoint attempt plus a successful one
        # inside a single logical graceful-client call.
        await self._clients[0].create(*args, **kwargs)
        return await self._clients[0].create(*args, **kwargs)


def test_call_metrics_separate_logical_calls_attempts_and_retries() -> None:
    client = _RetryingClient()
    runner._instrument_client_calls(client)
    before = runner._call_metrics(client)
    assert asyncio.run(client.create()) == "ok"
    after = runner._call_metrics(client)
    delta = runner._call_metrics_delta(after, before)
    assert delta == {"logical_calls": 1, "api_attempts": 2, "retries": 1}

