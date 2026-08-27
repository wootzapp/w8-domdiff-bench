#!/usr/bin/env python3
"""Serve HTMLCure's exact built-in smoke page for Wootz task trials."""

from __future__ import annotations

import argparse
import ast
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTMLCURE_ROOT = ROOT / ".runtime" / "HTMLCure"
EXPECTED_COMMIT = "18d68e8f1e5c2bcef7f3c00bcab3147e2a99d4db"


def load_official_smoke_html() -> str:
    head = (HTMLCURE_ROOT / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        commit = (HTMLCURE_ROOT / ".git" / head[5:]).read_text(
            encoding="utf-8"
        ).strip()
    else:
        commit = head
    if commit != EXPECTED_COMMIT:
        raise RuntimeError(f"HTMLCure commit is {commit}, expected {EXPECTED_COMMIT}")
    source = (HTMLCURE_ROOT / "htmleval" / "__main__.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "_SMOKE_HTML"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise RuntimeError("official HTMLCure _SMOKE_HTML constant was not found")


def handler_for(smoke_html: str):
    payload = smoke_html.encode("utf-8")

    class OfficialFixtureHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] == "/health":
                body = b"ok\n"
                content_type = "text/plain; charset=utf-8"
            elif self.path.split("?", 1)[0] in {"/", "/smoke"}:
                body = payload
                content_type = "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    return OfficialFixtureHandler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()
    smoke_html = load_official_smoke_html()
    digest = hashlib.sha256(smoke_html.encode("utf-8")).hexdigest()
    print(
        f"official HTMLCure smoke fixture commit={EXPECTED_COMMIT} "
        f"sha256={digest} http://{args.host}:{args.port}/smoke",
        flush=True,
    )
    server = ThreadingHTTPServer(
        (args.host, args.port),
        handler_for(smoke_html),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
