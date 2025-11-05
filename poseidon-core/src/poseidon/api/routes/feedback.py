"""User feedback ingestion endpoint for Agent Chat UI."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parents[3]
_DPO_DIR = _BASE_DIR / "data" / "dpo_data"
_FEEDBACK_FILE = _DPO_DIR / "feedback_pairs.jsonl"

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackPayload(BaseModel):
    module: str = Field(..., description="Agent module under evaluation.")
    prompt: str = Field(..., description="Original user prompt.")
    response: Dict[str, Any] = Field(..., description="Agent response payload.")
    is_correct: bool = Field(..., description="Whether the response was satisfactory.")
    reason: str | None = Field(
        None, description="Optional rationale for the rating."
    )
    correct_response: Dict[str, Any] | None = Field(
        None, description="Optional corrected response payload."
    )
    metadata: Dict[str, Any] | None = Field(
        None, description="Optional context (user id, run id, etc.)."
    )


@router.post("", status_code=201)
def submit_feedback(request: Request, payload: FeedbackPayload) -> dict[str, str]:
    """Append a feedback record to the JSONL dataset."""
    trace_id = getattr(request.state, "trace_id", "N/A")
    session_id = getattr(request.state, "session_id", "N/A")
    logger.info(
        "Feedback submission received",
        extra={
            "trace_id": trace_id,
            "session_id": session_id,
            "module": payload.module,
            "is_correct": payload.is_correct,
        },
    )
    try:
        _DPO_DIR.mkdir(parents=True, exist_ok=True)
        record = payload.model_dump(mode="json")
        with _FEEDBACK_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception(
            "Failed to persist feedback",
            extra={"trace_id": trace_id, "session_id": session_id, "module": payload.module},
        )
        raise HTTPException(status_code=500, detail=f"Failed to persist feedback: {exc}")

    logger.debug(
        "Feedback appended to %s",
        _FEEDBACK_FILE,
        extra={"trace_id": trace_id, "session_id": session_id, "module": payload.module},
    )

    return {"status": "ok"}
