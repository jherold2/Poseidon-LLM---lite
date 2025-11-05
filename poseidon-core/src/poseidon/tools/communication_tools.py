"""Communication helper tools for retrieving escalation contacts."""

from __future__ import annotations

import json
from typing import Dict, Iterable, List

from langchain_core.tools import Tool

from poseidon.utils.db_connect import run as db_run

MODULE_KEYWORDS = {
    "sales": ["sales", "commercial"],
    "purchasing": ["purchasing", "procurement", "buying"],
    "logistics": ["logistics", "supply chain", "distribution"],
    "manufacturing": ["manufacturing", "production", "plant"],
    "accounting": ["accounting", "finance", "controlling"],
    "inference": ["analytics", "data science", "strategy"],
}


def _build_contact_query(keywords: Iterable[str], site: str | None) -> tuple[str, List[str]]:
    base_clauses = [
        "active = TRUE",
        "work_email IS NOT NULL",
        "(login_status ILIKE 'active%' OR login_status ILIKE 'enabled%' OR login_status IS NULL)",
    ]
    params: List[str] = []

    cleaned = [kw.strip() for kw in keywords if kw and kw.strip()]
    if cleaned:
        like_parts: List[str] = []
        for kw in cleaned:
            pattern = f"%{kw}%"
            like_parts.append("department_name ILIKE %s")
            params.append(pattern)
            like_parts.append("job_title ILIKE %s")
            params.append(pattern)
        base_clauses.append("(" + " OR ".join(like_parts) + ")")

    if site:
        base_clauses.append("work_location ILIKE %s")
        params.append(f"%{site}%")

    where_sql = " AND ".join(base_clauses)
    query = f"""
        SELECT
            employee_id,
            employee_name,
            job_title,
            department_name,
            work_email,
            work_location,
            manager_id,
            manager_name
        FROM cda_it_custom.dim_employee
        WHERE {where_sql}
        ORDER BY department_name, job_title
    """
    return query, params


def lookup_escalation_contacts(args: Dict[str, object]) -> str:
    """Return escalation contacts scoped by module, optional keywords, and site."""
    module = str(args.get("module", "")).strip().lower()
    if not module:
        return json.dumps({"error": "module is required"})

    raw_keywords = args.get("keywords") or []
    if isinstance(raw_keywords, str):
        keywords = [raw_keywords]
    elif isinstance(raw_keywords, (list, tuple)):
        keywords = [str(kw) for kw in raw_keywords]
    else:
        return json.dumps({"error": "keywords must be a string or list of strings"})

    site = args.get("site")
    if site is not None:
        site = str(site).strip()
        if not site:
            site = None

    try:
        limit = args.get("limit")
        limit_int = int(limit) if limit is not None else None
        if limit_int is not None and limit_int <= 0:
            return json.dumps({"error": "limit must be positive"})
    except (TypeError, ValueError):
        return json.dumps({"error": "limit must be an integer"})

    combined_keywords = MODULE_KEYWORDS.get(module, []) + keywords
    query, params = _build_contact_query(combined_keywords, site)

    try:
        rows = db_run(query, tuple(params) if params else None)
    except Exception as exc:  # pragma: no cover - defensive guard
        return json.dumps({"error": str(exc)})

    contacts: List[Dict[str, object]] = []
    for row in rows or []:
        contacts.append(
            {
                "employee_id": row[0],
                "name": row[1],
                "job_title": row[2],
                "department": row[3],
                "email": row[4],
                "work_location": row[5],
                "manager_id": row[6],
                "manager_name": row[7],
            }
        )
    if limit_int is not None:
        contacts = contacts[:limit_int]

    payload = {
        "module": module,
        "keywords": combined_keywords,
        "site": site,
        "count": len(contacts),
        "contacts": contacts,
    }
    return json.dumps(payload)


lookup_escalation_contacts_tool = Tool(
    name="lookup_escalation_contacts",
    func=lookup_escalation_contacts,
    description=(
        "Retrieve active employees to notify for escalations. Args: module (str), "
        "keywords (list[str], optional), site (str, optional), limit (int, optional)."
    ),
)

__all__ = ["lookup_escalation_contacts_tool", "lookup_escalation_contacts"]
