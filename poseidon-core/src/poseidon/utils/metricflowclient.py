"""Thin client for calling the MetricFlow semantic layer service."""

from __future__ import annotations

import os
import time
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


class MetricFlowError(RuntimeError):
    """Raised when the MetricFlow service returns an error response."""


class MetricFlowClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
        cache_ttl_seconds: int = 120,
    ) -> None:
        self.base_url = base_url or os.getenv("METRICFLOW_URL", "http://localhost:9000")
        self.timeout = timeout
        self.session = session or requests.Session()

        auth_token = token or os.getenv("METRICFLOW_TOKEN")
        if auth_token:
            self.session.headers.update({"Authorization": f"Bearer {auth_token}"})
        self.session.headers.setdefault("Content-Type", "application/json")

        self._cache: Dict[Tuple[str, Tuple[str, ...], Tuple[str, ...], Optional[str], Optional[int]], Tuple[float, Dict[str, Any]]] = {}
        self.cache_ttl_seconds = cache_ttl_seconds

    def query_metric(
        self,
        metric: str,
        *,
        group_by: Optional[Iterable[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        time_range: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "metrics": [metric],
            "group_by": list(group_by or []),
            "filters": filters or [],
        }
        if time_range:
            payload["time_range"] = time_range
        if limit is not None:
            payload["limit"] = limit

        cache_key = (
            metric,
            tuple(group_by or []),
            tuple((json.dumps(f, sort_keys=True)) for f in (filters or [])),
            json.dumps(time_range, sort_keys=True) if time_range else None,
            limit,
        )

        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) <= self.cache_ttl_seconds:
            return cached[1]

        response = self.session.post(
            f"{self.base_url}/query",
            json=payload,
            timeout=self.timeout,
        )
        if not response.ok:
            raise MetricFlowError(
                f"MetricFlow query failed with status {response.status_code}: {response.text}"
            )
        data = response.json()
        self._cache[cache_key] = (time.time(), data)
        return data


_default_client: Optional[MetricFlowClient] = None


def get_metricflow_client() -> MetricFlowClient:
    global _default_client
    if _default_client is None:
        _default_client = MetricFlowClient()
    return _default_client
