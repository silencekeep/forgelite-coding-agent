"""Command-line interface for the local coding agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent import CodingAgent
from .client import ModelRequestError
from .config import AgentConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coding-agent",
        description="A small framework-free coding agent using an OpenAI-compatible tool-calling API.",
    )
    parser.add_argument("--workspace", default=".", help="Directory the agent may read, write and use as command CWD.")
    parser.add_argument("--task", help="Run one task and exit. Without it, start an interactive conversation.")
    parser.add_argument("--model", help="Override CODING_AGENT_MODEL for this run.")
    parser.add_argument(
        "--thinking",
        choices=("low", "medium", "high"),
        help="Reasoning profile. It changes the local planning prompt and default turn/context budgets.",
    )
    parser.add_argument("--max-steps", type=int, help="Override CODING_AGENT_MAX_STEPS for this run.")
    parser.add_argument("--quiet", action="store_true", help="Hide per-step tool progress.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_steps is not None and args.max_steps <= 0:
        print("--max-steps must be positive.", file=sys.stderr)
        return 2
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(f"Workspace is not a directory: {workspace}", file=sys.stderr)
        return 2
    try:
        config = AgentConfig.from_environment(
            model_override=args.model,
            max_steps_override=args.max_steps,
            thinking_override=args.thinking,
        )
        agent = CodingAgent(config, str(workspace), on_event=(lambda text: None) if args.quiet else print)
        if not args.quiet:
            print(
                f"Thinking: {config.thinking_level} | max steps: {config.max_steps} | "
                f"context budget: {config.context_char_budget} chars"
            )
        if args.task:
            _print_result(agent.run_task(args.task))
            return 0
        return _repl(agent, workspace)
    except (ValueError, ModelRequestError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


def _repl(agent: CodingAgent, workspace: Path) -> int:
    print(f"Local Coding Agent | workspace: {workspace}")
    print("Enter a programming task. Type /exit to quit. Conversation context persists for this session.")
    while True:
        try:
            task = input("\nYou> ").strip()
        except EOFError:
            print()
            return 0
        if task.lower() in {"/exit", "exit", "quit"}:
            return 0
        if not task:
            continue
        try:
            _print_result(agent.run_task(task))
        except (ValueError, ModelRequestError) as exc:
            print(f"Error: {exc}", file=sys.stderr)


def _print_result(result: str) -> None:
    print("\nAgent> " + result)


if __name__ == "__main__":
    raise SystemExit(main())
