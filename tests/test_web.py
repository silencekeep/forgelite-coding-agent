from __future__ import annotations

import json
import os
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from unittest.mock import patch

from coding_agent.agent import AgentStepLimitError
from coding_agent.web import AgentBusyError, ConsoleApplication, ConsoleServer


class FakeAgent:
    last_config = None

    def __init__(self, config, workspace, on_event, audit_sink):
        FakeAgent.last_config = config
        self.audit_sink = audit_sink

    def run_task(self, task):
        self.audit_sink("run_started", {"task_characters": len(task)})
        self.audit_sink("tool_called", {"tool": "list_files"})
        self.audit_sink("run_finished", {"outcome": "model_final"})
        return "Fake task completed."


class StepLimitedAgent(FakeAgent):
    def run_task(self, task):
        raise AgentStepLimitError("Stopped at the configured limit.")


class ConsoleApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "CODING_AGENT_API_KEY": "test-key",
                "CODING_AGENT_MAX_STEPS": "",
                "CODING_AGENT_CONTEXT_CHARS": "",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.application = ConsoleApplication(".", agent_factory=FakeAgent)

    def test_thinking_selection_reaches_real_agent_configuration(self) -> None:
        response = self.application.run({"task": "Inspect the project.", "thinking": "high"})
        self.assertTrue(response["ok"])
        self.assertEqual(response["thinking"], "high")
        self.assertEqual(FakeAgent.last_config.max_steps, 28)
        self.assertEqual(response["events"][-1]["outcome"], "model_final")

    def test_invalid_payloads_are_rejected(self) -> None:
        for payload in (None, {}, {"task": ""}, {"task": "ok", "thinking": "extreme"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.application.run(payload)

    def test_second_run_is_rejected_while_workspace_is_busy(self) -> None:
        self.application._run_lock.acquire()
        try:
            with self.assertRaises(AgentBusyError):
                self.application.run({"task": "Do not race.", "thinking": "medium"})
        finally:
            self.application._run_lock.release()

    def test_http_console_serves_assets_and_runs_task(self) -> None:
        server = ConsoleServer(("127.0.0.1", 0), self.application)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        opener = build_opener(ProxyHandler({}))
        base = f"http://127.0.0.1:{server.server_port}"

        with opener.open(base + "/", timeout=5) as response:
            html = response.read().decode("utf-8")
            self.assertIn("ForgeLite", html)
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        with opener.open(base + "/console.css", timeout=5) as response:
            self.assertIn("text/css", response.headers["Content-Type"])
            self.assertIn(".result-grid", response.read().decode("utf-8"))

        body = json.dumps({"task": "Build it.", "thinking": "low"}).encode("utf-8")
        request = Request(base + "/api/run", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with opener.open(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["result"], "Fake task completed.")
        self.assertEqual(payload["thinking"], "low")

    def test_http_console_reports_step_limit_as_non_success(self) -> None:
        application = ConsoleApplication(".", agent_factory=StepLimitedAgent)
        server = ConsoleServer(("127.0.0.1", 0), application)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        opener = build_opener(ProxyHandler({}))
        body = json.dumps({"task": "Keep going.", "thinking": "medium"}).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/run",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            opener.open(request, timeout=5)
        self.assertEqual(raised.exception.code, 422)
        payload = json.loads(raised.exception.read().decode("utf-8"))
        self.assertFalse(payload["ok"])
        self.assertIn("configured limit", payload["error"])


if __name__ == "__main__":
    unittest.main()
