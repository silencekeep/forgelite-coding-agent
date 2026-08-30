# Todo App

A tiny command‑line todo manager written in pure Python (standard library only).

## Features
- **add** `<description>` – add a new todo item.
- **list** – show all todos with their status.
- **done** `<id>` – mark a todo as completed.
- Data persisted in a `todos.json` file in the current working directory.
- Proper argument validation and non‑zero exit codes on errors.

## Usage
```bash
# Add a task
python -m todo_app add "Buy milk"

# List tasks
python -m todo_app list

# Mark a task as done (use the numeric ID shown by list)
python -m todo_app done 1
```

## Running the tests
The project includes a unittest suite.
```bash
python -m unittest discover -s tests -v
```
All tests should pass.
