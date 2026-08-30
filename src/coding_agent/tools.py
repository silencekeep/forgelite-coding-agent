"""Local tool definitions and their deliberately small implementation surface."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable


MAX_FILE_BYTES = 200_000
MAX_COMMAND_OUTPUT = 12_000
MAX_LIST_OUTPUT = 12_000


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories below the workspace. Use before reading unfamiliar paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory path, default is workspace root."},
                    "max_entries": {"type": "integer", "minimum": 1, "maximum": 500},
                    "recursive": {
                        "type": "boolean",
                        "description": "List all descendants when true. Default false lists only the current directory.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Search UTF-8 text files inside the workspace for a literal string. Returns path, line number and a short matching line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Non-empty literal text to find."},
                    "path": {"type": "string", "description": "Relative file or directory, default workspace root."},
                    "file_pattern": {"type": "string", "description": "Optional glob such as *.py, default *."},
                    "case_sensitive": {"type": "boolean", "description": "Default false."},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the workspace, with 1-based optional line bounds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or replace a UTF-8 text file inside the workspace. Parent directories are created.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": "Replace exactly one occurrence of old_text with new_text in a UTF-8 text file. Safer than rewriting a large file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a development command inside the workspace, returning exit code and combined output. Do not start servers or use destructive commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass
class ToolResult:
    ok: bool
    output: str

    def as_json(self) -> str:
        return json.dumps({"ok": self.ok, "output": self.output}, ensure_ascii=False)


class WorkspaceTools:
    """The only bridge between the model and this machine.

    Every file path is resolved against ``root`` before use. Command execution also
    uses that directory as its working directory, but commands remain powerful:
    users should point the agent at a disposable project directory when possible.
    """

    def __init__(self, root: str | Path, command_timeout_seconds: int = 30) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace does not exist or is not a directory: {self.root}")
        self.command_timeout_seconds = command_timeout_seconds
        self._handlers: dict[str, Callable[..., ToolResult]] = {
            "list_files": self.list_files,
            "search_text": self.search_text,
            # Compatibility alias for models that emit the generic name despite
            # receiving the more explicit search_text schema.
            "search": self.search_text,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "replace_in_file": self.replace_in_file,
            "run_command": self.run_command,
        }

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(False, f"Unknown tool: {name}")
        try:
            return handler(**self.normalize_arguments(name, arguments))
        except TypeError as exc:
            return ToolResult(False, f"Invalid arguments for {name}: {exc}")
        except (OSError, ValueError, UnicodeError) as exc:
            return ToolResult(False, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def normalize_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Tolerate common native-tool-call dialects without weakening tool scope."""
        normalized = dict(arguments)
        if name == "read_file":
            if "line_start" in normalized and "start_line" not in normalized:
                normalized["start_line"] = normalized.pop("line_start")
            if "line_end" in normalized and "end_line" not in normalized:
                normalized["end_line"] = normalized.pop("line_end")
        if name in {"list_files", "search", "search_text"}:
            if normalized.get("path") == "":
                normalized["path"] = "."
        if name == "list_files":
            # A few OpenAI-compatible models habitually request 1,000 entries.
            # It is still bounded, and a larger listing prevents needless repair turns.
            if normalized.get("max_entries") == 1000:
                normalized["max_entries"] = 500
        return normalized

    def _resolve(self, relative_path: str) -> Path:
        if not relative_path or Path(relative_path).is_absolute():
            raise ValueError("Path must be a non-empty relative path.")
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Path escapes the configured workspace.") from exc
        return candidate

    def list_files(self, path: str = ".", max_entries: int = 200, recursive: bool = False) -> ToolResult:
        if not 1 <= max_entries <= 500:
            raise ValueError("max_entries must be between 1 and 500.")
        directory = self.root if path == "." else self._resolve(path)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {path}")
        entries: list[str] = []
        used_characters = 0
        truncated = False
        candidates = directory.rglob("*") if recursive else directory.iterdir()
        for item in sorted(candidates, key=lambda p: str(p).lower()):
            try:
                relative = item.relative_to(self.root)
            except ValueError:
                continue
            if any(part in {".git", "__pycache__", ".venv", "node_modules"} for part in relative.parts):
                continue
            suffix = "/" if item.is_dir() else ""
            rendered = relative.as_posix() + suffix
            if used_characters + len(rendered) + 1 > MAX_LIST_OUTPUT:
                truncated = True
                break
            entries.append(rendered)
            used_characters += len(rendered) + 1
            if len(entries) >= max_entries:
                truncated = True
                break
        if not entries:
            return ToolResult(True, "(empty)")
        tail = "\n[truncated; use a narrower path or recursive=false]" if truncated else ""
        return ToolResult(True, "\n".join(entries) + tail)

    def search_text(
        self,
        query: str,
        path: str = ".",
        file_pattern: str = "*",
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> ToolResult:
        if not query:
            raise ValueError("query must not be empty.")
        if not 1 <= max_results <= 200:
            raise ValueError("max_results must be between 1 and 200.")
        location = self.root if path == "." else self._resolve(path)
        if not location.exists():
            raise ValueError(f"Path does not exist: {path}")
        candidates = [location] if location.is_file() else location.rglob("*")
        needle = query if case_sensitive else query.casefold()
        matches: list[str] = []
        used_characters = 0
        truncated = False
        for candidate in sorted(candidates, key=lambda item: str(item).lower()):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(self.root)
            if any(part in {".git", "__pycache__", ".venv", "node_modules"} for part in relative.parts):
                continue
            try:
                candidate.resolve().relative_to(self.root)
            except (OSError, ValueError):
                # Do not follow a file symlink that points outside the workspace.
                continue
            if not fnmatch(relative.as_posix(), file_pattern) and not fnmatch(candidate.name, file_pattern):
                continue
            try:
                if candidate.stat().st_size > MAX_FILE_BYTES:
                    continue
                raw = candidate.read_bytes()
                if b"\x00" in raw:
                    continue
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                haystack = line if case_sensitive else line.casefold()
                if needle not in haystack:
                    continue
                compact_line = line.strip()[:300]
                rendered = f"{relative.as_posix()}:{line_number}: {compact_line}"
                if used_characters + len(rendered) + 1 > MAX_LIST_OUTPUT:
                    truncated = True
                    break
                matches.append(rendered)
                used_characters += len(rendered) + 1
                if len(matches) >= max_results:
                    truncated = True
                    break
            if truncated:
                break
        if not matches:
            return ToolResult(True, "(no matches)")
        tail = "\n[truncated; narrow path, pattern, or query]" if truncated else ""
        return ToolResult(True, "\n".join(matches) + tail)

    def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> ToolResult:
        target = self._resolve(path)
        if not target.is_file():
            raise ValueError(f"Not a file: {path}")
        if target.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"File exceeds {MAX_FILE_BYTES} byte read limit: {path}")
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        if start_line is not None and start_line < 1:
            raise ValueError("start_line must be at least 1.")
        if end_line is not None and end_line < 1:
            raise ValueError("end_line must be at least 1.")
        if start_line is not None and end_line is not None and start_line > end_line:
            raise ValueError("start_line must not exceed end_line.")
        start = (start_line - 1) if start_line else 0
        end = end_line if end_line else len(lines)
        body = "".join(lines[start:end])
        numbered = "".join(f"{line_no:>5}: {line}" for line_no, line in enumerate(body.splitlines(keepends=True), start + 1))
        return ToolResult(True, numbered or "(empty)")

    def write_file(self, path: str, content: str) -> ToolResult:
        target = self._resolve(path)
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"Content exceeds {MAX_FILE_BYTES} byte write limit.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".coding-agent-tmp")
        temporary.write_text(content, encoding="utf-8", newline="")
        temporary.replace(target)
        return ToolResult(True, f"Wrote {path} ({len(content.encode('utf-8'))} bytes).")

    def replace_in_file(self, path: str, old_text: str, new_text: str) -> ToolResult:
        if not old_text:
            raise ValueError("old_text must not be empty.")
        target = self._resolve(path)
        if not target.is_file():
            raise ValueError(f"Not a file: {path}")
        original = target.read_text(encoding="utf-8")
        count = original.count(old_text)
        if count != 1:
            raise ValueError(f"Expected old_text exactly once; found {count} occurrences.")
        changed = original.replace(old_text, new_text, 1)
        if len(changed.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"Replacement would exceed {MAX_FILE_BYTES} byte write limit.")
        temporary = target.with_name(target.name + ".coding-agent-tmp")
        temporary.write_text(changed, encoding="utf-8", newline="")
        temporary.replace(target)
        return ToolResult(True, f"Replaced text in {path}.")

    def run_command(self, command: str, timeout_seconds: int | None = None) -> ToolResult:
        if not command.strip():
            raise ValueError("command must not be empty.")
        timeout = timeout_seconds or self.command_timeout_seconds
        if not 1 <= timeout <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120.")
        blocked = _dangerous_command_reason(command)
        if blocked:
            return ToolResult(False, f"Command blocked: {blocked}")
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            output = _truncate(output)
            elapsed = time.monotonic() - started
            return ToolResult(
                completed.returncode == 0,
                f"exit_code={completed.returncode}; elapsed={elapsed:.2f}s\n{output or '(no output)'}",
            )
        except subprocess.TimeoutExpired as exc:
            partial = _truncate(((exc.stdout or "") + (exc.stderr or "")))
            return ToolResult(False, f"Timed out after {timeout}s.\n{partial or '(no output)'}")


def _truncate(output: str) -> str:
    if len(output) <= MAX_COMMAND_OUTPUT:
        return output
    return output[:MAX_COMMAND_OUTPUT] + "\n[output truncated]"


def _dangerous_command_reason(command: str) -> str | None:
    """Reject a narrow set of catastrophic patterns; this is not a security sandbox."""
    normalized = " ".join(command.lower().split())
    forbidden = {
        "rm -rf": "recursive Unix deletion is disabled",
        "rmdir /s": "recursive Windows deletion is disabled",
        "remove-item -recurse": "recursive PowerShell deletion is disabled",
        "del /s": "recursive Windows deletion is disabled",
        "format ": "disk formatting is disabled",
        "shutdown ": "system shutdown is disabled",
        "restart-computer": "system restart is disabled",
    }
    for pattern, explanation in forbidden.items():
        if pattern in normalized:
            return explanation
    return None
