from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from coding_agent.agent import AgentStepLimitError
from coding_agent.cli import main
from coding_agent.config import AgentConfig


class CommandLineTests(unittest.TestCase):
    def test_step_limit_returns_nonzero_exit_code(self) -> None:
        config = AgentConfig("unused", "http://example.invalid/v1", "fake", 1, 8_000, 5, 3)
        with tempfile.TemporaryDirectory() as workspace:
            with (
                patch("coding_agent.cli.AgentConfig.from_environment", return_value=config),
                patch("coding_agent.cli.CodingAgent") as agent_type,
                redirect_stderr(io.StringIO()) as stderr,
            ):
                agent_type.return_value.run_task.side_effect = AgentStepLimitError("step limit reached")
                exit_code = main(["--workspace", workspace, "--task", "Keep working.", "--quiet"])
        self.assertEqual(exit_code, 1)
        self.assertIn("step limit reached", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
