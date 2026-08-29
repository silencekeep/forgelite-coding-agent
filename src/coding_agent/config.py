"""Configuration loading. Secrets deliberately live only in the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .thinking import get_profile


@dataclass(frozen=True)
class AgentConfig:
    api_key: str
    base_url: str
    model: str
    max_steps: int
    context_char_budget: int
    command_timeout_seconds: int
    lru_memory_items: int
    thinking_level: str = "medium"

    @classmethod
    def from_environment(
        cls,
        *,
        model_override: str | None = None,
        max_steps_override: int | None = None,
        thinking_override: str | None = None,
    ) -> "AgentConfig":
        """Read non-secret defaults and the API key from environment variables."""
        api_key = os.getenv("CODING_AGENT_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "Missing CODING_AGENT_API_KEY. Set it in your shell; never put it in a file."
            )

        thinking_level = thinking_override or os.getenv("CODING_AGENT_THINKING", "medium")
        profile = get_profile(thinking_level)
        return cls(
            api_key=api_key,
            base_url=os.getenv("CODING_AGENT_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=model_override or os.getenv("CODING_AGENT_MODEL", "gpt-4.1-mini"),
            max_steps=max_steps_override or _optional_positive_int("CODING_AGENT_MAX_STEPS") or profile.max_steps,
            context_char_budget=(
                _optional_positive_int("CODING_AGENT_CONTEXT_CHARS") or profile.context_char_budget
            ),
            command_timeout_seconds=_positive_int("CODING_AGENT_COMMAND_TIMEOUT", 30),
            lru_memory_items=_positive_int("CODING_AGENT_LRU_MEMORY_ITEMS", 12),
            thinking_level=profile.name.lower(),
        )


def _positive_int(variable: str, default: int) -> int:
    raw = os.getenv(variable, "")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{variable} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"{variable} must be positive.")
    return value


def _optional_positive_int(variable: str) -> int | None:
    raw = os.getenv(variable, "")
    return _positive_int(variable, 1) if raw else None
