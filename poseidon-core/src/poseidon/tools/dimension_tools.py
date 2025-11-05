"""LangChain tools for dimension value lookups."""

from __future__ import annotations

import json
from typing import Dict

from langchain_core.tools import Tool

from poseidon.utils.dimension_lookup import resolve_dimension_value


def lookup_dimension_value(args: Dict[str, str]) -> str:
    table = args.get("table")
    search_text = args.get("search_text")
    match_column = args.get("match_column", "name")
    return_column = args.get("return_column", match_column)
    filters = args.get("filters")
    limit = int(args.get("limit", 5))
    additional_filters = json.loads(filters) if isinstance(filters, str) else filters
    results = resolve_dimension_value(
        table=table,
        search_text=search_text,
        match_column=match_column,
        return_column=return_column,
        additional_filters=additional_filters,
        limit=limit,
    )
    return json.dumps({"results": results})


dimension_lookup_tool = Tool(
    name="lookup_dimension_value",
    func=lookup_dimension_value,
    description=(
        "Fuzzy lookup for dimension members. Args: table (str), search_text (str), "
        "match_column (str optional), return_column (str optional), filters (json optional), limit (int optional)."
    ),
)

__all__ = ["dimension_lookup_tool"]
