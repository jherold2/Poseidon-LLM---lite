"""Utility helpers shared by inference tool modules."""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def parse_date(value: Optional[str | datetime]) -> datetime:
    """Parse inbound date strings into ``datetime`` instances.

    Accepts already-instantiated ``datetime`` objects, ISO formatted strings, or
    YYYY-MM-DD strings. Raises ``ValueError`` when the value cannot be parsed.
    """
    if isinstance(value, datetime):
        return value
    if not value:
        raise ValueError("Date value is required")

    value_str = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value_str)
    except ValueError as exc:  # pragma: no cover - defensive fallback
        raise ValueError(f"Unable to parse date '{value_str}'") from exc


__all__ = ["parse_date"]
