"""Helpers for resolving dimension values from free-text input."""

from __future__ import annotations

import logging

import json
from typing import Dict, List, Optional

from poseidon.utils.db_connect import run as db_run
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def resolve_dimension_value(
    table: str,
    search_text: str,
    match_column: str,
    return_column: str,
    additional_filters: Optional[Dict[str, str]] = None,
    limit: int = 5,
) -> List[Dict[str, str]]:
    if not search_text:
        return []
    filters = additional_filters or {}
    clauses = ["LOWER({}) LIKE LOWER(%s)".format(match_column)]
    params: List[str] = [f"%{search_text}%"]
    for column, value in filters.items():
        clauses.append(f"{column} = %s")
        params.append(value)
    where_clause = " AND ".join(clauses)
    query = (
        f"SELECT DISTINCT {return_column}, {match_column} "
        f"FROM {table} "
        f"WHERE {where_clause} "
        f"ORDER BY LENGTH({match_column}) ASC "
        f"LIMIT {limit}"
    )
    try:
        rows = db_run(query, tuple(params))
        results = [
            {"value": row[0], "label": row[1]}
            for row in rows
        ]
        if not results:
            logger.info("No dimension matches for %s in %s.%s", search_text, table, match_column)
        return results
    except Exception as exc:  # pragma: no cover
        logger.error("Dimension lookup failed: %s", exc)
        return []
