"""Postgres connectivity helpers with logging-aware execution."""

from __future__ import annotations

import functools
import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Sequence, Tuple, cast

import yaml
from dotenv import load_dotenv

try:  # pragma: no cover - optional dependency
    from sqlalchemy import types as sqltypes
    from sqlalchemy.dialects.postgresql.base import ischema_names
    from sqlalchemy.types import TypeDecorator
except ModuleNotFoundError:  # pragma: no cover - slim env fallback
    sqltypes = None  # type: ignore[assignment]
    ischema_names = None  # type: ignore[assignment]
    TypeDecorator = object  # type: ignore[assignment]

from poseidon.utils.logger_setup import LoggingContext, setup_logging
from poseidon.utils.path_utils import resolve_config_path

try:  # pragma: no cover - dependency available in production
    import psycopg2  # type: ignore
    from psycopg2.extras import register_default_json
except ModuleNotFoundError:  # pragma: no cover - slim env fallback
    psycopg2 = None  # type: ignore[assignment]
    register_default_json = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from psycopg2.extensions import connection as PsycopgConnection
else:  # pragma: no cover - runtime fallback
    PsycopgConnection = Any  # type: ignore[assignment]

load_dotenv()

_CONFIG_PATH = resolve_config_path("db_config.yaml")
setup_logging()
logger = logging.getLogger(__name__)
_SQL_DATABASE: "SimpleSQLDatabase | None" = None

PSYCOPG2_AVAILABLE = psycopg2 is not None
"""Expose driver availability so callers can branch to CLI fallbacks."""


if sqltypes is not None and ischema_names is not None:
    class _PGVectorType(TypeDecorator):  # pragma: no cover - reflection helper
        """Map Postgres `vector` columns to a float array for SQLAlchemy reflection."""

        impl = sqltypes.ARRAY(sqltypes.Float)
        cache_ok = True


    # Ensure SQLAlchemy recognises pgvector columns during metadata reflection.
    ischema_names.setdefault("vector", _PGVectorType)


def _require_psycopg2() -> Any:
    """Return the psycopg2 module or raise with installation guidance."""

    if psycopg2 is None:
        raise ModuleNotFoundError(
            "psycopg2 is not installed. Install the wheel in your virtualenv "
            "or run code paths that use the CLI fallback (e.g. psql) instead."
        )
    return psycopg2


@functools.lru_cache(maxsize=1)
def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Database configuration not found at {_CONFIG_PATH}")
    with _CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    required = {"host", "port", "database", "username"}
    missing = [key for key in required if key not in config]
    if missing:
        raise KeyError(f"Missing database configuration keys: {', '.join(missing)}")
    return config


def _resolve_password(config: dict) -> str:
    env_var = config.get("password_env_var") or os.getenv("DB_PASSWORD_VAR", "DB_PASSWORD")
    password = os.getenv(env_var)
    if password:
        return password
    if config.get("password"):
        return config["password"]
    raise ValueError(
        "Database password not configured. Set the environment variable "
        f"'{env_var}' or provide 'DB_PASSWORD'."
    )


def get_connection_kwargs() -> dict:
    """Return keyword arguments that describe the configured connection."""

    config = _load_config()
    kwargs = {
        "dbname": config["database"],
        "user": config["username"],
        "password": _resolve_password(config),
        "host": config["host"],
        "port": config["port"],
    }
    # Allow specifying a default schema via search_path when provided
    schema = (config.get("schema") or "").strip()
    if schema:
        # Use Postgres options to set search_path
        kwargs["options"] = f"-c search_path={schema},public"
    return kwargs


@contextmanager
def _connect() -> Iterator[PsycopgConnection]:
    module = _require_psycopg2()
    conn = module.connect(**get_connection_kwargs())
    if register_default_json is not None:
        register_default_json(conn, globally=False, loads=lambda value: value)
    try:
        yield cast(PsycopgConnection, conn)
    finally:
        conn.close()


class SimpleSQLDatabase:
    """Tiny wrapper exposing a LangChain-like `.run` API backed by psycopg2."""

    def run(self, query: str, params: Sequence | None = None) -> list[Tuple]:
        normalised_params = tuple(params) if params is not None else None
        with _connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, normalised_params)
                return cursor.fetchall()


def get_db() -> SimpleSQLDatabase:
    """Return a cached ``SimpleSQLDatabase`` instance for integrations."""

    if os.getenv("POSEIDON_DISABLE_DB") == "1":
        class _NoopDatabase:
            def run(self, *args, **kwargs):  # pragma: no cover - used only in tests
                raise RuntimeError("Database access disabled via POSEIDON_DISABLE_DB")

        return _NoopDatabase()  # type: ignore[return-value]

    _require_psycopg2()

    global _SQL_DATABASE
    if _SQL_DATABASE is None:
        config = _load_config()
        redacted_uri = (
            f"postgresql+psycopg2://{config['username']}:****@"
            f"{config['host']}:{config['port']}/{config['database']}"
        )
        with LoggingContext(session_id="system", trace_id="db-connect"):
            logger.info("Creating SimpleSQLDatabase engine for %s", redacted_uri)
        _SQL_DATABASE = SimpleSQLDatabase()
    return _SQL_DATABASE


def run(query: str, params: Sequence | None = None):
    """Execute a SQL query and return rows as tuples."""

    if os.getenv("POSEIDON_DISABLE_DB") == "1":
        raise RuntimeError("Database access disabled via POSEIDON_DISABLE_DB")

    normalised_params = tuple(params) if params is not None else None
    logger.debug("Executing DB query", extra={"query": query, "params": normalised_params})

    with _connect() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, normalised_params)
                rows = cursor.fetchall()
                logger.debug("Query returned %d rows", len(rows))
                return rows
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Database query failed: %s", exc)
            raise


def execute(query: str, params: Sequence | None = None) -> None:
    """Execute a SQL statement that does not return rows (INSERT/UPDATE/DELETE)."""

    if os.getenv("POSEIDON_DISABLE_DB") == "1":
        raise RuntimeError("Database access disabled via POSEIDON_DISABLE_DB")

    normalised_params = tuple(params) if params is not None else None
    logger.debug("Executing DB statement", extra={"query": query, "params": normalised_params})

    with _connect() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, normalised_params)
            conn.commit()
        except Exception as exc:  # pragma: no cover - defensive logging
            conn.rollback()
            logger.error("Database statement failed: %s", exc)
            raise
