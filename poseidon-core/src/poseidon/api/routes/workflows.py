"""API endpoints for orchestrating Poseidon workflows."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from poseidon.agents.registry import AgentRegistry
from poseidon.observability import (
    create_workflow_run,
    log_application_event,
    log_user_action,
    update_workflow_run_status,
)
from poseidon.utils.logger_setup import LoggingContext
from poseidon.workflows.async_dispatcher import AsyncTaskDispatcher
from poseidon.workflows.hierarchical_graph import SupervisorWorkflow
from poseidon.workflows.master_pipeline import master_workflow


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowStep(BaseModel):
    module: str = Field(..., description="Registered module name.")
    input: str = Field(..., description="Prompt or instruction for the agent.")
    session_id: str | None = Field(None, description="Optional session scope.")


class WorkflowRunRequest(BaseModel):
    steps: List[WorkflowStep] = Field(
        default_factory=list,
        description="Optional explicit workflow steps; defaults to master workflow.",
    )
    use_master_workflow: bool = Field(
        False,
        description="Force execution of the default master workflow regardless of steps.",
    )


class WorkflowAsyncResponse(BaseModel):
    task_id: str = Field(..., description="Identifier for polling job status.")
    workflow_run_id: str = Field(..., description="Workflow execution identifier.")
    status: str = Field("queued", description="Initial task status.")


class WorkflowTaskStatus(BaseModel):
    task_id: str
    status: str
    result: List[dict[str, object]] | None = None
    error: str | None = None
    attempts: int = 0
    max_retries: int = 0
    queued_at: float
    started_at: float | None = None
    finished_at: float | None = None
    metadata: dict[str, object] | None = None

    @classmethod
    def from_state(cls, task_id: str, state: dict[str, object]) -> "WorkflowTaskStatus":
        return cls(task_id=task_id, **state)


def get_supervisor() -> SupervisorWorkflow:
    """Dependency that provides a fresh supervisor per request."""
    return SupervisorWorkflow()


def _resolve_steps(payload: WorkflowRunRequest) -> List[dict[str, object]]:
    if payload.use_master_workflow and payload.steps:
        raise HTTPException(
            status_code=400,
            detail="Provide either steps or set use_master_workflow, not both.",
        )

    if payload.use_master_workflow or not payload.steps:
        steps = master_workflow
    else:
        steps = [step.dict(exclude_none=True) for step in payload.steps]

    if not steps:
        raise HTTPException(status_code=400, detail="No workflow steps provided.")
    return steps


def _primary_session(steps: List[dict[str, object]]) -> str:
    for step in steps:
        session_id = step.get("session_id")
        if session_id:
            return str(session_id)
    return "default"


def _summarise_results(results: List[dict[str, object]]) -> dict[str, int]:
    total = len(results)
    errors = sum(
        1
        for step in results
        for result in step.values()
        if isinstance(result, dict) and result.get("error")
    )
    return {"steps": total, "errors": errors}


@router.get("/modules")
async def list_modules() -> dict[str, list[str]]:
    """Return the available and enabled modules for orchestration."""
    available = sorted(AgentRegistry.get_available_modules())
    enabled = sorted(AgentRegistry.get_enabled_modules())
    logger.debug(
        "Listed modules",
        extra={"session_id": "system", "trace_id": "orchestrator", "available": len(available), "enabled": len(enabled)},
    )
    return {"available": available, "enabled": enabled}


@router.get("/master")
async def master_definition() -> dict[str, list[dict[str, str]]]:
    """Expose the currently configured master workflow for clients."""
    logger.debug(
        "Master workflow definition requested",
        extra={"session_id": "system", "trace_id": "orchestrator", "step_count": len(master_workflow)},
    )
    return {"workflow": master_workflow}


@router.post("/run")
async def run_workflow(
    request: Request,
    payload: WorkflowRunRequest,
    supervisor: SupervisorWorkflow = Depends(get_supervisor),
) -> dict[str, list[dict[str, object]]]:
    """
    Execute a workflow synchronously and return agent outputs.

    Clients can either supply custom steps or request the predefined master workflow.
    """
    trace_id = getattr(request.state, "trace_id", "N/A")
    request_session = getattr(request.state, "session_id", "N/A")
    steps = _resolve_steps(payload)
    user_id = request.headers.get("X-User-Id", "anonymous")
    workflow_name = "master_workflow" if payload.use_master_workflow or not payload.steps else "custom_workflow"
    session_id = _primary_session(steps)
    session_context = session_id or request_session or "default"
    run_id = create_workflow_run(
        workflow_name,
        trigger_user=user_id,
        session_id=session_id,
        is_async=False,
        request_payload=payload.dict(),
    )

    log_user_action(
        workflow_run_id=run_id,
        user_id=user_id,
        session_id=session_id,
        action_type="workflow_run_requested",
        action_payload={"step_count": len(steps), "use_master": payload.use_master_workflow},
    )
    update_workflow_run_status(run_id, "running")
    log_application_event(
        workflow_run_id=run_id,
        event_type="workflow_started",
        event_payload={"step_count": len(steps), "workflow_name": workflow_name},
    )
    with LoggingContext(trace_id=trace_id, session_id=session_context):
        logger.info(
            "Workflow execution started",
            extra={
                "trace_id": trace_id,
                "session_id": session_context,
                "workflow_run_id": run_id,
                "workflow_name": workflow_name,
                "step_count": len(steps),
            },
        )
        try:
            results = supervisor.execute_workflow(steps, workflow_run_id=run_id, trace_id=trace_id)
        except Exception as exc:
            logger.exception(
                "Workflow execution failed",
                extra={
                    "trace_id": trace_id,
                    "session_id": session_context,
                    "workflow_run_id": run_id,
                    "workflow_name": workflow_name,
                },
            )
            update_workflow_run_status(run_id, "failed", error=str(exc), completed=True)
            log_application_event(
                workflow_run_id=run_id,
                event_type="workflow_failed",
                event_level="error",
                event_payload={"error": str(exc), "workflow_name": workflow_name},
            )
            raise

        summary = _summarise_results(results)
        update_workflow_run_status(run_id, "completed", result_summary=summary, completed=True)
        log_application_event(
            workflow_run_id=run_id,
            event_type="workflow_completed",
            event_payload={"summary": summary, "workflow_name": workflow_name},
        )
        logger.info(
            "Workflow execution completed",
            extra={
                "trace_id": trace_id,
                "session_id": session_context,
                "workflow_run_id": run_id,
                "workflow_name": workflow_name,
                "summary": summary,
            },
        )
    return {"workflow_run_id": run_id, "results": results}


def _get_dispatcher(request: Request) -> AsyncTaskDispatcher:
    dispatcher = getattr(request.app.state, "dispatcher", None)
    if dispatcher is None:
        raise HTTPException(status_code=503, detail="Async dispatcher not initialised.")
    return dispatcher


@router.post("/run_async", response_model=WorkflowAsyncResponse, status_code=202)
async def run_workflow_async(
    request: Request,
    payload: WorkflowRunRequest,
    supervisor: SupervisorWorkflow = Depends(get_supervisor),
) -> WorkflowAsyncResponse:
    """Queue a workflow for async execution."""
    trace_id = getattr(request.state, "trace_id", "N/A")
    request_session = getattr(request.state, "session_id", "N/A")
    steps = _resolve_steps(payload)
    dispatcher = _get_dispatcher(request)
    user_id = request.headers.get("X-User-Id", "anonymous")
    workflow_name = "master_workflow" if payload.use_master_workflow or not payload.steps else "custom_workflow"
    session_id = _primary_session(steps)
    session_context = session_id or request_session or "default"
    run_id = create_workflow_run(
        workflow_name,
        trigger_user=user_id,
        session_id=session_id,
        is_async=True,
        request_payload=payload.dict(),
    )

    log_user_action(
        workflow_run_id=run_id,
        user_id=user_id,
        session_id=session_id,
        action_type="workflow_run_queued",
        action_payload={"step_count": len(steps), "use_master": payload.use_master_workflow},
    )
    log_application_event(
        workflow_run_id=run_id,
        event_type="workflow_queued",
        event_payload={"workflow_name": workflow_name, "step_count": len(steps)},
    )

    with LoggingContext(trace_id=trace_id, session_id=session_context):
        logger.info(
            "Workflow queued for async execution",
            extra={
                "trace_id": trace_id,
                "session_id": session_context,
                "workflow_run_id": run_id,
                "workflow_name": workflow_name,
                "step_count": len(steps),
            },
        )

    async def _execute_async():
        with LoggingContext(trace_id=trace_id, session_id=session_context):
            update_workflow_run_status(run_id, "running")
            log_application_event(
                workflow_run_id=run_id,
                event_type="workflow_started",
                event_payload={"step_count": len(steps), "workflow_name": workflow_name, "async": True},
            )
            try:
                results = supervisor.execute_workflow(steps, workflow_run_id=run_id, trace_id=trace_id)
            except Exception as exc:
                logger.exception(
                    "Async workflow execution failed",
                    extra={
                        "trace_id": trace_id,
                        "session_id": session_context,
                        "workflow_run_id": run_id,
                        "workflow_name": workflow_name,
                    },
                )
                update_workflow_run_status(run_id, "failed", error=str(exc), completed=True)
                log_application_event(
                    workflow_run_id=run_id,
                    event_type="workflow_failed",
                    event_level="error",
                    event_payload={"error": str(exc), "workflow_name": workflow_name},
                )
                raise

            summary = _summarise_results(results)
            update_workflow_run_status(run_id, "completed", result_summary=summary, completed=True)
            log_application_event(
                workflow_run_id=run_id,
                event_type="workflow_completed",
                event_payload={"summary": summary, "workflow_name": workflow_name, "async": True},
            )
            logger.info(
                "Async workflow execution completed",
                extra={
                    "trace_id": trace_id,
                    "session_id": session_context,
                    "workflow_run_id": run_id,
                    "workflow_name": workflow_name,
                    "summary": summary,
                },
            )
            return results

    task_id = await dispatcher.submit(_execute_async, retries=1, metadata={"workflow_run_id": run_id})
    logger.debug(
        "Workflow task submitted",
        extra={
            "trace_id": trace_id,
            "session_id": session_context,
            "workflow_run_id": run_id,
            "task_id": task_id,
        },
    )
    return WorkflowAsyncResponse(task_id=task_id, workflow_run_id=run_id)


@router.get("/results/{task_id}", response_model=WorkflowTaskStatus)
async def workflow_status(request: Request, task_id: str) -> WorkflowTaskStatus:
    """Poll the status or result of an async workflow."""
    trace_id = getattr(request.state, "trace_id", "N/A")
    session_id = getattr(request.state, "session_id", "N/A")
    dispatcher = _get_dispatcher(request)
    state = await dispatcher.result(task_id)
    if state is None:
        logger.warning(
            "Workflow task lookup failed",
            extra={"trace_id": trace_id, "session_id": session_id, "task_id": task_id},
        )
        raise HTTPException(status_code=404, detail=f"Unknown workflow task '{task_id}'.")
    logger.debug(
        "Workflow task status returned",
        extra={
            "trace_id": trace_id,
            "session_id": session_id,
            "task_id": task_id,
            "status": state.get("status"),
        },
    )
    return WorkflowTaskStatus.from_state(task_id, state)
