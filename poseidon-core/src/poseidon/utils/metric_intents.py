"""Utility helpers for resolving natural language requests to catalogued metrics."""

from __future__ import annotations

import logging

import functools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from difflib import get_close_matches

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

INTENT_FILE = Path("data/metric_intents.yaml")


@dataclass
class MetricIntent:
    name: str
    metric: str
    triggers: List[str]
    synonyms: List[str] = field(default_factory=list)
    default_group_by: List[str] = field(default_factory=list)
    default_time_range: Optional[Dict[str, Any]] = None
    filters: List[Dict[str, Any]] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def build_filters(self, query_args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Merge default filters with dynamic ones supplied at call time."""
        dynamic_filters = query_args.get("filters") or []
        return self.filters + dynamic_filters


@functools.lru_cache(maxsize=1)
def load_metric_intents() -> List[MetricIntent]:
    if not INTENT_FILE.exists():
        logger.warning("Metric intent file %s missing", INTENT_FILE)
        return []

    raw = yaml.safe_load(INTENT_FILE.read_text()) or []
    intents: List[MetricIntent] = []
    for entry in raw:
        try:
            intent = MetricIntent(
                name=entry["name"],
                metric=entry["metric"],
                triggers=[t.lower() for t in entry.get("triggers", [])],
                synonyms=[s.lower() for s in entry.get("synonyms", [])],
                default_group_by=entry.get("default_group_by", []) or [],
                default_time_range=entry.get("default_time_range"),
                filters=entry.get("filters", []) or [],
                depends_on=entry.get("depends_on", []) or [],
                notes=entry.get("notes"),
            )
            intents.append(intent)
        except KeyError as exc:
            logger.warning("Skipping malformed intent entry %s: %s", json.dumps(entry), exc)
    return intents


def resolve_metric_intent(question: str) -> Optional[MetricIntent]:
    question_lc = question.lower()
    best_match: Optional[MetricIntent] = None
    best_score = 0

    intents = load_metric_intents()

    for intent in intents:
        for keyword in intent.triggers + intent.synonyms:
            if keyword and keyword in question_lc:
                score = len(keyword)
                if score > best_score:
                    best_score = score
                    best_match = intent

    if best_match:
        logger.debug("Resolved metric intent '%s' for question '%s'", best_match.name, question)
        return best_match

    keyword_map = {k: intent for intent in intents for k in intent.triggers + intent.synonyms}
    candidates = get_close_matches(question_lc, keyword_map.keys(), n=1, cutoff=0.6)
    if candidates:
        match_keyword = candidates[0]
        matched_intent = keyword_map.get(match_keyword)
        if matched_intent:
            logger.debug(
                "Fuzzy resolved metric intent '%s' via keyword '%s'",
                matched_intent.name,
                match_keyword,
            )
            return matched_intent

    logger.info("No metric intent match for question '%s'", question)
    return None
