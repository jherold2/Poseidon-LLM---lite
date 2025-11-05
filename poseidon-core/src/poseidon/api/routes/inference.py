"""API endpoints for direct interaction with the local LLM."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from poseidon.utils.local_llm import get_llm
from poseidon.utils.logger_setup import LoggingContext

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/inference", tags=["inference"])


class CompletionRequest(BaseModel):
    prompt: str = Field(..., description="User prompt sent to the LLM.")
    max_tokens: int | None = Field(
        None, description="Optional override for maximum new tokens."
    )


class CompletionResponse(BaseModel):
    prompt: str
    completion: str


@router.post("/complete", response_model=CompletionResponse)
async def complete(request: Request, payload: CompletionRequest) -> CompletionResponse:
    """Generate a response using the cached local LLM."""
    llm = get_llm()
    if hasattr(llm, "max_tokens") and payload.max_tokens is not None:
        if payload.max_tokens <= 0:
            raise HTTPException(status_code=400, detail="max_tokens must be positive.")

    trace_id = getattr(request.state, "trace_id", "N/A")
    session_id = getattr(request.state, "session_id", "N/A")
    start_time = time.perf_counter()
    logger.info(
        "LLM completion request received",
        extra={
            "trace_id": trace_id,
            "session_id": session_id,
            "max_tokens": payload.max_tokens,
        },
    )

    def _invoke() -> str:
        kwargs = {}
        if payload.max_tokens is not None:
            kwargs["max_tokens"] = payload.max_tokens
        with LoggingContext(trace_id=trace_id, session_id=session_id):
            logger.debug(
                "Dispatching LLM prompt snippet: %s",
                payload.prompt[:150],
                extra={"trace_id": trace_id, "session_id": session_id},
            )
            result = llm.invoke(payload.prompt, **kwargs)
            if isinstance(result, str):
                return result
            if isinstance(result, dict) and "text" in result:
                return str(result["text"])
            return str(result)

    completion = await run_in_threadpool(_invoke)
    latency_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "LLM completion finished",
        extra={
            "trace_id": trace_id,
            "session_id": session_id,
            "latency_ms": round(latency_ms, 2),
        },
    )
    return CompletionResponse(prompt=payload.prompt, completion=completion)
