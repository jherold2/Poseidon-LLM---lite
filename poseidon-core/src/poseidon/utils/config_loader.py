"""Shared helpers for loading project configuration such as feature flags."""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Dict

import yaml

from poseidon.utils.path_utils import resolve_config_path

_DEFAULT_FLAGS_PATH = resolve_config_path("feature_flags.yaml")


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@functools.lru_cache(maxsize=1)
def get_feature_flags() -> Dict[str, Any]:
    """Return feature flag configuration with environment override."""
    custom_path = os.getenv("FEATURE_FLAGS_PATH")
    if custom_path:
        candidate = Path(custom_path)
        path = candidate if candidate.exists() else resolve_config_path(custom_path)
    else:
        path = _DEFAULT_FLAGS_PATH
    return _load_yaml(path)


def get_enabled_modules() -> list[str]:
    flags = get_feature_flags()
    modules = flags.get("enabled_modules") or []
    return [m for m in modules if isinstance(m, str)]


def get_metric_catalog_path() -> str:
    flags = get_feature_flags()
    return flags.get("metric_catalog_path", "analytics/metric_catalog.yaml")


def get_prompt_config() -> Dict[str, Any]:
    flags = get_feature_flags()
    return flags.get("prompt", {})


def get_guardrail_config() -> Dict[str, Any]:
    """Return optional guardrail configuration block."""
    flags = get_feature_flags()
    return flags.get("guardrails", {})


def is_tool_enabled(tool_name: str) -> bool:
    """Check whether a named tool family is enabled via feature flags."""
    flags = get_feature_flags()
    tools_config = flags.get("tools")
    if not isinstance(tools_config, dict):
        return True
    value = tools_config.get(tool_name)
    if value is None:
        return True
    return bool(value)
