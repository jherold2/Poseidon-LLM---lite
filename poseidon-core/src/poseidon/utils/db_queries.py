"""Helpers to build schema-aware SQL queries."""

from __future__ import annotations

import os
import re
from typing import Optional


def _get_default_schema() -> str:
    """Resolve default schema from env/config; fall back to 'public'."""

    # Prefer explicit override via environment
    for env_var in ("POSEIDON_DB_SCHEMA", "ERP_DBT_SCHEMA"):
        value = os.getenv(env_var)
        if value and value.strip():
            return value.strip()
    # Fallback
    return "public"


_SAFE_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_schema(schema: str) -> str:
    """Return a safe schema identifier for literal embedding."""

    schema = (schema or "public").strip()
    if not _SAFE_SCHEMA_RE.match(schema):
        return "public"
    return schema


def render_db_schema_query(schema: Optional[str] = None) -> str:
    """Render the DB schema discovery query for the provided schema name."""

    schema = _safe_schema(schema or _get_default_schema())
    # Compose literals used in the query
    schema_literal = schema

    return f"""
WITH objects AS (
    SELECT
        c.relname AS name,
        CASE c.relkind
            WHEN 'r' THEN 'TABLE'
            WHEN 'v' THEN 'VIEW'
            WHEN 'm' THEN 'MATERIALIZED VIEW'
            WHEN 'f' THEN 'FOREIGN TABLE'
            ELSE c.relkind::text
        END AS type
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n
      ON n.oid = c.relnamespace
    WHERE n.nspname = '{schema_literal}'
      AND c.relname NOT LIKE 'pg_%'
      AND c.relname NOT LIKE 'sql_%'
      AND c.relkind IN ('r', 'v', 'm', 'f')
      AND (
            c.relname LIKE 'dim_%'
         OR c.relname LIKE 'fact_%'
      )
), table_metadata AS (
    SELECT json_build_object(
               'name', obj.name,
               'type', obj.type,
               'description', COALESCE(obj_description(('{schema_literal}.' || obj.name)::regclass, 'pg_class'), 'No description'),
               'columns', COALESCE(cols.columns, '[]'::json)
           ) AS metadata
    FROM objects obj
    LEFT JOIN LATERAL (
        SELECT json_agg(
                   json_build_object(
                       'name', a.attname,
                       'type', pg_catalog.format_type(a.atttypid, a.atttypmod),
                       'description', COALESCE(col_description(('{schema_literal}.' || obj.name)::regclass, a.attnum), 'No description'),
                       'is_primary_key', EXISTS (
                           SELECT 1
                           FROM information_schema.table_constraints tc
                           JOIN information_schema.constraint_column_usage ccu
                             ON tc.constraint_name = ccu.constraint_name
                           WHERE tc.constraint_type = 'PRIMARY KEY'
                             AND tc.table_schema = '{schema_literal}'
                             AND tc.table_name = obj.name
                             AND ccu.column_name = a.attname
                       ),
                       'is_foreign_key', EXISTS (
                           SELECT 1
                           FROM information_schema.table_constraints tc
                           JOIN information_schema.constraint_column_usage ccu
                             ON tc.constraint_name = ccu.constraint_name
                           WHERE tc.constraint_type = 'FOREIGN KEY'
                             AND tc.table_schema = '{schema_literal}'
                             AND tc.table_name = obj.name
                             AND ccu.column_name = a.attname
                       )
                   )
                   ORDER BY a.attnum
               ) AS columns
        FROM pg_catalog.pg_attribute a
        WHERE a.attrelid = ('{schema_literal}.' || obj.name)::regclass
          AND a.attnum > 0
          AND NOT a.attisdropped
    ) cols ON TRUE
)
SELECT json_agg(metadata ORDER BY metadata->>'name') AS metadata
FROM table_metadata;
"""


# Backwards-compatible constant using the resolved default schema
DB_SCHEMA_QUERY = render_db_schema_query()
