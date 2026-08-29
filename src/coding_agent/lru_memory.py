"""An LRU working memory used alongside chronological chat history.

Chat history answers "what happened in order?".  This tiny cache answers "which
workspace facts were touched most recently?".  It deliberately stores compact
observations, not hidden full file copies: a model must still use read_file before
making an edit based on stale content.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from .tools import ToolResult


@dataclass(frozen=True)
class MemoryItem:
    label: str
    observation: str


class LruWorkingMemory:
    """Bounded recency cache whose serialized form is safe to place in context."""

    def __init__(self, capacity: int = 12, observation_limit: int = 900) -> None:
        if capacity < 1:
            raise ValueError("LRU memory capacity must be positive.")
        self.capacity = capacity
        self.observation_limit = observation_limit
        self._items: OrderedDict[str, MemoryItem] = OrderedDict()

    def observe(self, tool_name: str, arguments: dict[str, Any], result: ToolResult) -> None:
        """Record only useful successful tool observations, refresh on repeat access."""
        if not result.ok:
            return
        key, label, observation = _to_memory_item(tool_name, arguments, result.output)
        if not key:
            return
        compact = _compact(observation, self.observation_limit)
        self._items.pop(key, None)
        self._items[key] = MemoryItem(label, compact)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def render(self, char_budget: int) -> str:
        """Return most-recent entries that fit, while retaining LRU eviction semantics."""
        if char_budget < 80 or not self._items:
            return ""
        heading = (
            "Recent workspace memory (LRU compacted; it is an aid, not source of truth. "
            "Read a file again before editing it):"
        )
        chosen: list[str] = []
        used = len(heading) + 1
        # Reverse iteration is MRU -> LRU.  Present chronologically within the
        # selected window so the oldest retained fact comes first.
        for item in reversed(self._items.values()):
            line = f"- {item.label}: {item.observation}"
            if used + len(line) + 1 > char_budget:
                break
            chosen.append(line)
            used += len(line) + 1
        if not chosen:
            return ""
        chosen.reverse()
        return heading + "\n" + "\n".join(chosen)

    def __len__(self) -> int:
        return len(self._items)


def _to_memory_item(tool_name: str, arguments: dict[str, Any], output: str) -> tuple[str, str, str]:
    path = str(arguments.get("path", ""))
    if tool_name == "read_file" and path:
        return f"file:{path}", f"read {path}", output
    if tool_name == "write_file" and path:
        return f"file:{path}", f"wrote {path}", output
    if tool_name == "replace_in_file" and path:
        return f"file:{path}", f"edited {path}", output
    if tool_name == "list_files":
        location = path or "."
        return f"listing:{location}", f"listed {location}", output
    if tool_name == "run_command":
        command = str(arguments.get("command", ""))
        return f"command:{command}", f"command `{command[:120]}`", output
    return "", "", ""


def _compact(text: str, limit: int) -> str:
    normalized = " ".join(text.replace("\n", " ").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + " …[compacted]"
