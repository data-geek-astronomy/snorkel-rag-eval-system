---
title: Snorkel RAG Evaluation System
sdk: gradio
sdk_version: 5.33.0
app_file: app.py
pinned: false
license: apache-2.0
tags:
  - rag
  - evaluation
  - llm-evaluation
  - n8n
  - snorkel
  - agentic-ai
  - legal-ai
  - human-in-the-loop
  - gradio
---

# 🧪 Snorkel RAG Evaluation System

**Automated evaluation pipeline for enterprise RAG agents** — Inspired by [Snorkel AI's](https://snorkel.ai) programmatic labeling methodology. Built entirely with n8n agentic workflows.

## What It Does

Upload legal/enterprise documents → Generate adversarial test questions → Evaluate a RAG agent's answers with deterministic scoring → Gate at 90% pass rate → Expert calibration loop writes corrections to a golden training dataset.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Gradio UI (Hugging Face Space)                │
│  [Ingest] [Ask Question] [Run Eval] [Dashboard] [Architecture]  │
└──────┬──────────────┬──────────────┬──────────────┬────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐
│ Document │  │   RAG    │  │   Snorkel    │  │Dashboard │
│Ingestion │  │  Query   │  │ Eval Pipeline│  │   API    │
│  Agent   │  │  Agent   │  │    Agent     │  │  Agent   │
└──────────┘  └──────────┘  └──────────────┘  └──────────┘
       │              │              │              │
       └──────────────┴──────────────┴──────────────┘
                             │
                  ┌──────────┴──────────┐
                  │    Supabase DB       │
                  │  ┌───────────────┐  │
                  │  │   documents   │  │  ← vector store (pgvector)
                  │  ├───────────────┤  │
                  │  │ eval_results  │  │  ← pass/fail logs
                  │  ├───────────────┤  │
                  │  │expert_correct │  │  ← golden dataset
                  │  └───────────────┘  │
                  └─────────────────────┘
```

## The 4 n8n Agent Workflows

| Agent | Workflow ID | Purpose |
|-------|------------|---------|
| **Document Ingestion** | `v3kxtfz9PTPPAErR` | PDF → 500-char chunks → OpenAI embeddings → Supabase vector store |
| **RAG Query** | `PPYgg6CLpKnvX1Er` | Question → embedding → similarity search → GPT-4o answers with citations |
| **Snorkel Eval Pipeline** | `CzPeQdps0o9VB9Ym` | Adversarial QA generation → programmatic scoring → 90% gate → expert form |
| **Results Dashboard** | `gRnIveT0uRVGqs1n` | Aggregates Supabase eval stats → JSON API |

## Snorkel-Inspired Scoring Logic

```
citation_checker    (40%) → regex: [Section X.Y], [Page N], [Clause N.N]
snorkel_rubric      (60%) → completeness + section coverage + conflict resolution + legal precision

final_score = (citation_score × 0.4) + (rubric_score × 0.6)
passed      = final_score ≥ 75
pass_rate   = (passed / 10 questions) × 100

PRODUCTION READY = pass_rate ≥ 90%
NEEDS REVIEW     = pass_rate < 90% → triggers expert adjudication form
```

## Setup

### 1. Supabase
```bash
# Run in Supabase SQL editor
# Creates: documents (pgvector), eval_results, expert_corrections, match_documents()
psql < supabase_schema.sql
```

### 2. n8n Environment Variables
Set in your n8n instance settings:
```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
TARGET_AGENT_API_KEY=<your-rag-agent-api-key>
```

### 3. n8n Credentials
- **OpenAI API** — for GPT-4o + embeddings
- **Supabase** — for golden dataset logging

### 4. Activate All 4 Workflows
Flip each workflow to **Active** in [n8n Cloud](https://aravind5.app.n8n.cloud).

### 5. Hugging Face Space
Set `N8N_BASE_URL` secret in the Space settings:
```
N8N_BASE_URL=https://aravind5.app.n8n.cloud
```

## Files

| File | Description |
|------|-------------|
| `app.py` | Gradio UI — connects all 4 n8n agents |
| `requirements.txt` | Python dependencies (gradio, requests) |
| `supabase_schema.sql` | Complete DB schema with pgvector, indexes, RLS |
| `workflows/` | n8n workflow JSON exports (import into any n8n instance) |

## Webhook Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhook/ingest-document` | POST | Upload PDF (multipart/form-data) |
| `/webhook/rag-query` | POST | `{"question": "..."}` |
| `/webhook/snorkel-eval-upload` | POST | Upload PDF for evaluation |
| `/webhook/eval-dashboard` | POST | `{}` → returns stats JSON |

## Related

- [Snorkel AI](https://snorkel.ai) — programmatic labeling methodology
- [n8n](https://n8n.io) — workflow automation platform
- [czlonkowski/n8n-skills](https://github.com/czlonkowski/n8n-skills) — Claude Code skills used to build this
- [Original Eval Pipeline](https://github.com/data-geek-astronomy/snorkel-rag-eval-pipeline) — standalone eval workflow
