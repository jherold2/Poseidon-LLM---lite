"""FastAPI application package for Poseidon."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from poseidon.langgraph.server import get_langgraph_app
from poseidon.utils.logger_setup import LoggingContext, setup_logging
from poseidon.workflows.async_dispatcher import (
    dispatcher,
    shutdown_dispatcher,
    startup_dispatcher,
)
from .routes import auth_service, feedback, health, inference, workflows

setup_logging()
logger = logging.getLogger(__name__)


def _extract_session_id(request: Request) -> str:
    for header in ("x-session-id", "x-sessionid", "x-session"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    if request.query_params.get("session_id"):
        return str(request.query_params["session_id"])
    cookie = request.cookies.get("session_id")
    if cookie:
        return cookie
    return uuid4().hex


def _extract_trace_id(request: Request) -> str:
    for header in ("x-trace-id", "x-request-id", "x-correlation-id"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    return uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach trace and session identifiers for every incoming request."""

    async def dispatch(self, request: Request, call_next):
        trace_id = _extract_trace_id(request)
        session_id = _extract_session_id(request)
        request.state.trace_id = trace_id
        request.state.session_id = session_id

        start_time = time.perf_counter()
        with LoggingContext(trace_id=trace_id, session_id=session_id):
            logger.info(
                "Request started",
                extra={
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "Request failed",
                    extra={
                        "trace_id": trace_id,
                        "session_id": session_id,
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
                raise

            latency_ms = (time.perf_counter() - start_time) * 1000
            response.headers["X-Trace-ID"] = trace_id
            logger.info(
                "Request completed",
                extra={
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "latency_ms": round(latency_ms, 2),
                    "status_code": response.status_code,
                    "path": request.url.path,
                },
            )
            return response


def create_app() -> FastAPI:
    """Instantiate the FastAPI app and register routers."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await startup_dispatcher()
        try:
            with LoggingContext(trace_id="startup", session_id="system"):
                logger.info("Poseidon API startup complete")
            yield
        finally:
            with LoggingContext(trace_id="shutdown", session_id="system"):
                logger.info("Poseidon API shutdown initiated")
            await shutdown_dispatcher()

    fastapi_app = FastAPI(
        title="Poseidon Orchestration API",
        description=(
            "REST interface for orchestrating Poseidon workflows, "
            "LLM inference, and system automation."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    fastapi_app.add_middleware(RequestContextMiddleware)

    fastapi_app.include_router(auth_service.router)
    fastapi_app.include_router(health.router)
    fastapi_app.include_router(workflows.router)
    fastapi_app.include_router(inference.router)
    fastapi_app.include_router(feedback.router)
    fastapi_app.mount("/graph", get_langgraph_app())

    fastapi_app.state.dispatcher = dispatcher

    return fastapi_app


def app() -> FastAPI:
    """Compatibility wrapper for `uvicorn poseidon.api:app --factory`."""
    return create_app()


__all__ = ["RequestContextMiddleware", "create_app", "app"]
