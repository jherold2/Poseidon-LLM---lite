# src/agents/base_agent.py
import json
import logging
from time import perf_counter

from poseidon.utils.cache import ConversationCache
from poseidon.utils.logger_setup import LoggingContext, setup_logging

setup_logging()
logger = logging.getLogger(__name__)
cache = ConversationCache()

def format_context(session_id: str, time_window_hours: int = 24) -> tuple[str, int]:
    """Fetch and format historical conversation context."""
    history = cache.get_history(session_id, time_window_hours)
    formatted = "\n".join(
        [f"Prompt: {h['prompt']}\nResponse: {json.dumps(h['response'])}" for h in history]
    )
    return formatted, len(history)

def execute_agent(
    agent,
    prompt_text: str,
    session_id: str = "default",
    *,
    trace_id: str | None = None,
    agent_name: str | None = None,
) -> dict:
    """Execute an agent while emitting structured observability logs."""
    label_candidate = agent_name or getattr(agent, "name", None)
    if callable(label_candidate):
        label_candidate = label_candidate()
    if isinstance(label_candidate, str):
        agent_label = label_candidate.strip() or agent.__class__.__name__
    else:
        agent_label = agent.__class__.__name__

    trace_value = trace_id or "N/A"

    with LoggingContext(session_id=session_id, trace_id=trace_value, agent_name=agent_label):
        context, history_count = format_context(session_id)
        logger.debug(
            "Loaded %d cached context entries",
            history_count,
            extra={"agent_name": agent_label},
        )
        logger.info(
            "[%s] Executing LLM prompt",
            agent_label,
            extra={"agent_name": agent_label},
        )
        logger.debug(
            "Prompt snippet: %s",
            prompt_text[:200],
            extra={"agent_name": agent_label},
        )
        start_time = perf_counter()
        payload = {
            "input": prompt_text,
            "context": context,
            "trace_id": trace_value,
            "session_id": session_id,
        }
        try:
            raw_output = agent.invoke(payload)
            if isinstance(raw_output, dict):
                candidate = raw_output.get("output", raw_output)
            else:
                candidate = raw_output
            if isinstance(candidate, str):
                try:
                    result_payload = json.loads(candidate)
                except json.JSONDecodeError:
                    result_payload = candidate
            else:
                result_payload = candidate

            latency_ms = int((perf_counter() - start_time) * 1000)
            cache_payload = result_payload if isinstance(result_payload, dict) else {"result": result_payload}
            cache.add_entry(session_id, prompt_text, cache_payload)
            logger.info(
                "[%s] Agent completed",
                agent_label,
                extra={"agent_name": agent_label, "latency_ms": latency_ms},
            )
            return result_payload
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("[%s] Agent execution failed", agent_label)
            return {"error": str(exc)}
