# src/agents/comms_agent.py
import logging
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from poseidon.utils.langchain_shim import create_tool_calling_agent, AgentExecutor

from poseidon.tools.communication_tools import lookup_escalation_contacts_tool
from poseidon.tools.notification_tools import escalation_tool
from poseidon.tools.notes_tools import decision_tool
from poseidon.tools.context_tools import context_tool
from poseidon.tools.feedback_tools import feedback_tool
from poseidon.utils.logger_setup import LoggingContext, setup_logging
from poseidon.utils.prompt_loader import load_prompt_template
from poseidon.agents.base_agent import execute_agent
from poseidon.utils.local_llm import get_llm

setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """
You are the Communications Agent coordinating alerts and stakeholder outreach.

Capabilities:
- `lookup_escalation_contacts` surfaces staff to notify, based on module keywords, custom topics, and optional site filters.
- `notification_escalation` dispatches structured emails and records the escalation for audit.
- `record_decision` logs communication notes for compliance.

Guidelines:
- Always gather the relevant contact list before sending an alert; include module, keywords, and site context when available.
- Clearly document severity, recommended actions, and any SOP references provided by upstream agents.
- All outputs must be JSON-formatted, capturing recipients, message summary, and next actions.

Historical Context:
{context}
Human: {input}
"""

PROMPT_TEMPLATE = load_prompt_template("comms_agent", DEFAULT_PROMPT_TEMPLATE)


def create_comms_agent():
    """Return a Communications Agent that orchestrates outreach workflows."""
    logger.info("Initializing Communications Agent", extra={"agent_name": "comms"})

    all_tools = [
        lookup_escalation_contacts_tool,
        escalation_tool,
        decision_tool,
        context_tool,
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

        with LoggingContext(session_id=session_id, trace_id=trace_id, agent_name="comms"):
            return execute_agent(
                agent,
                prompt_text,
                session_id,
                trace_id=trace_id,
                agent_name="comms",
            )

    return AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=True,
        handle_parsing_errors=True,
        execute=execute_with_context,
    )


__all__ = ["create_comms_agent"]
