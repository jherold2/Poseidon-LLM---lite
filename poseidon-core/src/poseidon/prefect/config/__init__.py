"""Configuration helpers for top-level Prefect flows."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence
from urllib.parse import quote_plus

from poseidon.utils.path_utils import repo_root

from . import defaults

try:  # Prefect variables are optional at runtime
    from prefect.exceptions import MissingVariableError
    from prefect.variables import get as get_variable
except Exception:  # pragma: no cover - Prefect not available
    MissingVariableError = RuntimeError  # type: ignore[assignment]

    def get_variable(name: str) -> str | None:  # type: ignore[override]
        raise MissingVariableError


def _get_config_value(name: str, *, default: str) -> str:
    """Return configuration value preferring Prefect Variables."""
    try:
        value = get_variable(name)
    except MissingVariableError:
        value = None
    if value is None:
        value = os.getenv(name, default)
    return value


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls, prefix: str = "POSEIDON_REPLICA") -> "PostgresConfig":
        return cls(
            host=_get_config_value(f"{prefix}_HOST", default="localhost"),
            port=int(_get_config_value(f"{prefix}_PORT", default="5432")),
            database=_get_config_value(f"{prefix}_DATABASE", default="postgres"),
            user=_get_config_value(f"{prefix}_USER", default="poseidon"),
            password=_get_config_value(f"{prefix}_PASSWORD", default="poseidon"),
        )


def airflow_temp_root() -> Path:
    return repo_root() / "airflow-temp"


def _load_manifest(env_var: str, fallback: Sequence[Dict[str, str]], default_filename: str) -> List[Dict[str, str]]:
    override = _get_config_value(env_var, default="")
    if override:
        path = Path(override)
        if not path.exists():
            raise FileNotFoundError(f"{env_var} points to missing file: {path}")
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError(f"{env_var} must point to a JSON array of manifest entries.")
        return data

    candidate = airflow_temp_root() / default_filename
    if candidate.exists():
        with candidate.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data

    return list(fallback)


def load_sales_materialized_views() -> List[Dict[str, str]]:
    return _load_manifest("POSEIDON_PREFECT_SALES_MV", defaults.SALES_MV_CONFIG, "sales_materialized_views.json")


def load_accounting_materialized_views() -> List[Dict[str, str]]:
    return _load_manifest("POSEIDON_PREFECT_ACCOUNTING_MV", defaults.ACCOUNTING_MV_CONFIG, "accounting_materialized_views.json")


def load_production_materialized_views() -> List[Dict[str, str]]:
    return _load_manifest("POSEIDON_PREFECT_PRODUCTION_MV", defaults.PRODUCTION_MV_CONFIG, "production_materialized_views.json")


def airflow_sql_path(relative_sql: str) -> Path:
    candidate = airflow_temp_root() / "sql" / relative_sql
    if not candidate.exists():
        raise FileNotFoundError(f"Unable to locate SQL file: {candidate}")
    return candidate


def build_sqlalchemy_url(config: PostgresConfig, *, driver: str = "psycopg2") -> str:
    """
    Create a SQLAlchemy-compatible Postgres URL from a PostgresConfig.

    Parameters
    ----------
    config:
        Connection settings for the target Postgres instance.
    driver:
        DBAPI driver name. Defaults to ``psycopg2``.
    """
    user = quote_plus(config.user)
    password = quote_plus(config.password)
    return f"postgresql+{driver}://{user}:{password}@{config.host}:{config.port}/{config.database}"


def create_sqlalchemy_engine(prefix: str = "POSEIDON_REPLICA"):
    """
    Lazily construct a SQLAlchemy engine using environment or Prefect variables.

    The prefix matches the PostgresConfig.from_env prefix, defaulting to the replica configuration.
    """
    from sqlalchemy import create_engine  # local import to avoid unconditional dependency

    pg_config = PostgresConfig.from_env(prefix=prefix)
    return create_engine(build_sqlalchemy_url(pg_config))
