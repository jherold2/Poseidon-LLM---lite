"""Helpers for interacting with MLflow-managed prompt artifacts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:  # pragma: no cover - optional dependency in some environments
    import mlflow
except Exception:  # pragma: no cover - fallback when mlflow missing
    mlflow = None  # type: ignore[assignment]

import yaml

logger = logging.getLogger(__name__)

_MESSAGE_KEYS = ("prompt", "template", "content", "body", "system", "text")


def _extract_prompt_string(data: Any) -> Optional[str]:
    """Normalise different prompt structures into a plain string."""
    if data is None:
        return None

    if isinstance(data, str):
        text = data.strip()
        return text or None

    if isinstance(data, dict):
        for key in _MESSAGE_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        messages = data.get("messages")
        if messages:
            return _extract_prompt_string(messages)
        # Some prompt registries wrap actual text under nested keys.
        for value in data.values():
            extracted = _extract_prompt_string(value)
            if extracted:
                return extracted
        return None

    if isinstance(data, list):
        segments = []
        for item in data:
            if isinstance(item, dict):
                role = item.get("role") or item.get("type")
                content = (
                    _extract_prompt_string(item.get("content"))
                    or _extract_prompt_string(item.get("text"))
                    or _extract_prompt_string(item.get("message"))
                )
                if content:
                    segments.append(f"{role}: {content}" if role else content)
                    continue
            extracted = _extract_prompt_string(item)
            if extracted:
                segments.append(extracted)
        if segments:
            return "\n".join(segments)
        return None

    return None


def load_prompt_from_mlflow(run_id: str, artifact_path: str) -> Optional[str]:
    """Download and parse a prompt artifact stored in MLflow.

    Parameters
    ----------
    run_id:
        The MLflow run identifier that houses the prompt artifacts.
    artifact_path:
        Path to the prompt artifact within the run's artifact store.

    Returns
    -------
    Optional[str]
        The extracted prompt text if retrieval succeeds, otherwise ``None``.
    """

    if not run_id or not artifact_path:
        logger.debug("Missing run_id (%s) or artifact_path (%s) for MLflow prompt", run_id, artifact_path)
        return None

    if mlflow is None:
        logger.warning("MLflow is not available; cannot load prompt %s from run %s", artifact_path, run_id)
        return None

    try:
        client = mlflow.tracking.MlflowClient()
        local_path = Path(client.download_artifacts(run_id, artifact_path))
    except Exception as exc:  # pragma: no cover - network/filesystem failures
        logger.warning("Failed to download MLflow artifact %s from run %s: %s", artifact_path, run_id, exc)
        return None

    if local_path.is_dir():
        logger.warning("Expected file artifact for prompt but found directory at %s", local_path)
        return None

    try:
        text = local_path.read_text(encoding="utf-8").strip()
    except OSError as exc:  # pragma: no cover - filesystem issues
        logger.warning("Unable to read downloaded prompt artifact %s: %s", local_path, exc)
        return None

    if not text:
        return None

    # Attempt to parse structured YAML/JSON that contains the actual prompt field.
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None

    prompt_text = _extract_prompt_string(data)
    if prompt_text:
        return prompt_text

    return _extract_prompt_string(text)


def load_prompt_from_registry(prompt_ref: str) -> Optional[str]:
    """Load a prompt directly from the MLflow Prompt Registry."""
    if not prompt_ref:
        return None

    if mlflow is None:
        logger.warning("MLflow is not available; cannot load prompt %s", prompt_ref)
        return None

    try:
        prompt_obj = mlflow.load_prompt(prompt_ref)
    except Exception as exc:  # pragma: no cover - network/registry failures
        logger.warning("Failed to load MLflow prompt %s: %s", prompt_ref, exc)
        return None

    if prompt_obj is None:
        return None

    for attr in ("template", "prompt", "content", "text"):
        if hasattr(prompt_obj, attr):
            value = getattr(prompt_obj, attr)
            extracted = _extract_prompt_string(value)
            if extracted:
                return extracted

    if hasattr(prompt_obj, "messages"):
        extracted = _extract_prompt_string(getattr(prompt_obj, "messages"))
        if extracted:
            return extracted

    for method in ("to_dict", "dict", "model_dump"):
        if hasattr(prompt_obj, method):
            try:
                data = getattr(prompt_obj, method)()
            except Exception:  # pragma: no cover - defensive
                continue
            extracted = _extract_prompt_string(data)
            if extracted:
                return extracted

    return _extract_prompt_string(str(prompt_obj))
