# Running Prefect Flows

Poseidon's orchestration story now uses [Prefect 2](https://docs.prefect.io/) instead of the legacy Airflow DAGs that previously lived under `poseidon-cda/Airflow_DAG`.  The active flows now live under `poseidon-core/src/poseidon/prefect/flows/`, with complementary tasks under `poseidon-core/src/poseidon/prefect/tasks/`, orchestrating the three reporting pipelines plus the new Lean ingestion pipeline.

## Prerequisites

- Install the updated dependencies:

```bash
pip install -r poseidon-core/config/requirements.txt
```

- Provide the required connection details via environment variables.  The defaults match the previous Airflow configuration and can be overridden for your environment:

| Purpose              | Environment Variables (defaults shown)                                              |
|----------------------|--------------------------------------------------------------------------------------|
| Postgres source      | `PLATFORM_DB_HOST=localhost`, `PLATFORM_DB_PORT=5432`, `ANALYTICS_DB_NAME=analytics`, `ANALYTICS_DB_USER=dbt_analytics`, `ANALYTICS_DB_PASSWORD=<password>` |
| Replica / FDW        | `POSEIDON_REPLICA_HOST`, `POSEIDON_REPLICA_PORT`, `POSEIDON_REPLICA_DATABASE`, `POSEIDON_REPLICA_USER`, `POSEIDON_REPLICA_PASSWORD` *(may be set as Prefect Variables instead)* |
| Optional manifests   | `POSEIDON_PREFECT_SALES_MV`, `POSEIDON_PREFECT_ACCOUNTING_MV`, `POSEIDON_PREFECT_PRODUCTION_MV` – JSON overrides for materialised-view manifests. |
| Langfuse tracing     | `LANGFUSE_HOST`, `LANGFUSE_PROJECT_ID`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| MLflow tracking      | `MLFLOW_TRACKING_URI`, `POSEIDON_MLFLOW_EXPERIMENT` |
| Lean schema          | `POSEIDON_LEAN_SCHEMA` (defaults to `cedea_metrics`) |
| Log ingestion        | `FASTAPI_LOG_EXPORT_URL`, `OBSERVABILITY_EVENT_URL` |
| Teams alerts         | `TEAMS_WEBHOOK_URL` |

## CLI Integration

The `poseidon` CLI now exposes a `prefect` subcommand that wraps each supported flow:

```bash
# Inspect available subcommands
poseidon prefect run --help

# Refresh the sales reporting materialised views
poseidon prefect run refresh-sales-reporting

# Refresh accounting / production marts (with optional SharePoint upload)
poseidon prefect run refresh-accounting-reporting --view fact_accounting_budget_mv
poseidon prefect run refresh-production-reporting --skip-sharepoint

# Ingest Lean telemetry and rebuild the unified event log
poseidon prefect run lean-ingestion --prefect-limit 500 --dbt-select event_log_unified lean_metrics

# Run semantic-layer builds and tests
poseidon prefect run dbt-build --selector lean_metrics --selector lean_event_health

# Trigger a metric-focused dbt build via prefect-dbt
poseidon prefect run dbt-metric-build --dbt-metric-select lean_metrics+

# Execute an MLflow experiment run
poseidon prefect run mlflow-experiment --experiment poseidon-agents --run-name nightly --param lr=0.01 --metric accuracy=0.94

# Trigger a Langfuse trace run
poseidon prefect run langfuse-trace --trace-name poseidon-default --param client_id=cda --metric accuracy=0.94

# Invoke an agent batch
poseidon prefect run agent-inference --agent-name sales --prompt "Summarise week-to-date revenue"

# Trigger observability sweep and weekly reflections
poseidon prefect run observability-monitor --window-minutes 30
poseidon prefect run hansei-weekly --days-back 7

# Refresh MCP metadata for dbt semantic models
poseidon prefect run mcp-metadata-refresh

# Execute the full Lean orchestration pipeline
poseidon prefect run orchestration --run-agents

# Fire an ad-hoc Teams Andon alert
poseidon prefect run andon-alert --andon-flow-name manual-test --message "Testing Teams integration" --severity info
```

Each command streams structured logs to the existing logging subsystem. In addition, every flow run emits Prefect events (suitable for Automations) and writes a table artifact summarising the refreshed resources. Apply deployment tags (e.g., `reporting`, `sales`) when you create deployments to use tag-based concurrency in Prefect Cloud/Orion.

### Flow Overview

- **`refresh-sales-reporting`**, **`refresh-accounting-reporting`**, **`refresh-production-reporting`** – replace their respective Airflow DAGs. Prefect honours inter-view dependencies and executes the original SQL (now sourced from `airflow-temp/sql`). The production flow can optionally trigger the SharePoint export upon completion.
- **`lean-ingestion`** – orchestrates ingestion from Prefect, Langfuse, dbt, FastAPI, and observability feeds into the unified Lean event mart, then (optionally) rebuilds the `event_log_unified` and `lean_metrics` dbt models.
- **`dbt-build`** – wraps `dbt deps`, `dbt run`, and `dbt test` with optional selectors for the semantic layer.
- **`mlflow-experiment`** – manages lightweight experiment lifecycles (start run, log params/metrics, and close the run with a Kaizen note).
- **`langfuse-trace`** – manages lightweight trace lifecycles (create trace, log metrics, and ingest the latest Langfuse events).
- **`agent-inference`** – executes Poseidon’s LangChain agents (sales, purchasing, manufacturing, logistics, accounting, inference) on a schedule or batch.
- **`observability-monitor`** – polls the Lean telemetry mart for fresh anomalies and forwards them through the Andon alert flow.
- **`hansei-weekly`** – compiles recent Andon alerts into a Teams Hansei report.
- **`mcp-metadata-refresh`** – extracts dbt semantic metadata and publishes it into `lean_obs.mcp_metadata` for the MCP server.
- **`orchestration`** – coordinates the Lean ingestion, dbt builds, observability alerts, MCP refresh, and Hansei reflection in one run (optionally triggering agent batches).
- **`andon-alert`** – exposes a manual hook for raising Teams notifications from any pipeline.

## Running Flows With Prefect UI/Server

The flows are regular Prefect 2 flows; you can register them with Orion/Prefect Cloud by importing them in a deployment script, for example:

```python
from prefect.deployments import Deployment
from poseidon.prefect import refresh_sales_reporting_flow

Deployment.build_from_flow(
    flow=refresh_sales_reporting_flow,
    name="sales-refresh-hourly",
    parameters={"view_names": ["fact_sales_mv"]},
).apply()
```

You can also use the helper in `poseidon.prefect.deployments` to create deployments for reporting flows and the six work streams:

```bash
python -m poseidon.prefect.deployments --mode reporting
python -m poseidon.prefect.deployments --mode streams --queue-prefix poseidon
```

Once applied, manage schedules, tag-based concurrency limits, work pools, and workers directly in Prefect.  The CLI helper is merely a convenience for local execution and ad-hoc runs.

### Prefect Event Router Listener

To stream Prefect events into the new router, run:

```bash
python poseidon-core/scripts/prefect_event_listener.py
```

This command wires into `poseidon.prefect.events.event_router.listen_to_prefect_events()` and keeps the Andon/Kaizen/Hansei event handlers active.

### Remote Prefect API (airflow-admin@100.119.16.57)

When the Prefect backend lives on the remote controller (`airflow-admin@100.119.16.57`):

1. SSH to the box that will run deployments/workers (or forward the API port).
2. Point your shell at the remote API before running deployments or starting workers:

   ```bash
   export PREFECT_API_URL=http://100.119.16.57:4201/api
   # or activate a Prefect profile that already has this URL:
   # prefect profile use airflow-admin
   ```

3. Apply deployments / start workers as usual:

   ```bash
   python -m poseidon.prefect.deployments.reporting
   prefect worker start -p default-process-pool
   ```

Ensure firewall rules/networking allow access to `100.119.16.57:4201` when invoking the Prefect UI or API.  For stream deployments on the remote controller run:

```bash
python -m poseidon.prefect.deployments --mode streams --work-pool default --queue-prefix cedea
```

### Concurrency & Eventing

- Seven dedicated work queues (`ingestion-queue`, `dbt-queue`, `mlflow-queue`, `langfuse-queue`, `agent-queue`, `observability-queue`, `weekly-review-queue`) map to the Lean value streams. Create them with `prefect work-queue create <queue> --work-pool default` and attach workers per lane for Heijunka balancing.
- Lifecycle hooks emit Prefect events (`poseidon.prefect.<flow>.scheduled|started|completed|failed`), enabling Automations (e.g., Teams Andon alerts) without additional code.
- Table artifacts are created for every run; these show up under the flow run Artifacts tab and can be exported or queried through the Prefect API.
- An optional long-running event listener is provided at `poseidon-core/src/poseidon/prefect/events/event_router.py`; start it with `python -m poseidon.prefect.events.event_router` to stream Prefect events and fan them out to the Andon/Kaizen/Hansei handlers.

## Migration Notes

- The legacy Airflow DAGs are left in place for reference but no longer required.  All logic (SQL manifests, table lists, ClickHouse schema rules) is either re-used directly or mirrored as JSON manifests inside the new Prefect module.
- Configuration values prefer Prefect Variables (when available) and fall back to environment variables.  This allows you to manage credentials centrally without changing code.
- Observability is unified: each Prefect flow run emits lifecycle events to the Postgres telemetry tables (`telemetry.workflow_runs`, `telemetry.application_events`) and also raises Prefect events that can trigger Automations.
- For reporting purposes a Prefect table artifact summarises every run; this can be surfaced in Prefect Cloud/Orion or forwarded to Grafana/Loki alongside existing logs.
