from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from coding_agent.config import AgentConfig
from coding_agent.thinking import get_profile


class ThinkingProfileTests(unittest.TestCase):
    def test_profiles_have_increasing_budgets(self) -> None:
        low, medium, high = (get_profile(level) for level in ("low", "medium", "high"))
        self.assertLess(low.max_steps, medium.max_steps)
        self.assertLess(medium.max_steps, high.max_steps)
        self.assertLess(low.context_char_budget, high.context_char_budget)

    def test_profile_supplies_defaults_but_explicit_limit_wins(self) -> None:
        environment = {"CODING_AGENT_API_KEY": "test-key", "CODING_AGENT_THINKING": "high"}
        with patch.dict(os.environ, environment, clear=True):
            config = AgentConfig.from_environment(max_steps_override=5)
        self.assertEqual(config.thinking_level, "high")
        self.assertEqual(config.max_steps, 5)
        self.assertEqual(config.context_char_budget, get_profile("high").context_char_budget)
