import logging
import re
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from poseidon.utils.langchain_shim import create_tool_calling_agent, AgentExecutor
from poseidon.tools.query_tools.sales_history_queries import (
    customer_order_history_tool,
    order_status_tool,
    sales_metrics_tool,
)
from poseidon.tools.query_tools.category_queries import category_sales_tool
from poseidon.tools.metric_tools import metric_query_tool
from poseidon.tools.lean_metrics_tools import lean_metric_summary_tool
from poseidon.tools.statistical_tools import anomaly_detection_tool
from poseidon.tools.document_tools import (
    list_documents_tool,
    search_documents_tool,
    fetch_document_tool,
)
from poseidon.tools.dimension_tools import dimension_lookup_tool
from poseidon.tools.data_quality_tools import freshness_tool, null_rate_tool
from poseidon.tools.feedback_tools import feedback_tool
from poseidon.tools.context_tools import context_tool
from poseidon.tools.notes_tools import decision_tool
from poseidon.tools.notification_tools import escalation_tool
from poseidon.utils.logger_setup import LoggingContext, setup_logging
from poseidon.utils.prompt_loader import load_prompt_template
from poseidon.agents.base_agent import execute_agent
from poseidon.utils.dimension_lookup import resolve_dimension_value
from poseidon.utils.local_llm import get_llm
from poseidon.utils.config_loader import is_tool_enabled

setup_logging()
logger = logging.getLogger(__name__)

# ----- Customer ID Helper -----
def get_customer_id(customer: str) -> str:
    if re.match(r'^C\d+$', customer):
        return customer
    matches = resolve_dimension_value("dim_customer", customer, "customer", "customer_id")
    if matches:
        return matches[0]["value"]
    alt_matches = resolve_dimension_value(
        "cda_it_custom.fact_sales_mv",
        customer,
        "customer",
        "customer_ref",
    )
    if alt_matches:
        return alt_matches[0]["value"]
    logger.error("Customer '%s' not found", customer)
    return None

# ----- Prompt Template -----
DEFAULT_PROMPT_TEMPLATE = """
You are the Sales Agent for Cedea, focused on commercial performance.

Core Data:
- Metric layer: dbt semantic metrics exposed through `query_semantic_metric`.
- Drill-down tables: cda_it_custom.fact_sales_mv, dim_customer, dim_product.

Instructions:
- Always attempt KPI or aggregate questions via `query_semantic_metric` first.
- When the user requests detailed order lines, category breakdowns, or contextual lists, call the legacy SQL helpers (`query_customer_purchase_history`, `query_sales_by_category`, `query_order_status`).
- If the semantic layer returns a warning in the tool output, acknowledge the fallback and proceed with the provided data.
- Keep responses JSON-structured in line with the tool results.
- Infer customer_id from customer_name when necessary before dispatching tools.

Historical Context:
{context}
Human: {input}
"""

PROMPT_TEMPLATE = load_prompt_template("sales_agent", DEFAULT_PROMPT_TEMPLATE)

# ----- Agent Factory -----
def create_sales_agent():
    """
    Returns a new Sales Agent instance. Safe to call multiple times in Streamlit.
    """
    logger.info("Initializing Sales Agent", extra={"agent_name": "sales"})

    document_tools = []
    if is_tool_enabled("document_tools"):
        document_tools = [search_documents_tool, list_documents_tool, fetch_document_tool]

    all_tools = [
        customer_order_history_tool,
        category_sales_tool,
        sales_metrics_tool,
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
    llm = get_llm()  # only creates instance at runtime
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

        with LoggingContext(session_id=session_id, trace_id=trace_id, agent_name="sales"):
            match = re.search(r'(customer|client)\s+([^\s]+)', prompt_text, re.IGNORECASE)
            if match:
                customer_id = get_customer_id(match.group(2))
                if customer_id:
                    prompt_text = prompt_text.replace(match.group(2), customer_id)
                    logger.info(
                        "Normalized customer reference to ID %s",
                        customer_id,
                        extra={"agent_name": "sales"},
                    )

            return execute_agent(
                agent,
                prompt_text,
                session_id,
                trace_id=trace_id,
                agent_name="sales",
            )

    return AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=True,
        handle_parsing_errors=True,
        execute=execute_with_context
    )
