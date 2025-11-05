"""High-level orchestration utilities built on top of the Supervisor workflow.

This module keeps the orchestration logic thin so it can be reused by the CLI,
Streamlit UI, or background schedulers.  It delegates all routing decisions to
:class:`poseidon.workflows.hierarchical_graph.SupervisorWorkflow` and reuses the
``master_workflow`` definition for default smoke tests.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Mapping, Optional

from poseidon.workflows.hierarchical_graph import SupervisorWorkflow
from poseidon.workflows.master_pipeline import master_workflow

logger = logging.getLogger(__name__)

DEFAULT_SESSION_ID = "orchestrator"


def run_workflow(
    workflow: Optional[Iterable[Mapping[str, str]]] = None,
    *,
    supervisor: Optional[SupervisorWorkflow] = None,
    session_id: str = DEFAULT_SESSION_ID,
) -> List[dict]:
    """Execute a sequence of workflow steps through the supervisor.

    Args:
        workflow: iterable of ``{"module": str, "input": str, "session_id": str}``.
            If omitted, :data:`master_workflow` is used.
        supervisor: optional pre-initialised :class:`SupervisorWorkflow`.  A new
            instance is created when ``None``.
        session_id: default session identifier for steps that do not specify one.

    Returns:
        List of dictionaries containing the module, input, and supervisor response.
    """

    steps = list(workflow or master_workflow)
    engine = supervisor or SupervisorWorkflow()
    results: List[dict] = []

    logger.info("Starting orchestration run with %d steps", len(steps))

    for index, step in enumerate(steps, start=1):
        module = step.get("module")
        prompt = step.get("input")
        step_session = step.get("session_id", session_id)

        if not module or not prompt:
            logger.warning("Skipping step %d due to missing module or input", index)
            continue

        payload = {"input": prompt, "session_id": step_session}
        logger.debug("Dispatching step %d to module '%s'", index, module)
        response = engine.route_query(module, payload)
        results.append({"module": module, "input": prompt, "session_id": step_session, "response": response})

    logger.info("Completed orchestration run: %d steps processed", len(results))
    return results


def run_cli() -> None:
    """Helper entrypoint for ``python -m poseidon.workflows.orchestrator_pipeline``."""
    for record in run_workflow():
        module = record["module"]
        logger.info("[%s] %s", module, record["response"])


if __name__ == "__main__":  # pragma: no cover - manual execution convenience
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run_cli()
