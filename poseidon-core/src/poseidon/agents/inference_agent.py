# src/agents/inference_agent.py
import logging
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from poseidon.utils.langchain_shim import create_tool_calling_agent, AgentExecutor
from poseidon.tools.query_tools.sales_history_queries import (
    customer_order_history_tool,
    order_status_tool,
)
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
from poseidon.utils.prompt_loader import load_prompt_template
from poseidon.agents.base_agent import execute_agent
from poseidon.tools.metric_tools import metric_query_tool
from poseidon.tools.lean_metrics_tools import lean_metric_summary_tool
from poseidon.tools.behavior_tools import behavior_tool
from poseidon.tools.forecast_tools import forecast_tool
from poseidon.tools.executive_tools import executive_brief_tool
from poseidon.tools.rootcause_tools import root_cause_tool
from poseidon.tools.inference_tools.sales_recommendations import (
    upsell_inference_tool,
    payment_risk_tool,
    price_sensitivity_tool,
    margin_scenario_tool,
)
from poseidon.utils.local_llm import get_llm
from poseidon.utils.config_loader import is_tool_enabled

setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """
You are the Inference/Upsell Agent driving cross-sell recommendations.

Core Data:
- Metric layer: sales KPIs from `query_semantic_metric` (customer value, margin, order cadence).
- Drill-down tables: fact_sales_mv, dim_customer, dim_product for purchase histories.

Instructions:
- Start with `query_semantic_metric` for customer KPIs that guide upsell logic.
- Use SQL drill-down helpers only when you need raw order lines or contextual purchase history to justify recommendations.
- Highlight when fallbacks are used so downstream reviewers know the data provenance.
- Responses must be JSON-friendly.

Historical Context:
{context}
Human: {input}
"""

PROMPT_TEMPLATE = load_prompt_template("inference_agent", DEFAULT_PROMPT_TEMPLATE)

def create_inference_agent():
    logger.info("Initializing Inference/Upsell Agent", extra={"agent_name": "inference"})
    document_tools = []
    if is_tool_enabled("document_tools"):
        document_tools = [search_documents_tool, list_documents_tool, fetch_document_tool]

    all_tools = [
        customer_order_history_tool,
        order_status_tool,
        metric_query_tool,
        lean_metric_summary_tool,
        anomaly_detection_tool,
        *document_tools,
        dimension_lookup_tool,
        freshness_tool,
        null_rate_tool,
        forecast_tool,
        behavior_tool,
        executive_brief_tool,
        root_cause_tool,
        upsell_inference_tool,
        payment_risk_tool,
        price_sensitivity_tool,
        margin_scenario_tool,
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

        with LoggingContext(session_id=session_id, trace_id=trace_id, agent_name="inference"):
            return execute_agent(
                agent,
                prompt_text,
                session_id,
                trace_id=trace_id,
                agent_name="inference",
            )

    return AgentExecutor(agent=agent, tools=all_tools, verbose=True,
                         handle_parsing_errors=True, execute=execute_with_context)
