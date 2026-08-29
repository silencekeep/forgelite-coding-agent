"""The agent control loop: model call -> parsed local tools -> next model call."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .audit import AuditSink
from .client import ChatCompletionsClient
from .config import AgentConfig
from .history import compact_history
from .lru_memory import LruWorkingMemory
from .thinking import get_profile
from .tools import TOOL_SCHEMAS, WorkspaceTools


SYSTEM_PROMPT = """You are a careful local coding agent. You solve the user's programming task by inspecting and modifying only the configured workspace through the supplied tools.

Workflow: inspect relevant files first; make focused edits; run targeted verification; then give a concise final report. Do not claim tests passed unless run_command shows they passed. Do not use destructive commands, start long-running servers, access network credentials, or modify files outside the workspace. Ask the user when requirements are ambiguous or an action is irreversible. Tool output may be stale after compaction: read files again before relying on old content."""

EventCallback = Callable[[str], None]


class CodingAgent:
    """A single-agent executor with explicit, inspectable loop state."""

    def __init__(
        self,
        config: AgentConfig,
        workspace: str,
        on_event: EventCallback | None = None,
        audit_sink: AuditSink | None = None,
        client: ChatCompletionsClient | Any | None = None,
    ) -> None:
        self.config = config
        self.tools = WorkspaceTools(workspace, config.command_timeout_seconds)
        self.client = client or ChatCompletionsClient(config.api_key, config.base_url, config.model)
        self.on_event = on_event or (lambda _: None)
        self.audit_sink = audit_sink or (lambda _event, _fields: None)
        profile = get_profile(config.thinking_level)
        system_prompt = SYSTEM_PROMPT + f"\n\nThinking profile ({profile.name}): {profile.instruction}"
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        self.working_memory = LruWorkingMemory(config.lru_memory_items)

    def run_task(self, task: str) -> str:
        task = task.strip()
        if not task:
            raise ValueError("Task must not be empty.")
        self.messages.append({"role": "user", "content": task})
        self._audit(
            "run_started",
            thinking_level=self.config.thinking_level,
            max_steps=self.config.max_steps,
            context_char_budget=self.config.context_char_budget,
            task_characters=len(task),
        )

        for step in range(1, self.config.max_steps + 1):
            memory_budget = min(4_000, max(600, self.config.context_char_budget // 8))
            request_messages = compact_history(
                self.messages, max(2_000, self.config.context_char_budget - memory_budget)
            )
            memory = self.working_memory.render(memory_budget)
            if memory:
                request_messages.insert(1, {"role": "system", "content": memory})
            self.on_event(
                f"[step {step}/{self.config.max_steps} | thinking: {self.config.thinking_level}] "
                f"contacting {self.config.model}"
            )
            self._audit("model_request_started", step=step, message_count=len(request_messages))
            try:
                response = self.client.complete(request_messages, TOOL_SCHEMAS)
            except Exception as exc:
                self._audit("model_request_failed", step=step, error_type=type(exc).__name__)
                raise
            assistant = _assistant_message(response)
            self.messages.append(assistant)
            calls = assistant.get("tool_calls") or []
            if not calls:
                final = str(assistant.get("content") or "").strip()
                if final:
                    self._audit("run_finished", outcome="model_final", final_characters=len(final), steps_used=step)
                    return final
                self._audit("run_finished", outcome="empty_model_final", steps_used=step)
                return "The model ended without a textual conclusion. Inspect the workspace and tool log."

            for call in calls:
                tool_message = self._execute_call(call)
                self.messages.append(tool_message)

        stopped = (
            f"Stopped after the configured limit of {self.config.max_steps} model turns. "
            "The model may have made partial changes; inspect the workspace and rerun with a larger limit if appropriate."
        )
        self._audit("run_finished", outcome="step_limit", steps_used=self.config.max_steps)
        return stopped

    def _execute_call(self, call: dict[str, Any]) -> dict[str, str]:
        call_id = str(call.get("id") or "missing-tool-call-id")
        function = call.get("function")
        if not isinstance(function, dict):
            self._audit("tool_rejected", reason="malformed_tool_call")
            return {"role": "tool", "tool_call_id": call_id, "content": '{"ok": false, "output": "Malformed tool call."}'}
        name = str(function.get("name") or "")
        raw_arguments = function.get("arguments", "{}")
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            result = {"ok": False, "output": f"Invalid JSON arguments: {exc}"}
            self.on_event(f"  tool {name or '?'}: rejected malformed arguments")
            self._audit("tool_rejected", tool=name or "unknown", reason="invalid_json_arguments")
            return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)}

        self.on_event(f"  tool {name}({_safe_argument_preview(arguments)})")
        self._audit("tool_called", tool=name, argument_keys=sorted(arguments), has_path="path" in arguments)
        result = self.tools.execute(name, arguments)
        self.working_memory.observe(name, self.tools._normalize_arguments(name, arguments), result)
        marker = "ok" if result.ok else "error"
        self.on_event(f"  -> {marker}: {_first_line(result.output)}")
        self._audit(
            "tool_finished",
            tool=name,
            ok=result.ok,
            output_characters=len(result.output),
        )
        return {"role": "tool", "tool_call_id": call_id, "content": result.as_json()}

    def _audit(self, event: str, **fields: Any) -> None:
        self.audit_sink(event, fields)


def _assistant_message(response: dict[str, Any]) -> dict[str, Any]:
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Malformed model response: choices[0].message is missing.") from exc
    if not isinstance(message, dict):
        raise ValueError("Malformed model response: assistant message is not an object.")
    tool_calls = message.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        raise ValueError("Malformed model response: tool_calls is not a list.")
    return {
        "role": "assistant",
        "content": message.get("content") or "",
        **({"tool_calls": tool_calls} if tool_calls else {}),
    }


def _safe_argument_preview(arguments: dict[str, Any]) -> str:
    pairs: list[str] = []
    for key, value in arguments.items():
        if key == "content":
            pairs.append(f"content=<{len(str(value))} chars>")
        elif key in {"old_text", "new_text"}:
            pairs.append(f"{key}=<{len(str(value))} chars>")
        else:
            rendered = repr(value)
            pairs.append(f"{key}={rendered[:120]}")
    return ", ".join(pairs)


def _first_line(text: str) -> str:
    return text.splitlines()[0][:180] if text else "(no output)"
