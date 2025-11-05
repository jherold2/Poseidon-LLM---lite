# src/agents/purchasing_agent.py
import logging
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from poseidon.utils.langchain_shim import create_tool_calling_agent, AgentExecutor
from poseidon.tools.query_tools.sales_history_queries import order_status_tool
from poseidon.tools.feedback_tools import feedback_tool
from poseidon.tools.statistical_tools import anomaly_detection_tool
from poseidon.tools.document_tools import (
    list_documents_tool,
    search_documents_tool,
    fetch_document_tool,
)
from poseidon.tools.dimension_tools import dimension_lookup_tool
from poseidon.tools.data_quality_tools import freshness_tool, null_rate_tool
from poseidon.tools.context_tools import context_tool
from poseidon.tools.notes_tools import decision_tool
from poseidon.tools.notification_tools import escalation_tool
from poseidon.utils.logger_setup import LoggingContext, setup_logging
from poseidon.agents.base_agent import execute_agent
from poseidon.tools.metric_tools import metric_query_tool
from poseidon.tools.lean_metrics_tools import lean_metric_summary_tool
from poseidon.utils.prompt_loader import load_prompt_template
from poseidon.utils.local_llm import get_llm
from poseidon.utils.config_loader import is_tool_enabled

setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """
You are the Purchasing Agent responsible for supplier performance and procurement spend.

Core Data:
- Metric layer: dbt semantic metrics via `query_semantic_metric`.
- Drill-down tables: cda_it_custom.fact_purchases, dim_supplier, dim_product.

Instructions:
- Use `query_semantic_metric` for KPI-style requests (spend, pricing, lead times) before calling legacy SQL helpers.
- Use the remaining SQL tools only for detailed line-level extracts or supplier lookups where metrics are insufficient.
- If you fall back to SQL, surface that context in your response payload.
- All outputs should be JSON-friendly to downstream processes.

Historical Context:
{context}
Human: {input}
"""

PROMPT_TEMPLATE = load_prompt_template("purchasing_agent", DEFAULT_PROMPT_TEMPLATE)

def create_purchasing_agent():
    logger.info("Initializing Purchasing Agent", extra={"agent_name": "purchasing"})
    document_tools = []
    if is_tool_enabled("document_tools"):
        document_tools = [search_documents_tool, list_documents_tool, fetch_document_tool]

    all_tools = [
        order_status_tool,
        metric_query_tool,
        lean_metric_summary_tool,
        anomaly_detection_tool,
        *document_tools,
        dimension_lookup_tool,
        freshness_tool,
        null_rate_tool,
        context_tool,
        decision_tool,
        escalation_tool,
        feedback_tool,
    ]
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PROMPT_TEMPLATE),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(llm, all_tools, prompt)

    def execute_with_context(input_data: dict) -> dict:
        session_id = input_data.get("session_id", "default")
        trace_id = input_data.get("trace_id")
        prompt_text = input_data["input"]

        with LoggingContext(session_id=session_id, trace_id=trace_id, agent_name="purchasing"):
            return execute_agent(
                agent,
                prompt_text,
                session_id,
                trace_id=trace_id,
                agent_name="purchasing",
            )

    return AgentExecutor(agent=agent, tools=all_tools, verbose=True,
                         handle_parsing_errors=True, execute=execute_with_context)
