"""Routing workflow for multi-agent orchestration."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from time import perf_counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from poseidon.agents.registry import AgentRegistry
from poseidon.observability import log_agent_action, log_application_event
from poseidon.tools.data_quality_tools import freshness_tool, null_rate_tool
from poseidon.utils.config_loader import get_enabled_modules, get_guardrail_config
from poseidon.utils.logger_setup import LoggingContext, bind_context


logger = logging.getLogger(__name__)
_CONTRACTS_ENABLED = os.getenv("POSEIDON_ENABLE_CONTRACTS", "").lower() in ("1", "true", "yes")


@dataclass
class GuardrailResult:
    ok: bool
    message: str | None = None

    @classmethod
    def success(cls) -> "GuardrailResult":
        return cls(True, None)

    @classmethod
    def failure(cls, message: str) -> "GuardrailResult":
        return cls(False, message)


@dataclass
class SimpleContext:
    summary: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.summary or self.metadata)

    def to_legacy_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self.summary:
            payload["summary"] = self.summary
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    def render_text(self) -> str:
        if self.summary:
            return self.summary
        if self.metadata:
            return json.dumps(self.metadata)
        return ""


@dataclass
class AgentTaskInput:
    module: str
    prompt: str
    session_id: str = "default"
    parameters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_workflow(cls, module: str, payload: Dict[str, Any]) -> "AgentTaskInput":
        prompt = str(payload.get("input") or "").strip()
        if not prompt:
            raise ValueError("Input prompt must be provided.")
        session_id = str(payload.get("session_id") or "default")
        params = payload.get("parameters")
        if not isinstance(params, dict):
            params = {}
        return cls(module=module or "unknown", prompt=prompt, session_id=session_id, parameters=params)

    def to_legacy_payload(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "prompt": self.prompt,
            "session_id": self.session_id,
            "parameters": self.parameters,
        }

    def model_dump(self) -> Dict[str, Any]:
        return self.to_legacy_payload()


@dataclass
class AgentTaskOutput:
    result: Dict[str, Any]
    session_id: str
    module: str
    metrics: Dict[str, Any] | None = None
    context: SimpleContext = field(default_factory=SimpleContext)
    tool_traces: List[Dict[str, Any]] = field(default_factory=list)
    handoffs: List[Dict[str, Any]] = field(default_factory=list)

    def model_dump(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "result": self.result,
            "session_id": self.session_id,
            "module": self.module,
        }
        if self.metrics:
            payload["metrics"] = self.metrics
        if not self.context.is_empty():
            payload["context"] = self.context.to_legacy_dict()
        if self.tool_traces:
            payload["tool_traces"] = self.tool_traces
        if self.handoffs:
            payload["handoffs"] = self.handoffs
        return payload

_MODULE_HINTS: Dict[str, tuple[str, ...]] = {
    "sales": (
        "sale",
        "revenue",
        "customer",
        "upsell",
        "pipeline",
        "quote",
        "margin",
        "order",
    ),
    "purchasing": (
        "purchase",
        "supplier",
        "procure",
        "po",
        "vendor",
        "sourcing",
        "buy",
    ),
    "logistics": (
        "inventory",
        "logistic",
        "stock",
        "warehouse",
        "shipping",
        "delivery",
        "fulfillment",
        "transport",
    ),
    "manufacturing": (
        "production",
        "manufactur",
        "bom",
        "work order",
        "assembly",
        "factory",
        "line",
    ),
    "accounting": (
        "invoice",
        "journal",
        "ledger",
        "ap ",
        "ar ",
        "expense",
        "financial",
        "reconcile",
    ),
    "communications": (
        "email",
        "notify",
        "escalate",
        "message",
        "alert",
        "contact",
        "outreach",
    ),
    "inference": (
        "recommend",
        "inference",
        "predict",
        "scenario",
        "forecast",
        "risk",
        "opportunity",
    ),
}


class SupervisorWorkflow:
    _freshness_cache: Dict[str, Tuple[datetime, dict]] = {}

    def __init__(self):
        # Store factories instead of instances per session
        self._agents: Dict[str, object] = {}

    def get_agent(self, name: str):
        if name not in self._agents:
            self._agents[name] = AgentRegistry.get_agent(name)
        return self._agents[name]

    def _is_module_enabled(self, module: str) -> bool:
        enabled_registry = AgentRegistry.get_enabled_modules()
        if enabled_registry:
            return module in enabled_registry

        enabled_flags = set(get_enabled_modules())
        if enabled_flags:
            return module in enabled_flags

        return module in AgentRegistry.get_available_modules()

    def _default_module(self) -> str:
        enabled = AgentRegistry.get_enabled_modules()
        if enabled:
            if "inference" in enabled:
                return "inference"
            return sorted(enabled)[0]
        available = AgentRegistry.get_available_modules()
        if available:
            if "inference" in available:
                return "inference"
            return sorted(available)[0]
        raise RuntimeError("No agents are registered in the registry.")

    def _infer_module(self, prompt: str) -> str | None:
        text = prompt.lower()
        scores: Dict[str, int] = {}
        available = AgentRegistry.get_available_modules()
        if not text.strip():
            return None
        for module, hints in _MODULE_HINTS.items():
            if module not in available:
                continue
            count = sum(text.count(hint) for hint in hints if hint)
            if count:
                scores[module] = count
        if not scores:
            return None
        return max(scores.items(), key=lambda item: item[1])[0]

    def _resolve_module(self, requested_module: str | None, query_data: dict) -> str:
        candidate = (requested_module or "").strip().lower()
        if candidate and candidate in AgentRegistry.get_available_modules():
            if self._is_module_enabled(candidate):
                return candidate
        prompt_text = str(query_data.get("input") or "")
        inferred = self._infer_module(prompt_text)
        if inferred and self._is_module_enabled(inferred):
            return inferred
        return self._default_module()

    def _run_freshness_guardrail(self, module: str, guardrails: dict) -> GuardrailResult:
        config = guardrails.get(module)
        if not config:
            return GuardrailResult.success()

        cache_entry = self._freshness_cache.get(module)
        ttl_seconds = int(config.get("ttl_seconds", 300))
        if cache_entry:
            cached_at, cached_result = cache_entry
            if datetime.utcnow() - cached_at < timedelta(seconds=ttl_seconds):
                if "error" in cached_result:
                    return GuardrailResult.failure(str(cached_result["error"]))
                return GuardrailResult.success()

        payload = {
            "table": config.get("table"),
            "timestamp_column": config.get("timestamp_column"),
        }
        if not payload["table"] or not payload["timestamp_column"]:
            return GuardrailResult.success()

        logger.debug("Running freshness guardrail for module %s", module)
        raw = freshness_tool.func(payload)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            message = f"Freshness guardrail returned invalid JSON: {exc}"
            self._freshness_cache[module] = (datetime.utcnow(), {"error": message})
            return GuardrailResult.failure(message)

        self._freshness_cache[module] = (datetime.utcnow(), result)

        if result.get("error"):
            return GuardrailResult.failure(f"Freshness guardrail failed: {result['error']}")
        if result.get("latest_timestamp") is None:
            return GuardrailResult.failure("Freshness guardrail found no recent data")
        return GuardrailResult.success()

    def _run_null_rate_guardrail(self, module: str, guardrails: dict) -> GuardrailResult:
        module_checks = guardrails.get(module)
        if not module_checks:
            return GuardrailResult.success()

        if isinstance(module_checks, dict):
            module_checks = [module_checks]

        for check in module_checks:
            table = check.get("table")
            column = check.get("column")
            max_null_rate = check.get("max_null_rate")
            if not table or not column or max_null_rate is None:
                logger.debug(
                    "Skipping null-rate guardrail for module %s due to incomplete configuration", module
                )
                continue

            payload = {"table": table, "column": column}
            if check.get("where"):
                payload["where"] = check["where"]

            raw = null_rate_tool.func(payload)
            try:
                result = json.loads(raw)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                return GuardrailResult.failure(f"Null-rate guardrail returned invalid JSON: {exc}")

            if result.get("error"):
                return GuardrailResult.failure(f"Null-rate guardrail failed: {result['error']}")

            null_rate = result.get("null_rate")
            if null_rate is None:
                return GuardrailResult.failure("Null-rate guardrail returned no rate")

            try:
                rate_value = float(null_rate)
                threshold = float(max_null_rate)
            except (TypeError, ValueError):  # pragma: no cover - config validation
                return GuardrailResult.failure("Null-rate guardrail has invalid numeric threshold")

            if rate_value > threshold:
                return GuardrailResult.failure(
                    f"Null-rate guardrail exceeded for {table}.{column}: "
                    f"{rate_value:.4f} > allowed {threshold:.4f}"
                )

        return GuardrailResult.success()

    def _run_guardrails(self, module: str) -> GuardrailResult:
        if not _CONTRACTS_ENABLED:
            return GuardrailResult.success()
        guardrail_config = get_guardrail_config()
        result = self._run_freshness_guardrail(module, guardrail_config.get("freshness", {}))
        if not result.ok:
            return result
        return self._run_null_rate_guardrail(module, guardrail_config.get("null_rate", {}))

    def route_query(self, module: str, query_data: dict, *, workflow_run_id: str | None = None):
        """Route user query to the correct agent based on module."""
        session_context = str(query_data.get("session_id") or "default")
        trace_id = str(query_data.get("trace_id") or workflow_run_id or "N/A")

        with LoggingContext(trace_id=trace_id, session_id=session_context):
            requested_module = (module or "").strip().lower()
            resolved_module = self._resolve_module(requested_module, query_data)
            module_token = bind_context(agent_name=resolved_module)
            try:
                logger.info(
                    "Routing query",
                    extra={
                        "module": resolved_module,
                        "requested_module": requested_module or "auto",
                        "workflow_run_id": workflow_run_id,
                    },
                )

                if not self._is_module_enabled(resolved_module):
                    logger.warning(
                        "Module disabled after resolution",
                        extra={"module": resolved_module, "requested_module": requested_module or "auto"},
                    )
                    return {"error": f"Module '{resolved_module}' is disabled or unknown"}

                guardrail_result = self._run_guardrails(resolved_module)
                if not guardrail_result.ok:
                    logger.warning(
                        "Guardrail failure",
                        extra={"module": resolved_module, "reason": guardrail_result.message},
                    )
                    log_application_event(
                        workflow_run_id=workflow_run_id,
                        event_type="guardrail_failed",
                        event_level="warning",
                        event_payload={"module": resolved_module, "message": guardrail_result.message},
                    )
                    return {"error": guardrail_result.message}

                try:
                    agent_input = AgentTaskInput.from_workflow(resolved_module, query_data)
                except ValueError as exc:
                    logger.error(
                        "Invalid payload for module",
                        extra={"module": resolved_module, "error": str(exc)},
                    )
                    log_application_event(
                        workflow_run_id=workflow_run_id,
                        event_type="invalid_payload",
                        event_level="warning",
                        event_payload={"module": resolved_module, "error": str(exc)},
                    )
                    return {"error": str(exc)}

                session_context = agent_input.session_id or session_context
                session_token = bind_context(session_id=session_context)
                start_time = perf_counter()
                try:
                    agent = self.get_agent(resolved_module)
                    raw_output = agent.execute(agent_input.to_legacy_payload())
                    if isinstance(raw_output, AgentTaskOutput):
                        output = raw_output
                    elif isinstance(raw_output, dict):
                        output = AgentTaskOutput(
                            result=raw_output,
                            session_id=agent_input.session_id,
                            module=resolved_module,
                        )
                    else:
                        raise TypeError(
                            f"Agent '{resolved_module}' returned unsupported payload type: {type(raw_output)!r}"
                        )
                except ValueError as exc:
                    logger.error(
                        "Agent lookup failed",
                        extra={"module": resolved_module, "error": str(exc)},
                    )
                    log_application_event(
                        workflow_run_id=workflow_run_id,
                        event_type="agent_lookup_failed",
                        event_level="error",
                        event_payload={"module": resolved_module, "error": str(exc)},
                    )
                    return {"error": str(exc)}
                except Exception as exc:  # pragma: no cover - defensive guard for downstream agent errors
                    logger.exception(
                        "Agent execution raised exception",
                        extra={"module": resolved_module},
                    )
                    duration_ms = int((perf_counter() - start_time) * 1000)
                    log_agent_action(
                        workflow_run_id=workflow_run_id,
                        module=resolved_module,
                        action_type="execute",
                        request_payload=agent_input.model_dump(),
                        response_payload={"error": str(exc)},
                        duration_ms=duration_ms,
                        error=str(exc),
                    )
                    log_application_event(
                        workflow_run_id=workflow_run_id,
                        event_type="agent_execution_failed",
                        event_level="error",
                        event_payload={"module": resolved_module, "error": str(exc)},
                    )
                    return {"error": str(exc)}
                finally:
                    session_token.reset()

                response = dict(output.result)
                if output.metrics:
                    response["_metrics"] = output.metrics
                if not output.context.is_empty():
                    response["_context"] = output.context.to_legacy_dict()
                    response.setdefault("_context_text", output.context.render_text())
                if output.tool_traces:
                    response["_tool_traces"] = [
                        trace.model_dump(exclude_none=True) for trace in output.tool_traces
                    ]
                if output.handoffs:
                    response["_handoffs"] = [handoff.model_dump() for handoff in output.handoffs]
                response.setdefault("_module", resolved_module)
                if requested_module and requested_module != resolved_module:
                    response.setdefault("_requested_module", requested_module)
                response.setdefault("_session_id", output.session_id)
                response.setdefault("_trace_id", trace_id)

                duration_ms = int((perf_counter() - start_time) * 1000)
                error_message = response.get("error")
                log_agent_action(
                    workflow_run_id=workflow_run_id,
                    module=resolved_module,
                    action_type="execute",
                    request_payload=agent_input.model_dump(),
                    response_payload=response,
                    duration_ms=duration_ms,
                    error=error_message,
                )
                if error_message:
                    logger.warning(
                        "Agent returned error response",
                        extra={"module": resolved_module, "error": error_message},
                    )
                    log_application_event(
                        workflow_run_id=workflow_run_id,
                        event_type="agent_response_error",
                        event_level="warning",
                        event_payload={"module": resolved_module, "error": error_message},
                    )
                else:
                    logger.info(
                        "Agent execution completed",
                        extra={"module": resolved_module, "latency_ms": duration_ms},
                    )
                return response
            finally:
                module_token.reset()

    def execute_workflow(self, workflow_steps: list, *, workflow_run_id: str | None = None, trace_id: str | None = None):
        results = []
        for index, step in enumerate(workflow_steps):
            module = step.get("module")
            input_data = step.get("input")
            session_id = step.get("session_id", "default")
            payload = {"input": input_data, "session_id": session_id, "trace_id": trace_id}
            if workflow_run_id:
                log_application_event(
                    workflow_run_id=workflow_run_id,
                    event_type="workflow_step_started",
                    event_payload={
                        "step_index": index,
                        "module": module,
                        "session_id": session_id,
                    },
                )
            with LoggingContext(session_id=session_id, trace_id=trace_id, agent_name=module or "unknown"):
                if workflow_run_id is not None:
                    result = self.route_query(
                        module,
                        payload,
                        workflow_run_id=workflow_run_id,
                    )
                else:
                    result = self.route_query(module, payload)
            results.append({module: result})
            if workflow_run_id:
                has_error = isinstance(result, dict) and bool(result.get("error"))
                event_type = "workflow_step_failed" if has_error else "workflow_step_completed"
                event_level = "error" if has_error else "info"
                log_application_event(
                    workflow_run_id=workflow_run_id,
                    event_type=event_type,
                    event_level=event_level,
                    event_payload={
                        "step_index": index,
                        "module": module,
                        "session_id": session_id,
                        "error": result.get("error") if isinstance(result, dict) else None,
                    },
                )
        return results
