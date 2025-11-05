"""Shared helpers for query tools including payload validation."""

from __future__ import annotations

import logging

import json
import re
from typing import Any, Dict, Iterable, Mapping, Tuple

from poseidon.utils.db_connect import get_db, run
from poseidon.utils.dimension_lookup import resolve_dimension_value
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


# ==== Shared Utilities ====

def load_schema():
    """Load warehouse schema JSON for dynamic column mapping."""
    with open("data/db_schema_remora_9_9_2025.json", "r") as f:
        return json.load(f)


def parse_time_range(time_range: str) -> tuple[str, str]:
    """Standardize 'YYYY-MM-DD to YYYY-MM-DD' or single-year inputs."""
    try:
        if " to " in time_range:
            return tuple(time_range.split(" to "))
        if len(time_range) == 4 and time_range.isdigit():
            return (f"{time_range}-01-01", f"{time_range}-12-31")
        return time_range, time_range
    except Exception as exc:
        logger.error("Invalid time_range format: %s", exc)
        raise ValueError(f"Invalid time_range format: {time_range}")


def normalize_value(val: Any) -> str | None:
    """Convert DB values to clean strings."""
    if val is None:
        return None
    return str(val).strip()


# ==== Payload Validation ====

def _coerce_types(types: Iterable[type | tuple]) -> Tuple[type, ...]:
    flattened: list[type] = []
    for entry in types:
        if isinstance(entry, tuple):
            flattened.extend(entry)
        else:
            flattened.append(entry)
    return tuple(dict.fromkeys(flattened))  # preserve order without duplicates


def validate_payload(
    payload: Mapping[str, Any],
    required: Dict[str, Iterable[type]] | None = None,
    optional: Dict[str, Iterable[type]] | None = None,
    allow_extra: bool = True,
) -> str | None:
    """Validate tool payloads before dispatching database queries.

    Returns an error string if validation fails, otherwise ``None``.
    """

    if not isinstance(payload, Mapping):
        return "Payload must be a JSON object"

    required = required or {}
    optional = optional or {}

    for field, expected_types in required.items():
        if field not in payload:
            return f"Missing required field '{field}'"
        allowed = _coerce_types(expected_types)
        if allowed and not isinstance(payload[field], allowed):
            type_names = ", ".join(t.__name__ for t in allowed)
            return f"Field '{field}' must be of type: {type_names}"

    for field, expected_types in optional.items():
        if field in payload:
            allowed = _coerce_types(expected_types)
            if allowed and not isinstance(payload[field], allowed):
                type_names = ", ".join(t.__name__ for t in allowed)
                return f"Field '{field}' must be of type: {type_names}"

    if not allow_extra:
        extras = set(payload.keys()) - set(required.keys()) - set(optional.keys())
        if extras:
            return "Unexpected fields: " + ", ".join(sorted(extras))

    return None


__all__ = [
    "load_schema",
    "parse_time_range",
    "normalize_value",
    "validate_payload",
    "get_db",
    "run",
    "resolve_dimension_value",
]
