"""Agent responsible for recommending employee tasks."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from poseidon.agents import task_catalog, task_signals
from poseidon.utils.path_utils import resolve_config_path
from poseidon_cda.agents import impact_scoring

try:
    from poseidon.tools.query_tools.feedback_context import query_feedback_context
except Exception:  # pragma: no cover - optional vector store dependency
    def query_feedback_context(*_args: Any, **_kwargs: Any) -> List[Dict[str, Any]]:
        raise FileNotFoundError("Feedback context store unavailable")

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = resolve_config_path("task_orchestrator.yaml")

try:  # Optional dependency for semantic matching
    from sentence_transformers import SentenceTransformer, util as st_util
except ImportError:  # pragma: no cover - exercised only when dependency missing
    SentenceTransformer = None  # type: ignore[assignment]
    st_util = None  # type: ignore[assignment]


def load_orchestrator_config(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load optional configuration overrides for the orchestrator."""
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
        if not isinstance(payload, dict):
            raise ValueError("task_orchestrator.yaml must contain a mapping at the top level.")
        return payload


class _StaticEmbedder:
    """Fallback embedder when sentence-transformers is unavailable."""

    def __init__(self):
        LOGGER.warning(
            "SentenceTransformer not available; semantic matching disabled. "
            "Install 'sentence-transformers' for improved relevance."
        )

    def encode(self, *_args: Any, **_kwargs: Any):
        raise RuntimeError("Semantic matching unavailable without sentence-transformers.")


class TaskOrchestratorAgent:
    """Generate ranked employee tasks based on templates and runtime signals."""

    def __init__(
        self,
        *,
        fuzzy_matching: bool = True,
        semantic_matching: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.catalog = task_catalog.load_templates()
        self.signals = task_signals.get_current_signals()
        self.timestamp = datetime.utcnow()
        self.fuzzy_matching = fuzzy_matching
        self.semantic_matching = semantic_matching
        self.semantic_threshold = 0.6
        self.weights = {
            "base_impact": 0.7,
            "fuzzy_bonus": 0.1,
            "semantic_bonus": 0.15,
            "feedback_bonus": 0.05,
        }

        config = load_orchestrator_config()
        self.weights.update(config.get("weights", {}))
        self.semantic_threshold = float(config.get("semantic_threshold", self.semantic_threshold))

        self._embedder = self._init_embedder(embedding_model) if semantic_matching else None

    def _init_embedder(self, model_name: str):
        if SentenceTransformer is None:  # pragma: no cover - depends on optional dep
            self.semantic_matching = False
            return _StaticEmbedder()

        try:
            return SentenceTransformer(model_name)
        except Exception as exc:  # pragma: no cover - dependent on runtime env
            LOGGER.warning("Failed to load SentenceTransformer model '%s': %s", model_name, exc)
            self.semantic_matching = False
            return _StaticEmbedder()

    def _department_candidates(self, department: str) -> List[Dict[str, Any]]:
        tasks = list(self.catalog.get(department, []))
        if tasks:
            return tasks

        if not self.fuzzy_matching:
            return []

        matches: List[Dict[str, Any]] = []
        for dept_name, dept_tasks in self.catalog.items():
            if department.lower() in dept_name.lower() or dept_name.lower() in department.lower():
                matches.extend(dept_tasks)
        return matches

    def _semantic_bonus(self, role: str, task_role: str) -> float:
        if not self.semantic_matching or not self._embedder:
            return 0.0
        if not task_role:
            return 0.0

        try:
            role_embedding = self._embedder.encode(role, convert_to_tensor=True)  # type: ignore[attr-defined]
            task_embedding = self._embedder.encode(task_role, convert_to_tensor=True)  # type: ignore[attr-defined]
        except RuntimeError:
            return 0.0

        if st_util is None:
            return 0.0

        similarity = float(st_util.cos_sim(role_embedding, task_embedding).item())
        return similarity if similarity >= self.semantic_threshold else 0.0

    def _fuzzy_bonus(self, role: str, task_role: str) -> float:
        if not self.fuzzy_matching or not task_role:
            return 0.0
        role_lower = role.lower()
        task_lower = task_role.lower()
        return 0.05 if role_lower in task_lower or task_lower in role_lower else 0.0

    def _feedback_bonus(self, role: str, title: str) -> float:
        try:
            examples = query_feedback_context(f"{role} {title}", k=3)
        except FileNotFoundError:
            return 0.0
        scores = [float(item.get("score", 0.0)) for item in examples]
        if not scores:
            return 0.0
        return min(0.1, sum(scores) / 30.0)

    def _score_task(self, task: Dict[str, Any], employee: Dict[str, Any]) -> Dict[str, Any]:
        role = employee.get("job_title", "")
        task_role = task.get("role_title") or task.get("role") or ""
        title = task.get("title") or task.get("name") or task.get("id")

        base_score = impact_scoring.calculate(task, self.signals, employee)
        fuzzy_bonus = self._fuzzy_bonus(role, task_role)
        semantic_bonus = self._semantic_bonus(role, task_role)
        feedback_bonus = self._feedback_bonus(role, str(title))

        final_score = (
            base_score * self.weights["base_impact"]
            + fuzzy_bonus * self.weights["fuzzy_bonus"]
            + semantic_bonus * self.weights["semantic_bonus"]
            + feedback_bonus * self.weights["feedback_bonus"]
        )

        strategy = "exact"
        if semantic_bonus:
            strategy = "semantic"
        elif fuzzy_bonus:
            strategy = "fuzzy"

        enriched = dict(task)
        enriched.update(
            {
                "employee_id": employee.get("id"),
                "role": role,
                "base_score": base_score,
                "fuzzy_bonus": fuzzy_bonus,
                "semantic_bonus": semantic_bonus,
                "feedback_bonus": feedback_bonus,
                "score": final_score,
                "matching_strategy": strategy,
            }
        )
        return enriched

    def generate_candidates(self, employee: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Return ranked task recommendations for an employee.

        Args:
            employee: Dictionary containing at least ``department_name``, ``job_title``,
              and ``id`` keys.
        """
        department = employee.get("department_name")
        if not department:
            raise ValueError("Employee record must include 'department_name'.")

        candidates = self._department_candidates(department)
        if not candidates:
            LOGGER.info("No task templates found for department '%s'.", department)
            return []

        enriched = [self._score_task(task, employee) for task in candidates]
        enriched.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return enriched


__all__ = ["TaskOrchestratorAgent", "load_orchestrator_config"]
