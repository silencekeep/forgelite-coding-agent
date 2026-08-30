from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coding_agent.tools import TOOL_SCHEMAS, WorkspaceTools


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

    def test_model_visible_tool_set_is_explicit(self) -> None:
        names = [schema["function"]["name"] for schema in TOOL_SCHEMAS]
        self.assertEqual(
            names,
            ["list_files", "search_text", "read_file", "write_file", "replace_in_file", "run_command"],
        )

    def test_large_read_is_truncated_with_narrowing_guidance(self) -> None:
        content = "".join(f"line {index}: {'x' * 100}\n" for index in range(400))
        (self.root / "large.txt").write_text(content, encoding="utf-8")
        result = self.tools.execute("read_file", {"path": "large.txt"})
        self.assertTrue(result.ok)
        self.assertLess(len(result.output), len(content))
        self.assertIn("use start_line and end_line", result.output)

    def test_atomic_write_cleans_temporary_file_after_replace_failure(self) -> None:
        with patch("coding_agent.tools.os.replace", side_effect=OSError("simulated replace failure")):
            result = self.tools.execute("write_file", {"path": "target.txt", "content": "new content"})
        self.assertFalse(result.ok)
        self.assertIn("simulated replace failure", result.output)
        self.assertEqual(list(self.root.glob("*.coding-agent-tmp")), [])

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

    def test_listing_is_shallow_by_default_and_recursive_on_request(self) -> None:
        (self.root / "nested").mkdir()
        (self.root / "nested" / "inside.txt").write_text("inside", encoding="utf-8")
        shallow = self.tools.execute("list_files", {"path": "."})
        recursive = self.tools.execute("list_files", {"path": ".", "recursive": True})
        self.assertIn("nested/", shallow.output)
        self.assertNotIn("inside.txt", shallow.output)
        self.assertIn("nested/inside.txt", recursive.output)

    def test_search_text_is_literal_bounded_and_filterable(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "first.py").write_text("Alpha.beta\nalpha beta\n", encoding="utf-8")
        (self.root / "src" / "ignored.txt").write_text("alpha.beta\n", encoding="utf-8")
        result = self.tools.execute(
            "search_text",
            {"query": "alpha.beta", "path": "src", "file_pattern": "*.py", "max_results": 1},
        )
        self.assertTrue(result.ok)
        self.assertIn("src/first.py:1: Alpha.beta", result.output)
        self.assertNotIn("ignored.txt", result.output)
        self.assertNotIn("alpha beta", result.output)
        self.assertIn("[truncated", result.output)

    def test_search_alias_and_case_sensitivity(self) -> None:
        (self.root / "notes.txt").write_text("Needle\nneedle\n", encoding="utf-8")
        result = self.tools.execute("search", {"query": "Needle", "path": "", "case_sensitive": True})
        self.assertTrue(result.ok)
        self.assertIn("notes.txt:1: Needle", result.output)
        self.assertNotIn("notes.txt:2", result.output)

    def test_search_path_escape_is_rejected(self) -> None:
        result = self.tools.execute("search_text", {"query": "secret", "path": ".."})
        self.assertFalse(result.ok)
        self.assertIn("escapes", result.output)

    def test_recursive_delete_is_blocked(self) -> None:
        result = self.tools.execute("run_command", {"command": "rmdir /s /q anything"})
        self.assertFalse(result.ok)
        self.assertIn("blocked", result.output)
