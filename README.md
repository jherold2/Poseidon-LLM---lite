# Poseidon-Lite
_A demonstration of enterprise-grade orchestration for LLM and agentic systems._

![Architecture](architecture/data_flow.png)

Poseidon-Lite is an open demonstration of how to build and orchestrate a modular **Retrieval-Augmented Generation (RAG)** and **Agentic LLM** stack — without exposing proprietary data or internal logic.  
It focuses on showing **engineering design patterns**, **modular pipeline structure**, and **production readiness** that mirror enterprise deployments.

---

## 🏗️ Architecture Overview

**High-level flow:**

Document ingestion → Text chunking → Embedding → Vector store → Retrieval → LLM Agent → Evaluation

yaml
Copy code

**Core modules:**
- **Pipelines** — Handle ingestion, preprocessing, and embeddings.
- **Agents** — Orchestrate multi-step reasoning, retrieve context, and call tools.
- **Evaluation** — Validate retrieval accuracy and latency.
- **Configs** — Store environment and model parameters with clear separation of secrets.

---

## 🧩 Example Components

| Module | Description | Key File |
|--------|--------------|----------|
| Embeddings | Converts text docs to vector embeddings using FAISS/Chroma | `src/pipelines/embed_documents.py` |
| Chunking | Splits text into semantically meaningful chunks | `src/pipelines/chunker.py` |
| Agent Orchestrator | Manages tool-calling and chain-of-thought | `src/agents/orchestrator.py` |
| Prompt Templates | Declarative prompt configurations | `src/agents/prompts/` |
| Evaluation | Benchmarking retrieval quality | `src/evaluation/eval_metrics.py` |

---

## 🚀 Quickstart

```bash
git clone https://github.com/jherold2/Poseidon-Lite.git
cd Poseidon-Lite
pip install -r requirements.txt

# Set environment variables
cp configs/secrets_template.env .env

# Run embedding and retrieval demo
python src/pipelines/embed_documents.py
python notebooks/demo_agent.ipynb
```
