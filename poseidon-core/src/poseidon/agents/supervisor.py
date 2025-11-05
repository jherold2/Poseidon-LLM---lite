"""Command-line supervisor for routing prompts to domain agents."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict

from poseidon.workflows.hierarchical_graph import SupervisorWorkflow
from poseidon.agents.registry import AgentRegistry

try:
    from poseidon.workflows.master_pipeline import master_workflow
except ImportError:  # pragma: no cover - optional workflow
    master_workflow = None


def _available_modules() -> Dict[str, callable]:
    return AgentRegistry._agents  # type: ignore[attr-defined]


def route_once(supervisor: SupervisorWorkflow, module: str, prompt: str, session_id: str) -> None:
    payload = {"input": prompt, "session_id": session_id}
    result = supervisor.route_query(module, payload)
    print(json.dumps({"module": module, "response": result}, indent=2, ensure_ascii=False))


def run_workflow(supervisor: SupervisorWorkflow, workflow_name: str) -> None:
    if workflow_name == "master" and master_workflow is not None:
        results = supervisor.execute_workflow(master_workflow)
    else:
        raise ValueError(f"Unknown workflow '{workflow_name}'")
    print(json.dumps({"workflow": workflow_name, "results": results}, indent=2, ensure_ascii=False))


def interactive_loop(supervisor: SupervisorWorkflow) -> None:
    print("Interactive supervisor shell. Type 'exit' to quit.")
    session_id = "interactive"
    modules = list(_available_modules().keys())
    print(f"Available modules: {', '.join(modules)}")
    while True:
        module = input("Module> ").strip()
        if module.lower() in {"exit", "quit"}:
            break
        if module not in modules:
            print("Unknown module. Try again.")
            continue
        prompt = input("Prompt> ").strip()
        if prompt.lower() in {"exit", "quit"}:
            break
        route_once(supervisor, module, prompt, session_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Supervisor agent CLI")
    sub = parser.add_subparsers(dest="command")

    route_parser = sub.add_parser("route", help="Route a single prompt to an agent")
    route_parser.add_argument("module", help="Agent module name (e.g., sales, purchasing)")
    route_parser.add_argument("prompt", help="User prompt to send")
    route_parser.add_argument("--session", default="cli", help="Session identifier")

    workflow_parser = sub.add_parser("workflow", help="Execute a predefined workflow")
    workflow_parser.add_argument("name", help="Workflow name (e.g., master)")

    sub.add_parser("list", help="List available agent modules")

    sub.add_parser("interactive", help="Start an interactive shell")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    supervisor = SupervisorWorkflow()

    if args.command == "route":
        route_once(supervisor, args.module, args.prompt, args.session)
    elif args.command == "workflow":
        run_workflow(supervisor, args.name)
    elif args.command == "list":
        print(json.dumps({"modules": list(_available_modules().keys())}, indent=2))
    else:
        interactive_loop(supervisor)


if __name__ == "__main__":
    main(sys.argv[1:])
