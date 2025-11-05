"""Helpers for loading employee task templates from YAML."""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml

LOGGER = logging.getLogger(__name__)
DEFAULT_TEMPLATE_PATH = Path("data/employee_task_templates.yaml")


def _normalise_indentation(lines: List[str]) -> List[str]:
    """Fix legacy indentation quirks so YAML can be parsed."""
    normalised: List[str] = []
    for raw in lines:
        if raw.startswith("  version:"):
            continue  # duplicate header line with stray indent

        stripped = raw.strip()
        if not stripped:
            normalised.append("")
            continue

        indent = len(raw) - len(raw.lstrip())
        if stripped == "departments:":
            indent = 0
        elif indent == 4 and stripped.endswith(":") and stripped[0].isupper():
            indent = 2
        elif stripped.startswith("- id:"):
            indent = 4
        elif indent >= 6:
            indent = indent - 2

        normalised.append(" " * indent + stripped)
    return normalised


def _load_yaml(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Task template file not found at {path}")

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    normalised = _normalise_indentation(lines)
    payload = yaml.safe_load("\n".join(normalised)) or {}
    if not isinstance(payload, Mapping):
        raise ValueError("Task template file must contain a mapping at the top level.")
    return payload


@functools.lru_cache(maxsize=1)
def load_templates(path: Path = DEFAULT_TEMPLATE_PATH) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return task templates keyed by department.

    The loader normalises indentation quirks so we can keep the human-friendly
    YAML format without breaking structured access.
    """
    payload = _load_yaml(path)
    departments = payload.get("departments", {})
    if not isinstance(departments, Mapping):
        raise ValueError("Task template file is missing a 'departments' mapping.")

    cleaned: Dict[str, List[Dict[str, Any]]] = {}
    for dept, items in departments.items():
        if not isinstance(items, list):
            LOGGER.warning("Skipping department %s: expected a list of tasks.", dept)
            continue

        valid_tasks: List[Dict[str, Any]] = []
        for task in items:
            if isinstance(task, dict):
                valid_tasks.append(task)
            else:
                LOGGER.warning("Ignoring malformed task entry in %s: %r", dept, task)
        cleaned[dept] = valid_tasks
    return cleaned


def list_task_ids(path: Path = DEFAULT_TEMPLATE_PATH) -> List[str]:
    """Return all template IDs across departments."""
    templates = load_templates(path)
    ids: List[str] = []
    for tasks in templates.values():
        for item in tasks:
            task_id = item.get("id")
            if isinstance(task_id, str):
                ids.append(task_id)
    return ids


__all__ = ["load_templates", "list_task_ids"]
