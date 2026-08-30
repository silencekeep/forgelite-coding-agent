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

from .agent import MAX_TASK_CHARACTERS, AgentStepLimitError, CodingAgent
from .client import ModelRequestError
from .config import AgentConfig
from .thinking import get_profile


MAX_REQUEST_BYTES = 32_000
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/console.css": ("console.css", "text/css; charset=utf-8"),
    "/console.js": ("console.js", "text/javascript; charset=utf-8"),
    "/thinking-indicator.css": ("thinking-indicator.css", "text/css; charset=utf-8"),
    "/thinking-indicator.js": ("thinking-indicator.js", "text/javascript; charset=utf-8"),
    "/watch-indicator.svg": ("watch-indicator.svg", "image/svg+xml"),
}
AgentFactory = Callable[..., Any]
StreamEmitter = Callable[[dict[str, Any]], None]


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
        task, config = self._prepare_run(payload)
        events: list[dict[str, Any]] = []

        def audit(event: str, fields: dict[str, Any]) -> None:
            events.append({"event": event, **fields})

        result = self._execute(task, config, audit)
        return {
            "ok": True,
            "result": result,
            "thinking": config.thinking_level,
            "events": events,
        }

    def run_stream(self, payload: Any, emit: StreamEmitter) -> None:
        """Run one agent and emit credential-safe NDJSON records as work happens."""

        task, config = self._prepare_run(payload)
        event_count = 0

        def audit(event: str, fields: dict[str, Any]) -> None:
            nonlocal event_count
            event_count += 1
            emit({"type": "event", "event": event, **fields})

        result = self._execute(
            task,
            config,
            audit,
            on_started=lambda: emit(
                {"type": "status", "state": "started", "thinking": config.thinking_level}
            ),
        )
        emit(
            {
                "type": "result",
                "result": result,
                "thinking": config.thinking_level,
                "event_count": event_count,
            }
        )

    def _prepare_run(self, payload: Any) -> tuple[str, AgentConfig]:
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
        return task.strip(), config

    def _execute(
        self,
        task: str,
        config: AgentConfig,
        audit: Callable[[str, dict[str, Any]], None],
        *,
        on_started: Callable[[], None] | None = None,
    ) -> str:
        if not self._run_lock.acquire(blocking=False):
            raise AgentBusyError("Another agent task is already running for this workspace.")
        try:
            if on_started is not None:
                on_started()
            agent = self.agent_factory(
                config,
                str(self.workspace),
                on_event=lambda _message: None,
                audit_sink=audit,
            )
            return agent.run_task(task)
        finally:
            self._run_lock.release()


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
        path = urlsplit(self.path).path
        if path == "/api/run-stream":
            self._stream_run()
            return
        if path != "/api/run":
            self._json_response(404, {"ok": False, "error": "Not found."})
            return
        try:
            payload = self._read_json_payload()
            result = self.server.application.run(payload)
            self._json_response(200, result)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            self._json_response(400, {"ok": False, "error": str(exc)})
        except ModelRequestError as exc:
            self._json_response(502, {"ok": False, "error": str(exc)})
        except AgentStepLimitError as exc:
            self._json_response(422, {"ok": False, "error": str(exc)})
        except AgentBusyError as exc:
            self._json_response(409, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._json_response(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    def _stream_run(self) -> None:
        started = False

        def emit(record: dict[str, Any]) -> None:
            nonlocal started
            if not started:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; connect-src 'self'; style-src 'self'; img-src 'self'",
                )
                self.send_header("Connection", "close")
                self.end_headers()
                started = True
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            self.wfile.write(line)
            self.wfile.flush()

        try:
            payload = self._read_json_payload()
            self.server.application.run_stream(payload, emit)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            self._stream_error(started, emit, 400, str(exc))
        except ModelRequestError as exc:
            self._stream_error(started, emit, 502, str(exc))
        except AgentStepLimitError as exc:
            self._stream_error(started, emit, 422, str(exc))
        except AgentBusyError as exc:
            self._stream_error(started, emit, 409, str(exc))
        except (BrokenPipeError, ConnectionResetError):
            # The browser closed the local page while the agent was streaming.
            pass
        except Exception as exc:
            self._stream_error(started, emit, 500, f"{type(exc).__name__}: {exc}")
        finally:
            self.close_connection = True

    def _stream_error(self, started: bool, emit: StreamEmitter, status: int, message: str) -> None:
        if started:
            try:
                emit({"type": "error", "status": status, "error": message})
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self._json_response(status, {"ok": False, "error": message})

    def _read_json_payload(self) -> Any:
        raw_length = self.headers.get("Content-Length", "")
        length = int(raw_length)
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValueError(f"Request body must be 1..{MAX_REQUEST_BYTES} bytes.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

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
