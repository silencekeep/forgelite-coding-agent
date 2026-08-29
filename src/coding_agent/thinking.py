"""Reasoning profiles exposed as Low / Medium / High, with local effects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThinkingProfile:
    name: str
    max_steps: int
    context_char_budget: int
    instruction: str


PROFILES: dict[str, ThinkingProfile] = {
    "low": ThinkingProfile(
        name="Low",
        max_steps=8,
        context_char_budget=24_000,
        instruction="Work efficiently: inspect only what is needed, make focused changes, and verify once.",
    ),
    "medium": ThinkingProfile(
        name="Medium",
        max_steps=16,
        context_char_budget=48_000,
        instruction="Balance speed and care: inspect relevant files, make a small plan, edit, then verify the result.",
    ),
    "high": ThinkingProfile(
        name="High",
        max_steps=28,
        context_char_budget=80_000,
        instruction=(
            "Be deliberately thorough: inspect surrounding code and tests, consider alternative causes before editing, "
            "and run meaningful verification. Do not pad the task with unnecessary tool calls."
        ),
    ),
}


def get_profile(level: str) -> ThinkingProfile:
    try:
        return PROFILES[level.lower()]
    except KeyError as exc:
        choices = ", ".join(PROFILES)
        raise ValueError(f"Thinking level must be one of: {choices}.") from exc
