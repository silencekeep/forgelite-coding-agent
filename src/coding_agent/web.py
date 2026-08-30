"""A dependency-free, loopback-only web console for ForgeLite."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .agent import CodingAgent
from .client import ModelRequestError
from .config import AgentConfig
from .thinking import get_profile


MAX_REQUEST_BYTES = 32_000
MAX_TASK_CHARACTERS = 16_000
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/console.css": ("console.css", "text/css; charset=utf-8"),
    "/assets/console.js": ("console.js", "text/javascript; charset=utf-8"),
    "/assets/thinking-indicator.css": ("thinking-indicator.css", "text/css; charset=utf-8"),
    "/assets/thinking-indicator.js": ("thinking-indicator.js", "text/javascript; charset=utf-8"),
    "/assets/watch-indicator.svg": ("watch-indicator.svg", "image/svg+xml"),
}
AgentFactory = Callable[..., Any]


class AgentBusyError(RuntimeError):
    """Another web request is already mutating the configured workspace."""


class ConsoleApplication:
    """Validate browser input and execute an isolated agent per request."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        model_override: str | None = None,
        agent_factory: AgentFactory = CodingAgent,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise ValueError(f"Workspace is not a directory: {self.workspace}")
        self.model_override = model_override
        self.agent_factory = agent_factory
        self._run_lock = threading.Lock()

    def run(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        task = payload.get("task")
        thinking = payload.get("thinking", "medium")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string.")
        if len(task) > MAX_TASK_CHARACTERS:
            raise ValueError(f"task exceeds {MAX_TASK_CHARACTERS} characters.")
        if not isinstance(thinking, str):
            raise ValueError("thinking must be a string.")
        profile = get_profile(thinking)
        config = AgentConfig.from_environment(
            model_override=self.model_override,
            thinking_override=profile.name.lower(),
        )
        events: list[dict[str, Any]] = []

        def audit(event: str, fields: dict[str, Any]) -> None:
            events.append({"event": event, **fields})

        if not self._run_lock.acquire(blocking=False):
            raise AgentBusyError("Another agent task is already running for this workspace.")
        try:
            agent = self.agent_factory(
                config,
                str(self.workspace),
                on_event=lambda _message: None,
                audit_sink=audit,
            )
            result = agent.run_task(task.strip())
        finally:
            self._run_lock.release()
        return {
            "ok": True,
            "result": result,
            "thinking": config.thinking_level,
            "events": events,
        }


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], application: ConsoleApplication) -> None:
        self.application = application
        super().__init__(address, ConsoleHandler)


class ConsoleHandler(BaseHTTPRequestHandler):
    server: ConsoleServer
    server_version = "ForgeLiteConsole/0.1"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        asset = ASSETS.get(path)
        if asset is None:
            self._json_response(404, {"ok": False, "error": "Not found."})
            return
        name, content_type = asset
        body = files("coding_agent.web_assets").joinpath(name).read_bytes()
        self._send(200, body, content_type)

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/run":
            self._json_response(404, {"ok": False, "error": "Not found."})
            return
        try:
            raw_length = self.headers.get("Content-Length", "")
            length = int(raw_length)
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError(f"Request body must be 1..{MAX_REQUEST_BYTES} bytes.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = self.server.application.run(payload)
            self._json_response(200, result)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            self._json_response(400, {"ok": False, "error": str(exc)})
        except ModelRequestError as exc:
            self._json_response(502, {"ok": False, "error": str(exc)})
        except AgentBusyError as exc:
            self._json_response(409, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._json_response(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} - {fmt % args}")

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; img-src 'self'")
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ForgeLite local-only web console.")
    parser.add_argument("--workspace", default=".", help="Fixed workspace available to the agent.")
    parser.add_argument("--port", type=int, default=8765, help="Loopback TCP port, default 8765.")
    parser.add_argument("--model", help="Override CODING_AGENT_MODEL.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the console in the default browser.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("--port must be between 1 and 65535.", file=sys.stderr)
        return 2
    try:
        # Fail before binding if the credential or model configuration is invalid.
        AgentConfig.from_environment(model_override=args.model)
        application = ConsoleApplication(args.workspace, model_override=args.model)
        server = ConsoleServer(("127.0.0.1", args.port), application)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"ForgeLite web console: {url}")
    print(f"Workspace: {application.workspace}")
    print("Press Ctrl+C to stop. The server listens on loopback only.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
