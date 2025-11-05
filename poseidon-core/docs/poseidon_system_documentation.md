# Poseidon Platform: Comprehensive System Reference

*Generated September 29, 2025 (WIB)*

Poseidon is Cedea Seafood’s internal decision-intelligence platform. It blends a locally hosted LLaMA-3-8B-Instruct model with domain agents, curated data marts, and an SOP knowledge base so that commercial, operational, and finance teams can ask complex questions and receive transparent, auditable answers. This document captures the current architecture, operating model, quantified value, and roadmap.

---

## 1. Strategic Mission & Objectives
Poseidon’s mission is to streamline decision-making while safeguarding compliance and data privacy. It behaves like a virtual operations team: a supervisor evaluates every question, allocates it to the right specialist agent, and ensures the response cites trustworthy sources.

**Key objectives**
- Deliver rapid, data-backed answers to cross-functional questions.
- Keep recommendations policy-aligned by linking to SOP excerpts.
- Maintain audit trails for every decision, escalation, and prompt update.
- Run fully on-premises to protect customer, supplier, and financial data.

---

## 2. Business Value
Poseidon produces measurable benefits across revenue, efficiency, and risk mitigation. The estimates below assume **weekly enterprise-wide orchestration cycles**, where the Task Orchestrator Agent distributes high-impact tasks to employees, the Communications Agent handles outreach and follow-ups, and the Response Listener ingests results for future reasoning. This closed-loop system transforms the platform from a passive analytics layer into an **active operational engine**.

---

### 2.1 Revenue Enhancement
- **Faster decisions (query-driven uplift)**  
  - *Context*: Routine commercial and operational questions (e.g., “Explain last week’s margin dip”, “Generate upsell for C123”) are answered in minutes instead of days, allowing managers and analysts to make more profitable decisions faster.  
  - *Assumptions*: ~10–20 high-value queries/week × 50 weeks ≈ **500–1,000 queries/year**; average uplift **USD 500 – 3,000** per query.  
  - *Calculation*: 500–1,000 queries × USD 500–3,000 = **USD 0.25M – 3.0M/year**.  
  - *Estimate*: **USD 0.25M – 3.0M/year**.

- **Faster execution (task orchestration uplift)**  
  - *Context*: AI-recommended quick actions are dispatched weekly to every employee with an Odoo account, driving immediate actions such as upsells, retention calls, or cost reductions.  
  - *Assumptions*: ~150 employees × 1 high-value task/week × 50 weeks ≈ **7,500 tasks/year**; average task value **USD 100 – 400**.  
  - *Calculation*: 7,500 tasks × USD 100–400 = **USD 0.75M – 3.0M/year**.  
  - *Estimate*: **USD 0.75M – 3.0M/year**.

- **Scalable insights**  
  - *Context*: Weekly orchestration ensures insights from new MetricFlow metrics or variance marts are **immediately operationalized** into supplier negotiations, promo optimizations, and customer campaigns.  
  - *Assumptions*: 3–5 new use cases/year; each worth ~0.5–1% of revenue uplift on a USD 10M–15M baseline.  
  - *Calculation*: USD 50K–150K per use case × 3–5 = USD 150K–750K/year.  
  - *Estimate*: **USD 0.15M–0.75M/year**.

- **Innovation enablement**  
  - *Context*: Continuous weekly task assignment enables rapid experimentation (e.g., regional bundles, pricing pilots) and **accelerates monetization cycles** for new analytics-driven revenue streams.  
  - *Assumptions*: 2–3 new streams/year contributing 0.2–0.5% of revenue.  
  - *Calculation*: USD 200K–750K/year.  
  - *Estimate*: **USD 0.2M–0.75M/year**.

**Total revenue uplift**: **USD 1.35M – 7.5M per year**.

---

### 2.2 Cost Reduction
- **Employee empowerment**  
  - *Context*: Weekly AI task distribution reduces analyst decision time, shortens onboarding, and **replaces dozens of hours of manual coordination per month**.  
  - *Assumptions*: 8–15 analysts (USD 8K–10K/year each); automation saves 15–25% of time. New hire onboarding savings for 5–10 hires/year at USD 500–800 each.  
  - *Calculation*: Analyst savings USD 20K–60K; onboarding savings USD 2.5K–8K.  
  - *Estimate*: **USD 22.5K–68K/year**.

- **Tool consolidation**  
  - *Context*: Tableau or BI subscription (~USD 2,700/year) can be retired once dashboards and action workflows are fully automated.  
  - *Estimate*: **USD 2.7K/year**.

- **Process standardization**  
  - *Context*: Weekly orchestration embeds SOP-aligned steps directly into assigned tasks, reducing rework and ensuring consistent execution across teams.  
  - *Assumptions*: 20–35% efficiency gain for 20–30 staff (USD 6K/year each).  
  - *Calculation*: USD 24K–63K/year.  
  - *Estimate*: **USD 24K–63K/year**.

**Total cost reduction**: **USD 49.2K–133.7K per year**.

---

### 2.3 Risk Mitigation & Trust
- **Proactive risk mitigation**  
  - *Context*: Weekly task cycles ensure that anomaly detection (e.g., stockouts, fraud, budget misallocations) is **translated into concrete follow-ups**, reducing exposure windows from weeks to days.  
  - *Assumptions*: 7,500 orchestrated tasks/year × USD 20–50 per task in avoided risk.  
  - *Calculation*: USD 150K–375K/year.  
  - *Estimate*: **USD 150K–375K/year**.

- **Regulatory readiness**  
  - *Context*: Every orchestrated action, notification, and employee response is logged, creating a **complete audit trail** for internal controls and regulatory reviews.  
  - *Assumptions*: 1–2 audits/year (20–30% prep savings) + one avoided penalty (USD 10K–40K).  
  - *Calculation*: USD 20K–60K/year.  
  - *Estimate*: **USD 20K–60K/year**.

- **Brand protection**  
  - *Context*: Automated tasking reduces time-to-remediation for customer-impacting issues, significantly lowering churn and reputational risks.  
  - *Assumptions*: 1–2 brand-impact events prevented annually (~USD 15K–30K each).  
  - *Calculation*: USD 15K–60K/year.  
  - *Estimate*: **USD 15K–60K/year**.

**Total risk mitigation**: **USD 185K–495K per year**.

---

### 2.4 Combined Annual Value
- Revenue uplift: **USD 1.35M – 7.5M**  
- Cost reduction: **USD 49.2K – 133.7K**  
- Risk mitigation: **USD 185K – 495K**

**Total combined annual value** (with weekly orchestration and user query assumptions): **~USD 1.58M – 8.13M per year**

---

## 3. Cost & Resource Considerations
Annual costs remain modest compared with the projected benefits. Where staffing is required, we assume an internal billing rate of 500 K IDR/hour (≈USD 32) and express effort as a single FTE figure.

| Cost Category | Low Estimate (USD) | High Estimate (USD) | FTE | Notes |
| --- | --- | --- | --- | --- |
| Infrastructure | 1,800 | 3,000 | — | RTX 3090 workstation (≈10 M IDR) plus server/SSD power and maintenance |
| ML Operations | 7,700 | 15,400 | 0.35 | dbt builds, embedding refresh, regression tests  |
| Model Maintenance | 13,800 | 27,700 | 0.30 | SFT/DPO cycles, prompt governance, GPU scheduling  |
| Change Management | 3,840 | 7,680 | 0.15 | Training, comms, support channels|
| Security & Compliance | 1,920 | 3,840 | 0.10 | Reviews, log monitoring, legal coordination  |
| **Total Annual Cost** | **26,960** | **55,820** | **0.9** |  |

### 3.1 Net Benefit Scenarios
- **Low scenario**: USD 1.58 M (combined annual value) – USD 55,820 (high-end cost) ≈ **USD 1,524,180 net benefit**  
- **High scenario**: USD 8.13 M (combined annual value) – USD 26,960 (low-end cost) ≈ **USD 8,103,040 net benefit**


Even with conservative revenue and cost assumptions, Poseidon delivers a strong ROI.

---

## 4. Architectural Framework
Poseidon is an agentic stack orchestrated by LangChain.

- **Supervisor-Orchestrated Graph** (`poseidon-core/src/poseidon/workflows/hierarchical_graph.py`): Routes queries, checks feature flags, enforces data-quality gates, and logs outcomes.
- **Domain Agents** (`poseidon-core/src/poseidon/agents/`): Sales, purchasing, logistics, manufacturing, accounting, and inference agents each own a tailored prompt and toolset.
- **Shared Utilities** (`poseidon-core/src/poseidon/tools/`): Context caching, data validation, decision logging, escalation, and feedback capture keep behavior consistent.
- **Periodized Metrics Engine** (`poseidon-cda/dbt/.../periodized_metrics/`): Weekly aggregates plus a `variance_bridge` view fuel root-cause analysis.
- **Knowledge Retrieval**: Microsoft Graph + pgvector embeddings power SOP lookups (RAG) so answers cite policy.
- **Local LLM Runtime** (`poseidon-core/src/poseidon/utils/local_llm.py`): Loads quantized LLaMA-3 models on-prem without external APIs.


### Hardware & Deployment Footprint
- **Platform**: Ubuntu/Rocky Linux appliance inside Cedea’s secure network.
- **Compute**: Dual-socket CPUs (32–64 cores) paired with a locally provisioned NVIDIA RTX 3090 for training and inference bursts.
- **Memory/Storage**: 128 GB RAM + NVMe SSDs for dbt artifacts and embedding indices.
- **Isolation**: No outbound internet; packages mirrored internally; secrets via env vars or vault.
- **Scheduling**: Cron/Prefect jobs refresh dbt models, embeddings, and anomaly checks during off-peak hours.
- **Monitoring**: Prometheus exporters log GPU utilization, inference latency, and data-quality exceptions.

---

## 5. Data Foundation
All analytics originate from the warehouse schema (`data/db_schema.json`).

| Domain | Key Table | Purpose |
| --- | --- | --- |
| Sales | `fact_sales_mv` | Pricing, channel, regional attributes |
| Purchasing | `fact_purchases` | Supplier, buyer, quantity measures |
| Inventory | `fact_inventory_mv` | Movement balances and unit costs |
| Manufacturing | `fact_production` | Manufacturing cost, yield, scheduling |
| Logistics | `fact_stock_move`, `fact_stock_move_valuation` | Stock movements and valuations |
| Accounting | `fact_accounting_invoice`, `fact_accounting_journal_mv` | Invoice and journal activity |

A total of **51 warehouse tables** are modeled, allowing cross-functional analysis without bespoke extracts.

### Metric Catalog
- `poseidon-cda/dbt/analytics/metric_catalog.yaml` defines metric names, grains, dimensions, and dependencies.
- `scripts/render_metric_catalog.py` regenerates `docs/metric_catalog.md` so analysts can browse definitions.
- Metric coverage spans Sales, Purchasing, Inventory, Logistics, Manufacturing, Accounting/Finance, and Master/Data utilities; see `docs/metric_catalog.md` for the authoritative counts.
- General-ledger driven revenue and margin KPIs now source from `fact_accounting_journal_mv`. Update the account-group filters in the catalog when the chart of accounts changes so COGS buckets (materials, labour, overhead) stay aligned with finance.

dbt's MetricFlow is a powerful abstraction layer within dbt Cloud that transforms how metrics are defined, managed, and consumed across an organization’s data ecosystem. It serves as a centralized framework for codifying business metrics—such as total net sales, inventory turnover, or production yield—in a way that ensures consistency, governance, and reusability. By bridging the gap between raw data and business users, MetricFlow enables a standardized approach to metric creation and querying, reducing the chaos of ad-hoc SQL.

Agents use the catalog to determine whether to call MetricFlow or fall back to SQL.

---

## 6. Periodized Metrics & Variance Views
Weekly aggregates provide consistent comparisons (“this week vs last week”).

- `date_spine.sql`: Calendar spine anchoring all periodizations.
- `sales_periodized.sql`: Weekly net sales, discount, and order status metrics.
- `purchasing_periodized.sql`: Supplier spend and volume trends (buyer-normalized).
- `inventory_periodized.sql`: On-hand quantity trajectories by warehouse.
- `production_periodized.sql`: Cost, units, and weight trends per production line/BOM.
- `logistics_periodized.sql`: Stock-move counts and valuation swings by picking type.
- `variance_bridge.sql`: Unifies domain variances for the `root_cause_variances` view.

### MetricFlow Benefits
- Consistent calculations across channels and regions.
- Automatic SQL joins based on requested dimensions.
- Safe drill paths (dimension/time grain metadata).
- Performance optimizations that honor dbt incremental logic.

---

## 7. Knowledge Retrieval (RAG)
Poseidon uses retrieval-augmented generation: look up policy passages, then answer.

1. **Ingestion** (`scripts/embed_sops.py`): Download SOPs via Microsoft Graph, chunk ~1,000 characters, embed with `text-embedding-3-large`, store in `analytics_semantic.sop_embeddings`.
2. **Querying** (`retrieve_similar_sop_documents`): Embed the user’s question, run pgvector similarity (`<=>`), return top passages with metadata.
3. **Response Composition**: Agents weave metric outputs with SOP citations (name, URL) so reviewers see the policy basis.

---

## 8. Agent Portfolio
Each agent inherits context from the supervisor and uses specialized tools; a dedicated communications agent handles outreach across domains. Agents operate collaboratively within the orchestration graph, passing context and results to each other so decisions, actions, and feedback form a closed loop.

- **Sales Agent**: MetricFlow first, SQL fallbacks (`query_customer_purchase_history`, `query_sales_by_category`, `query_order_status`), anomaly detection, SOP retrieval, escalation.
- **Purchasing Agent**: Supplier KPIs, spend analysis, buyer simulators, document lookup.
- **Logistics Agent**: Shipment histories, delivery status, transit & stage inventory summaries, stock-move status dashboards, freshness/null diagnostics.
- **Manufacturing Agent**: Production orders, BOM insights, yield & schedule anomalies.
- **Accounting Agent**: Ledger entries, ledger-derived revenue/COGS/operating margin KPIs (with adjustable cost buckets), financial statement ratios, payment risk scoring, budget anomalies.
- **Inference Agent**: Cross-domain reasoning—upsell opportunities, price sensitivity, margin simulations, root-cause breakdowns.
- **Communications Agent**: Looks up escalation contacts, sends notifications, and logs outreach context for auditability.
- **Task Orchestrator Agent**: Core automation engine responsible for *routing, prioritizing, and dispatching* high-impact tasks to employees across the organization. It synthesizes real-time KPI signals, department-level goals, SOP alignment, and role context to decide which task will create the highest marginal value for each user. It integrates with HR and ERP systems (e.g., Odoo) to identify eligible users, composes task payloads, attaches necessary context, and triggers automated emails (via the Communications Agent). The orchestrator runs as part of a **weekly enterprise cycle**, generating ~7,500 targeted interventions annually.
- **Task Response Listener Agent**: A passive but critical listener service that monitors incoming task responses, parses employee replies, timestamps them, and logs them into the feedback datastore (`data/task_responses.jsonl`). Responses are vectorized into a searchable feedback database and made queryable by other agents and the LLM, creating a *learning loop* that improves prioritization, action recommendations, and future orchestration decisions over time.

### Orchestration Workflow Overview
1. **Task Generation**: The Task Orchestrator Agent ranks and selects tasks for each employee based on impact scoring, department KPIs, SOP context, and current signals.  Tasks are designed to take each employee less than 30 minutes of dedicated time to complete.  
2. **Outreach and Delivery**: The Communications Agent formats and sends structured task notifications (with deadlines and CCs) to employees and their managers.
3. **Response Capture**: The Task Response Listener Agent ingests and stores incoming task outcomes from email responses.
4. **Feedback Integration**: Logged responses feed back into the context vector store, improving future task prioritization, LLM recommendations, and anomaly detection.

This **closed-loop agent ecosystem** allows Poseidon not only to generate recommendations but also to ensure they are executed, measured, and iteratively improved — a shift from static analytics to *continuous operational optimization*.

---

#### Sales Agent Prompt (Full Text)
```
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
```

This prompt locks the agent into approved tools, ensures JSON compliance, and forces explicit mention of fallbacks.

---

## 9. Inference Toolkit
The inference agent layers several quantitative modules:
- **Behavior Scoring** (`behavior_tools.py`): RFM rollups, z-score normalization, optional channel/region weighting.
- **Demand Forecasting** (`forecast_tools.py`): Prophet-style decomposition with point forecasts and quantile intervals.
- **Executive Briefing** (`executive_tools.py`): Summaries of metric deltas mapped to templated narratives.
- **Scenario Simulators** (`upsell_inference_tool`, `price_sensitivity_tool`, `margin_scenario_tool`): Elasticity heuristics test price/volume/margin outcomes.
- **Root-Cause Decomposition** (`root_cause_tool`): Uses `root_cause_variances` for dimension-level contributions.
- **Payment Risk** (`payment_risk_tool`): Threshold-based scoring on DPD buckets and historical payment behavior.

---

## 10. Tooling Ecosystem
Shared utilities power the agent workflows.
- **Metric Tools**: Attempt MetricFlow first; emit SQL fallback data and warnings when needed.
- **Data Quality Tools**: `check_table_freshness`, `check_null_rate` short-circuit risk-prone requests.
- **Document Tools**: OneDrive integration (`list/search/fetch`), plus `retrieve_similar_sop_documents` for RAG.
- **Decision Logging**: `notes_tools.record_decision` captures structured JSONL decisions.
- **Escalation**: `notification_tools.escalation_tool` composes Office365 emails for high-severity issues.
- **Escalation contacts**: `lookup_escalation_contacts` (and the companion CLI) mines module keywords, custom topics, and site filters so the communications agent targets the right recipients.
- **Context Management**: `context_tools` serves recent prompts/responses from sqlite.
- **Budget Diagnostics**: `detect_budget_allocation_anomalies` flags budget/product mismatches over configurable thresholds.

### Escalation Flow
1. Guardrails or tools flag a high-severity anomaly (budget mismatch > IDR 5M, inventory risk, stale data, fraud signal).
2. `notification_tools.escalation_tool` sends an email with context and logs the event.
3. Decision logs capture the same payload for auditability.

---

## 11. Guardrails & Compliance
Multiple safeguards keep insights reliable.
- **Freshness**: Validates key tables before execution.
- **Null Rate**: Ensures critical dimensions meet coverage thresholds.
- **Decision Trail**: JSONL logs track prompts, responses, and follow-on actions.
- **Escalation Records**: Emails/logs record severity, issue, and recipients.
- **Secret Hygiene**: Credentials pulled from environment variables (migration to a secrets manager planned).

---

## 12. Model Tuning & Evaluation
Adapter-based tuning keeps the LLM aligned with business expectations.
- **SFT** (`tuning/recipes/sft/run_sft.py` + `tuning/recipes/sft/standard_sft_v1.yaml`): Curated prompt/response pairs (LoRA adapters, batch 8–16, LR ≈ 2e-5).
- **DPO** (`tuning/recipes/dpo/run_dpo.py` + `tuning/recipes/dpo/standard_dpo_v1.yaml`): Preference pairs favour guardrail-compliant responses.
- **Synthetic Data** (`tuning/data/generate_synthetic.py`): Edge-case prompts (seasonality shifts, conflicting guardrails).
- **Evaluation Harness** (`tuning/eval/runner.py`, `tuning/eval/gate_checker.py`): Regression suites (`core_functional_v1`, `safety_redteam_v1`) enforce margin accuracy, safety, and performance gates.
- **CI Gate** (`tuning/gates/standard_v1.yaml`, `tuning/ops/ci/check_gates.py`): Blocks merges when safety/non-reg/quality/perf thresholds fail.
- **Prompt Governance**: Prompts stored in Langfuse for change tracking, with MLflow retaining experiment lineage.

---

## 13. Feedback Surfaces
The primary conversational interface is the LangGraph-backed Agent Chat UI (Next.js) documented in `docs/howto/run_agent_chat_ui.md`. It proxies requests to the FastAPI `/graph` deployment and persists feedback through `/api/v1/feedback`.

`poseidon.ui.feedback_ui` (legacy feedback console) remains in the repository solely for historical regression tests. New development should avoid the legacy surface and rely on the Agent Chat UI or direct API calls.

---

## 14. Operational Runbooks
Focus on a handful of scripts and commands to keep Poseidon healthy.
- `dbt build --select periodized_metrics`: Refresh weekly tables + variance bridge.
- `scripts/refresh_periodized_metrics.sh`: Shell wrapper supporting additional selectors.
- `python scripts/render_metric_catalog.py`: Sync documentation after catalog edits.
- `python scripts/embed_sops.py --limit 20`: Refresh embeddings (requires MS Graph + OpenAI credentials).
- `pytest`: Run automated tests across agents, tools, workflows, and utilities.
- *(Planned)* Prefect/Airflow flows: Automate guardrail checks and notifications.

---

## 15. Testing & Validation
Automated coverage ensures regressions are caught early.
- `tests/integration/test_email_tool.py`: SMTP integration contract and guardrails.
- `tests/integration/test_sales_history_queries.py`: Cache/DB interaction for sales queries.
- `test_tools.py`: Utility helpers (metric fallbacks, data-quality checks, anomaly detectors).
- `test_workflows.py`: Supervisor routing, data-quality gating, workflow sequencing.
- `test_db_connect.py`: Postgres connectivity and credential resolution.
- Domain-specific tests (`test_sales_history_queries.py`, `test_forecast_tools.py`, etc.).
- Manual drills: guardrail failure simulations, SOP retrieval spot checks.

---

## 16. Limitations & Risks
Known gaps to monitor:
- Metric definitions can drift if upstream data pipelines change.
- Prompt updates require governance to avoid conflicting instructions.
- Customer behavior shifts necessitate periodic retraining.
- SOP coverage is limited to the master folder; contracts/SLAs pending ingestion.
- Human oversight remains essential for high-impact financial or operational actions.

---

## 17. Roadmap & Future Enhancements
Planned workstreams:
- Validate and expand the metric catalog (forecasting, accounting variance) with lineage transparency.
- Add variance/delta thresholds and referential checks to data-quality rules.
- Automate guardrail execution via Prefect/Airflow with SOP-linked alerts.
- Ingest richer customer interaction data for behavioral modeling.
- Enrich the Agent Chat UI with guardrail highlights, artifact previews, and workflow timelines.
- Harden RAG by indexing contracts and SLAs with multi-document citations.
- Formalize tuning pipelines (acceptance gates, regression suites, experimental RLHF).
- Extend observability (Prometheus/Grafana), automate secret rotation, streamline deployments.

---

## 18. Reference Documentation
- LangChain: <https://python.langchain.com/>
- dbt Core: <https://docs.getdbt.com/>
- MetricFlow: <https://docs.getdbt.com/docs/get-started-dbt-metricflow>
- Langfuse: <https://langfuse.com/docs>
- Meta LLaMA: <https://ai.meta.com/llama/>
- pgvector: <https://github.com/pgvector/pgvector>
- Prophet (forecasting reference): <https://facebook.github.io/prophet/docs/quick_start.html>

---
_Positive outcomes depend on sustained catalog governance, tuning cycles, and guardrail reviews. Treat this reference as a living document—update it as new agents, metrics, or workflows launch._
*** End Patch
