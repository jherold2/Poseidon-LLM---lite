from fastapi import FastAPI
from pydantic import BaseModel

from poseidon.mcp.graph import build_mcp_graph

app = FastAPI(title="Poseidon MCP Orchestrator")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


class Query(BaseModel):
    input: str


@app.post("/orchestrate")
async def orchestrate(query: Query) -> dict[str, str]:
    graph = getattr(app.state, "graph", None)
    if graph is None:
        return {"response": "Graph not initialised"}
    result = await graph.ainvoke({"messages": [{"role": "user", "content": query.input}]})
    return {"response": result["messages"][-1].content}


@app.on_event("startup")
async def startup() -> None:
    app.state.graph = await build_mcp_graph()
