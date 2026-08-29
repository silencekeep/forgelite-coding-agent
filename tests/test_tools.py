from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from coding_agent.tools import WorkspaceTools


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.tools = WorkspaceTools(self.root, command_timeout_seconds=5)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_write_read_and_exact_replace(self) -> None:
        written = self.tools.execute("write_file", {"path": "src/example.txt", "content": "one\ntwo\n"})
        self.assertTrue(written.ok)
        read = self.tools.execute("read_file", {"path": "src/example.txt"})
        self.assertIn("    1: one", read.output)
        edited = self.tools.execute(
            "replace_in_file", {"path": "src/example.txt", "old_text": "two", "new_text": "three"}
        )
        self.assertTrue(edited.ok)
        self.assertEqual((self.root / "src/example.txt").read_text(encoding="utf-8"), "one\nthree\n")

    def test_path_escape_is_rejected(self) -> None:
        result = self.tools.execute("read_file", {"path": "../outside.txt"})
        self.assertFalse(result.ok)
        self.assertIn("escapes", result.output)

    def test_model_argument_aliases_are_accepted(self) -> None:
        (self.root / "notes.txt").write_text("alpha\nbeta\n", encoding="utf-8")
        result = self.tools.execute("read_file", {"path": "notes.txt", "line_start": 2, "line_end": 2})
        self.assertTrue(result.ok)
        self.assertIn("    2: beta", result.output)
        listing = self.tools.execute("list_files", {"path": "", "max_entries": 1000})
        self.assertTrue(listing.ok)
        self.assertIn("notes.txt", listing.output)

    def test_recursive_delete_is_blocked(self) -> None:
        result = self.tools.execute("run_command", {"command": "rmdir /s /q anything"})
        self.assertFalse(result.ok)
        self.assertIn("blocked", result.output)

