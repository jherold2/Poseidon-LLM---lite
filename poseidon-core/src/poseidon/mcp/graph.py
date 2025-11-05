import asyncio
import os
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - safeguarded by requirements
    ChatOpenAI = None  # type: ignore

try:
    from langchain_community.chat_models import ChatOllama
except ImportError:  # pragma: no cover - safeguarded by requirements
    ChatOllama = None  # type: ignore

DEPARTMENTS: dict[str, str] = {
    "hr": "Handle onboarding, benefits, and people ops.",
    "it": "Provision access, devices, and SaaS credentials.",
    "finance": "Coordinate budgets, payments, and forecasting.",
    "strategy": "Summarise insights and recommend next steps.",
    "query": "Answer general business questions.",
}

DEFAULT_ENDPOINTS: dict[str, tuple[str, str]] = {
    "dbt": ("DBT_MCP_URL", "http://dbt-mcp:8000"),
    "pg": ("PG_MCP_URL", "http://pg-mcp:8001"),
    "sql": ("SQL_MCP_URL", "http://sql-toolbox:8000"),
    "langfuse": ("LANGFUSE_MCP_URL", "http://langfuse-mcp:8000"),
    "prefect": ("PREFECT_MCP_URL", "http://prefect-mcp:8000"),
    "outlook": ("OUTLOOK_MCP_URL", "http://outlook-mcp:8007"),
}


def build_server_config() -> dict[str, dict[str, str]]:
    """Resolve MCP endpoint URLs from the environment with sensible defaults."""
    return {
        name: {"url": os.getenv(env_var, default_url)}
        for name, (env_var, default_url) in DEFAULT_ENDPOINTS.items()
    }


async def fetch_tools_with_retry(
    client: MultiServerMCPClient, attempts: int = 5, delay_seconds: int = 3
):
    """Retry MCP tool discovery to allow dependent services time to start."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await client.get_tools()
        except Exception as exc:  # pragma: no cover - startup retry path
            last_error = exc
            wait_for = delay_seconds * attempt
            print(
                f"Waiting for MCP servers (attempt {attempt}/{attempts}) — retrying in {wait_for}s: {exc}",
                flush=True,
            )
            await asyncio.sleep(wait_for)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unable to fetch MCP tools; no attempts executed.")


def build_llm():
    """Initialise the chat model used by each departmental executor."""
    provider = os.getenv("POSEIDON_LLM_PROVIDER", "openai").lower()
    model_name = os.getenv("POSEIDON_LLM_MODEL", "gpt-4o")
    temperature = float(os.getenv("POSEIDON_LLM_TEMPERATURE", "0.0"))

    if provider == "ollama":
        if ChatOllama is None:
            raise RuntimeError("langchain-community is required for ChatOllama support.")
        base_url = os.getenv("POSEIDON_LLM_BASE_URL", "http://llm:11434")
        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=base_url,
        )

    if ChatOpenAI is None:
        raise RuntimeError("langchain-openai must be available for OpenAI-compatible providers.")

    init_kwargs: dict[str, Any] = {"model": model_name, "temperature": temperature}
    base_url = os.getenv("POSEIDON_LLM_BASE_URL")
    api_key = os.getenv("POSEIDON_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

    if base_url:
        init_kwargs["base_url"] = base_url
    if api_key:
        init_kwargs["api_key"] = api_key

    return ChatOpenAI(**init_kwargs)


async def build_mcp_graph():
    client = MultiServerMCPClient(build_server_config())

    tools = await fetch_tools_with_retry(client)
    tool_node = ToolNode(tools)
    llm = build_llm()

    def make_executor(department: str):
        async def executor(state: MessagesState) -> MessagesState:
            system_instruction = DEPARTMENTS[department]
            response: AIMessage = await llm.ainvoke(
                [SystemMessage(content=system_instruction), *state["messages"]]
            )
            return {"messages": [*state["messages"], response]}

        return executor

    def route(state: MessagesState) -> str:
        last_message = state["messages"][-1].content.lower()
        if any(keyword in last_message for keyword in ("onboard", "new hire")):
            return "hr"
        if "access" in last_message or "credential" in last_message:
            return "it"
        if "budget" in last_message or "invoice" in last_message:
            return "finance"
        if "insight" in last_message or "plan" in last_message:
            return "strategy"
        return "query"

    graph = StateGraph(MessagesState)
    for department in DEPARTMENTS:
        graph.add_node(department, make_executor(department))

    graph.add_node("tools", tool_node)
    graph.set_conditional_entry_point(route)

    for department in DEPARTMENTS:
        graph.add_edge(department, "tools")

    graph.add_edge("tools", "__end__")

    return graph.compile()


# Note: Do not create the graph at import time to avoid calling
# asyncio.run() inside ASGI startup. Import build_mcp_graph and
# construct the compiled graph during the FastAPI startup event.
