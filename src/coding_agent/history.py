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
    tail_groups: list[list[dict[str, Any]]] = []
    tail_size = 0
    groups = _message_groups(rest)
    for group in reversed(groups):
        group_size = _size(group)
        if tail_size + group_size > tail_limit:
            break
        tail_groups.insert(0, group)
        tail_size += group_size
    tail = [message for group in tail_groups for message in group]
    older_group_count = len(groups) - len(tail_groups)
    older = [message for group in groups[:older_group_count] for message in group]
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


def _message_groups(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Keep each tool-call exchange intact when trimming the conversation.

    OpenAI-compatible APIs require every ``role=tool`` message to follow the
    assistant message that introduced the corresponding call.  A naïve recency
    slice can retain only the tool result and produce an invalid request after a
    long coding task, so this function treats the entire exchange as one group.
    """
    groups: list[list[dict[str, Any]]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        group = [message]
        index += 1
        if message.get("role") == "assistant" and message.get("tool_calls"):
            while index < len(messages) and messages[index].get("role") == "tool":
                group.append(messages[index])
                index += 1
        groups.append(group)
    return groups


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
