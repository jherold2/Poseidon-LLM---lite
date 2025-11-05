# Run Agent Chat UI Against Poseidon

This guide replaces the legacy feedback console with the LangChain Agent Chat UI backed by a LangGraph deployment wrapped around Poseidon’s agents.

## 1. Install dependencies

```bash
pip install -r poseidon-core/config/requirements.txt
```

This pulls the LangGraph server packages (`langgraph`, `langgraph-api`, `langgraph-runtime-inmem`) alongside the existing stack.

## 2. Start the Poseidon API (with LangGraph mounted)

Launch the API using the project virtualenv so the LangGraph packages resolve correctly:

```bash
PYTHONPATH=poseidon-core/src \
  ./venv/bin/uvicorn poseidon.api:app \
  --factory --host 0.0.0.0 --port 8000
```

The FastAPI service now exposes:
- Existing orchestration endpoints (`/workflows`, `/inference`)
- LangServe playground (`/playground/...`)
- The new LangGraph deployment mounted at `/graph`

### Generate an access token

Both the LangGraph runtime and the UI proxy expect a shared bearer token:

```bash
export POSEIDON_AUTH_TOKEN=poseidon-dev-token  # override in production
```

The `/login` endpoint served by the API returns this token when the username/password
match the credentials in `.env` (`POSEIDON_LOGIN_USERNAME` / `POSEIDON_LOGIN_PASSWORD`).

## 3. Configure the Agent Chat UI

From the `ui/agent-chat-ui/` repo:

```bash
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8200/graph \
NEXT_PUBLIC_ASSISTANT_ID=poseidon-supervisor \
pnpm dev
```

Then browse to <http://localhost:3000>. The setup form will be pre-filled if you exported the environment variables; otherwise, enter:

- **Deployment URL**: `http://localhost:8200/graph`
- **Assistant / Graph ID**: `poseidon-supervisor`
- **Auth token**: paste the bearer token returned from `/login` or the value you set in `POSEIDON_AUTH_TOKEN`

## 4. Querying modules

Each user message should indicate the target module:

- Prefix style: `sales: List top 5 products by revenue`
- JSON style: `{"module": "logistics", "input": "Check stock levels for finished goods"}`

If no module is supplied, the graph defaults to the `inference` agent (or the first enabled agent if inference is disabled).

Responses render as JSON mirroring the agent output, including guardrail errors when present.

## 5. Preserving feedback

The historical feedback pipeline still writes to `poseidon-core/data/dpo_data/feedback_pairs.jsonl`. Use the `/api/v1/feedback` endpoint documented in `docs/howto/run_feedback_endpoint.md` to capture ratings after each run.

## 6. Service summary

Running the UI now involves three local processes:

1. **Poseidon FastAPI** (`uvicorn poseidon.api:app`) – orchestrates agents, exposes LangGraph and LangServe.
2. **Agent Chat UI** (`pnpm dev`) – React frontend connected to the LangGraph deployment.
3. **Local LLM runtime** (Ollama/remote host) – already required by the agents.
