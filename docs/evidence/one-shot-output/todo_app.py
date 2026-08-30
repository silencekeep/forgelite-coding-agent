#!/usr/bin/env python3
"""Simple command-line todo manager using only the Python standard library.

Supported subcommands:
  add <task description>   Add a new todo item.
  list                     List all todo items.
  done <id>                Mark the todo with the given ID as completed.

Data is persisted in a JSON file named ``todos.json`` in the current working
directory.  The file contains a list of objects with the keys ``id`` (int),
``task`` (str) and ``done`` (bool).

The script exits with a non‑zero status code for any error (e.g. missing
arguments, unknown subcommand, or an ID that does not exist) and prints a clear
error message to ``stderr``.
"""

import argparse
import json
import os
import sys
from typing import List, Dict

DATA_FILE = "todos.json"


def load_todos() -> List[Dict]:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading {DATA_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


def save_todos(todos: List[Dict]) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"Error writing {DATA_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


def add_task(task: str) -> None:
    if not task.strip():
        print("Task description cannot be empty.", file=sys.stderr)
        sys.exit(1)
    todos = load_todos()
    next_id = max((item["id"] for item in todos), default=0) + 1
    todos.append({"id": next_id, "task": task, "done": False})
    save_todos(todos)
    print(f"Added todo #{next_id}.")


def list_tasks() -> None:
    todos = load_todos()
    if not todos:
        print("No todos.")
        return
    for item in todos:
        status = "x" if item["done"] else " "
        print(f"{item['id']}. [{status}] {item['task']}")


def mark_done(task_id: str) -> None:
    try:
        tid = int(task_id)
    except ValueError:
        print(f"Invalid ID '{task_id}'. ID must be an integer.", file=sys.stderr)
        sys.exit(1)
    todos = load_todos()
    for item in todos:
        if item["id"] == tid:
            if item["done"]:
                print(f"Todo #{tid} is already marked as done.")
            else:
                item["done"] = True
                save_todos(todos)
                print(f"Marked todo #{tid} as done.")
            return
    print(f"Todo with ID {tid} not found.", file=sys.stderr)
    sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todo_app", description="Simple todo manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add command
    parser_add = subparsers.add_parser("add", help="Add a new todo")
    parser_add.add_argument("task", nargs=argparse.REMAINDER, help="Task description")

    # list command
    subparsers.add_parser("list", help="List all todos")

    # done command
    parser_done = subparsers.add_parser("done", help="Mark a todo as completed")
    parser_done.add_argument("id", help="ID of the todo to mark as done")

    return parser


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "add":
        # ``task`` may be a list of words; join them back into a string.
        task_str = " ".join(args.task).strip()
        if not task_str:
            print("Missing task description.", file=sys.stderr)
            sys.exit(1)
        add_task(task_str)
    elif args.command == "list":
        list_tasks()
    elif args.command == "done":
        mark_done(args.id)
    else:
        # This should never happen because argparse enforces choices.
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
