"""Runtime signals used by the task orchestrator."""

from __future__ import annotations

import functools
from typing import Dict


@functools.lru_cache(maxsize=1)
def get_current_signals() -> Dict[str, Dict[str, float]]:
    """
    Return a dictionary of the latest department-level urgency signals.

    In production this could hit a metric store or feature service; we start
    with stubbed values so the orchestrator can blend scores deterministically.
    """
    return {}


__all__ = ["get_current_signals"]
