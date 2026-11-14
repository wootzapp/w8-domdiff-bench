"""Keep the complete contract suite offline and independent of local credentials."""
from pathlib import Path
import socket

import pytest


@pytest.fixture(autouse=True)
def offline_model_access(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test-key")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(Path(__file__).resolve().parents[1] / ".runtime" / "tiktoken_cache"))
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError("offline tests cannot connect to model providers or external services")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
