from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from coding_agent.agent import CodingAgent
from coding_agent.audit import JsonlAuditLog
from coding_agent.config import AgentConfig
from coding_agent.history import compact_history
from coding_agent.lru_memory import LruWorkingMemory
from coding_agent.tools import ToolResult


class LruMemoryTests(unittest.TestCase):
    def test_eviction_refresh_and_render(self) -> None:
        memory = LruWorkingMemory(capacity=2, observation_limit=80)
        memory.observe("read_file", {"path": "old.py"}, ToolResult(True, "old content"))
        memory.observe("read_file", {"path": "keep.py"}, ToolResult(True, "keep v1"))
        memory.observe("read_file", {"path": "old.py"}, ToolResult(True, "old refreshed"))
        memory.observe("read_file", {"path": "new.py"}, ToolResult(True, "new content"))
        rendered = memory.render(1_000)
        self.assertNotIn("keep.py", rendered)
        self.assertIn("old.py", rendered)
        self.assertIn("new.py", rendered)

    def test_history_is_compacted(self) -> None:
        messages = [{"role": "system", "content": "rules"}]
        messages.extend({"role": "user", "content": f"turn-{index} " + "x" * 900} for index in range(6))
        compacted = compact_history(messages, 2_500)
        self.assertLessEqual(sum(len(str(message)) for message in compacted), 3_000)
        self.assertTrue(any("Earlier activity" in str(message.get("content")) for message in compacted))
        self.assertIn("turn-5", str(compacted[-1]))

    def test_history_never_keeps_an_orphaned_tool_result(self) -> None:
        messages = [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "older task " + "x" * 900},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call-old", "function": {"name": "read_file", "arguments": '{"path":"old.py"}'}}
                ],
            },
            {"role": "tool", "tool_call_id": "call-old", "content": "old file " + "y" * 900},
            {"role": "user", "content": "latest task " + "z" * 900},
        ]
        compacted = compact_history(messages, 2_000)
        call_ids = {
            call["id"]
            for message in compacted
            if message.get("role") == "assistant"
            for call in message.get("tool_calls", [])
        }
        for message in compacted:
            if message.get("role") == "tool":
                self.assertIn(message["tool_call_id"], call_ids)


class ScriptedClient:
    def __init__(self) -> None:
        self.requests: list[list[dict]] = []
        self.responses = [
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "list_files", "arguments": '{"path":".","max_entries":20}'},
                                }
                            ],
                        }
                    }
                ]
            },
            {"choices": [{"message": {"content": "Inspection complete."}}]},
        ]

    def complete(self, messages, tools):
        self.requests.append(messages)
        return self.responses.pop(0)


class AgentLoopTests(unittest.TestCase):
    def test_tool_loop_and_lru_context(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            client = ScriptedClient()
            config = AgentConfig("not-used", "http://example.invalid/v1", "fake", 3, 8_000, 5, 3)
            agent = CodingAgent(config, root, client=client)
            final = agent.run_task("Inspect this workspace.")
        self.assertEqual(final, "Inspection complete.")
        self.assertEqual(len(client.requests), 2)
        self.assertTrue(any("Recent workspace memory" in str(message.get("content")) for message in client.requests[1]))

    def test_audit_events_exclude_task_and_file_content(self) -> None:
        events: list[tuple[str, dict]] = []
        with tempfile.TemporaryDirectory() as root:
            client = ScriptedClient()
            config = AgentConfig("not-used", "http://example.invalid/v1", "fake", 3, 8_000, 5, 3)
            agent = CodingAgent(config, root, client=client, audit_sink=lambda event, fields: events.append((event, fields)))
            agent.run_task("Secret task text must not be written to audit.")
        rendered = json.dumps(events)
        self.assertIn("run_started", rendered)
        self.assertIn("tool_called", rendered)
        self.assertIn("run_finished", rendered)
        self.assertNotIn("Secret task text", rendered)
        self.assertNotIn("Inspection complete", rendered)

    def test_jsonl_audit_log_is_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "audit.jsonl"
            sink = JsonlAuditLog(path)
            sink("tool_finished", {"tool": "read_file", "ok": True})
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[0]["event"], "tool_finished")
        self.assertEqual(records[0]["tool"], "read_file")

    def test_one_run_creates_and_verifies_a_small_project(self) -> None:
        """Exercise the full local loop on a fresh workspace without a network model.

        The scripted responses use exactly the same OpenAI tool-call shape as a
        model response.  This proves the agent can sequence planning output,
        multi-file creation, command execution, tool results, and finalization.
        """
        app = '''def add(left: int, right: int) -> int:\n    return left + right\n'''
        test = (
            "import unittest\n\nfrom calculator import add\n\n\n"
            "class CalculatorTests(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
        )
        readme = "# Calculator\n\nRun: `python -m unittest discover -s tests -v`.\n"
        first_response = {
            "choices": [
                {
                    "message": {
                        "content": "I will create the implementation, test, and instructions.",
                        "tool_calls": [
                            {
                                "id": "write-app",
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": json.dumps({"path": "calculator.py", "content": app}),
                                },
                            },
                            {
                                "id": "write-test",
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": json.dumps({"path": "tests/test_calculator.py", "content": test}),
                                },
                            },
                            {
                                "id": "write-readme",
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": json.dumps({"path": "README.md", "content": readme}),
                                },
                            },
                        ],
                    }
                }
            ]
        }
        verify_response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "run-tests",
                                "type": "function",
                                "function": {
                                    "name": "run_command",
                                    "arguments": '{"command":"python -m unittest discover -s tests -v"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        final_response = {"choices": [{"message": {"content": "Created and verified the calculator project."}}]}

        with tempfile.TemporaryDirectory() as root:
            client = ScriptedClient()
            client.responses = [first_response, verify_response, final_response]
            config = AgentConfig("not-used", "http://example.invalid/v1", "fake", 5, 8_000, 10, 4, "high")
            agent = CodingAgent(config, root, client=client)
            final = agent.run_task("Build a small calculator project from scratch.")
            self.assertEqual(final, "Created and verified the calculator project.")
            self.assertEqual((Path(root) / "calculator.py").read_text(encoding="utf-8"), app)
            self.assertTrue((Path(root) / "tests/test_calculator.py").is_file())
            self.assertTrue((Path(root) / "README.md").is_file())
            tool_outputs = [message["content"] for message in agent.messages if message.get("role") == "tool"]
            self.assertTrue(any('"exit_code=0' in output for output in tool_outputs))
