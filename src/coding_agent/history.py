"""Bounded conversation history, implemented locally rather than delegated to an API."""

from __future__ import annotations

from typing import Any


def compact_history(messages: list[dict[str, Any]], char_budget: int) -> list[dict[str, Any]]:
    """Keep the system prompt and newest exchanges within a predictable character budget.

    Older turns are converted to a small, deterministic activity record. This is
    intentionally local: it cannot make another model call, leak history, or hide
    an unbounded context window behind a framework abstraction.
    """
    if char_budget < 2_000:
        raise ValueError("char_budget must be at least 2000.")
    if _size(messages) <= char_budget:
        return messages
    system = [message for message in messages if message.get("role") == "system"][:1]
    rest = [message for message in messages if message.get("role") != "system"]
    available = char_budget - _size(system)
    # Reserve room for an old-turn activity record, rather than letting the most
    # recent verbose tool output consume the whole context budget.
    summary_reserve = min(1_500, max(300, available // 3))
    tail_limit = max(300, available - summary_reserve)
    tail: list[dict[str, Any]] = []
    tail_size = 0
    for message in reversed(rest):
        message_size = _size([message])
        if tail_size + message_size > tail_limit:
            break
        tail.insert(0, message)
        tail_size += message_size
    older = rest[: len(rest) - len(tail)]
    summary = _summarize(older)
    summary_limit = max(0, char_budget - _size(system) - tail_size - 40)
    if len(summary) > summary_limit:
        summary = summary[:summary_limit].rsplit("\n", 1)[0] + "\n- …[compacted]"
    compacted = [*system]
    if summary:
        compacted.append({"role": "system", "content": summary})
    compacted.extend(tail)
    return compacted


def _size(messages: list[dict[str, Any]]) -> int:
    return sum(len(str(message.get("content", ""))) + len(str(message.get("tool_calls", ""))) + 40 for message in messages)


def _summarize(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return ""
    lines = ["Earlier activity (locally compacted; inspect files again before changing them):"]
    for message in messages:
        role = message.get("role", "unknown")
        content = str(message.get("content") or "").replace("\n", " ").strip()
        if role == "assistant" and message.get("tool_calls"):
            names = ", ".join(call.get("function", {}).get("name", "?") for call in message["tool_calls"])
            content = f"called tools: {names}"
        if role == "tool":
            content = f"tool result: {content}"
        if content:
            lines.append(f"- {role}: {content[:280]}")
    return "\n".join(lines[:18])
