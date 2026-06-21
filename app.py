"""
Snorkel RAG Evaluation System — Gradio UI
Connects to n8n agent webhooks for document ingestion, RAG querying,
eval pipeline triggering, and dashboard display.
"""

import gradio as gr
import requests
import json
import os
from datetime import datetime

# ── N8N WEBHOOK ENDPOINTS ─────────────────────────────────────────────────────
N8N_BASE = os.getenv("N8N_BASE_URL", "https://aravind5.app.n8n.cloud")
INGEST_URL = f"{N8N_BASE}/webhook/ingest-document"
QUERY_URL  = f"{N8N_BASE}/webhook/rag-query"
EVAL_URL   = f"{N8N_BASE}/webhook/snorkel-eval-upload"
DASH_URL   = f"{N8N_BASE}/webhook/eval-dashboard"

HEADERS = {"Content-Type": "application/json"}

# ── HELPER ────────────────────────────────────────────────────────────────────
def safe_post(url, **kwargs):
    try:
        r = requests.post(url, timeout=120, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "Request timed out (>120s). The n8n workflow may still be running."}
    except requests.exceptions.ConnectionError:
        return {"error": f"Cannot connect to n8n at {N8N_BASE}. Check N8N_BASE_URL env var."}
    except Exception as e:
        return {"error": str(e)}

# ── TAB 1: INGEST DOCUMENT ────────────────────────────────────────────────────
def ingest_document(pdf_file):
    if pdf_file is None:
        return "⚠️ Please upload a PDF file first.", None
    try:
        pdf_path = pdf_file if isinstance(pdf_file, str) else pdf_file.name
        with open(pdf_path, "rb") as f:
            files = {"data": (os.path.basename(pdf_path), f, "application/pdf")}
            r = requests.post(INGEST_URL, files=files, timeout=300)
            r.raise_for_status()
            result = r.json()
        chunks = result.get("chunks_stored", "?")
        source = os.path.basename(pdf_path)
        return (
            f"✅ **Document Ingested Successfully**\n\n"
            f"- **File**: {source}\n"
            f"- **Chunks stored**: {chunks}\n"
            f"- **Vector store**: Supabase (text-embedding-3-small)\n"
            f"- **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"You can now query this document in the **Ask Question** tab or run evaluation below."
        ), pdf_path
    except Exception as e:
        return f"❌ Ingestion failed: {e}\n\nMake sure the n8n Document Ingestion Agent is active.", None

# ── TAB 2: RAG QUERY ──────────────────────────────────────────────────────────
def query_rag(question):
    if not question.strip():
        return "", "", 0, ""
    result = safe_post(QUERY_URL, json={"question": question})
    if "error" in result:
        return f"❌ {result['error']}", "", 0, ""

    answer     = result.get("answer", "No answer returned.")
    citations  = result.get("citations", [])
    confidence = int(result.get("confidence", 0) * 100)
    sources    = ", ".join(result.get("sources_used", []))
    chunks     = result.get("chunks_found", 0)

    citation_md = "\n".join(f"- `{c}`" for c in citations) if citations else "- None found"
    meta = f"**Sources**: {sources} | **Chunks retrieved**: {chunks} | **Query ID**: {result.get('query_id','')}"

    return answer, citation_md, confidence, meta

# ── TAB 3: RUN EVALUATION ─────────────────────────────────────────────────────
def run_eval(stored_path):
    if not stored_path:
        return "⚠️ No document ingested yet. Please upload a PDF in the **Ingest Document** tab first."
    try:
        pdf_path = stored_path
        with open(pdf_path, "rb") as f:
            files = {"data": (os.path.basename(pdf_path), f, "application/pdf")}
            r = requests.post(EVAL_URL, files=files, timeout=60)
            r.raise_for_status()

        source = os.path.basename(pdf_path)
        return (
            f"🚀 **Evaluation Pipeline Started**\n\n"
            f"- **Document**: {source}\n"
            f"- **Pipeline**: Generating questions → RAG queries → Scoring → Logging\n"
            f"- **Started at**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⏳ Results will be ready in **~2 minutes**.\n\n"
            f"👉 Go to the **📊 Dashboard** tab and click **Refresh Dashboard** to see your results."
        )
    except Exception as e:
        return f"❌ Evaluation trigger failed: {e}"

# ── TAB 4: DASHBOARD ──────────────────────────────────────────────────────────
def load_dashboard():
    result = safe_post(DASH_URL, json={})
    if "error" in result:
        return f"❌ {result['error']}", "No data", "No data"

    summary = result.get("summary", {})
    rc      = result.get("root_cause_breakdown", {})
    recent  = result.get("recent_runs", [])

    summary_md = (
        f"### Overall Statistics\n"
        f"| Metric | Value |\n|--------|-------|\n"
        f"| Total Eval Runs | {summary.get('total_runs', 0)} |\n"
        f"| Avg Pass Rate | **{summary.get('avg_pass_rate', 0)}%** |\n"
        f"| Avg Score | {summary.get('avg_score', 0)}/100 |\n"
        f"| Production Ready | {summary.get('production_ready_count', 0)} |\n"
        f"| Needs Review | {summary.get('needs_review_count', 0)} |\n"
        f"| Expert Corrections | {summary.get('total_corrections', 0)} |\n"
    )

    rc_md = "### Root Cause Breakdown\n"
    if rc:
        rc_md += "\n".join(f"- **{k}**: {v} occurrence(s)" for k, v in rc.items())
    else:
        rc_md += "_No failures recorded yet._"

    recent_md = "### Recent Evaluation Runs\n"
    if recent:
        recent_md += "| Run ID | Pass Rate | Status |\n|--------|-----------|--------|\n"
        for r in recent[:5]:
            icon = "🟢" if r.get("pass_rate", 0) >= 90 else "🔴"
            recent_md += f"| `{r.get('eval_run_id','?')[:12]}...` | {r.get('pass_rate','?')}% | {icon} {r.get('status','?')} |\n"
    else:
        recent_md += "_No runs yet. Trigger an evaluation in the **Run Evaluation** tab._"

    return summary_md, rc_md, recent_md

# ── BUILD UI ──────────────────────────────────────────────────────────────────
THEME = gr.themes.Soft(
    primary_hue="violet",
    secondary_hue="indigo",
    neutral_hue="slate",
)

with gr.Blocks(title="Snorkel RAG Evaluation System", theme=THEME) as demo:
    last_pdf = gr.State(None)  # stores path of last ingested PDF
    gr.Markdown("""
    # 🧪 Snorkel RAG Evaluation System
    **Automated evaluation pipeline for enterprise RAG agents** — Inspired by Snorkel AI's programmatic labeling methodology.

    > Upload legal documents → Generate adversarial test questions → Evaluate RAG agent with deterministic scoring → Expert calibration loop
    """)

    with gr.Tabs():

        # ── TAB 1: INGEST ─────────────────────────────────────────────────────
        with gr.Tab("📄 Ingest Document"):
            gr.Markdown("### Upload a PDF to the vector store\nThe document will be chunked (500-char segments) and embedded using OpenAI `text-embedding-3-small`, then stored in Supabase for RAG querying and evaluation.")
            with gr.Row():
                ingest_file = gr.File(label="Upload PDF", file_types=[".pdf"])
            ingest_btn    = gr.Button("Ingest Document →", variant="primary")
            ingest_result = gr.Markdown(label="Result")
            ingest_btn.click(fn=ingest_document, inputs=ingest_file, outputs=[ingest_result, last_pdf])

        # ── TAB 2: QUERY ──────────────────────────────────────────────────────
        with gr.Tab("💬 Ask Question (RAG)"):
            gr.Markdown("### Query the ingested documents\nAsk any question — the RAG agent will retrieve relevant chunks and answer with citations.")
            question_box = gr.Textbox(
                label="Your Question",
                placeholder="e.g. What is the liability cap in Section 4 and does it conflict with Section 9?",
                lines=2
            )
            query_btn = gr.Button("Ask RAG Agent →", variant="primary")
            with gr.Row():
                with gr.Column():
                    answer_box = gr.Markdown(label="Answer")
                with gr.Column():
                    citations_box = gr.Markdown(label="Citations")
            with gr.Row():
                confidence_slider = gr.Slider(0, 100, label="Confidence Score", interactive=False)
                meta_box = gr.Markdown(label="Metadata")
            query_btn.click(
                fn=query_rag,
                inputs=question_box,
                outputs=[answer_box, citations_box, confidence_slider, meta_box]
            )

        # ── TAB 3: EVAL ───────────────────────────────────────────────────────
        with gr.Tab("🔬 Run Evaluation"):
            gr.Markdown("""
            ### Trigger the Snorkel RAG Evaluation Pipeline
            Uses the document you already ingested — no re-upload needed.
            The pipeline will:
            1. Generate adversarial questions with GPT-4o
            2. Query your RAG agent for each question
            3. Score with `citation_checker` + `snorkel_rubric_evaluator`
            4. Gate at 90% pass rate → Production Ready or Expert Review
            """)
            eval_btn    = gr.Button("Run Evaluation Pipeline →", variant="primary")
            eval_result = gr.Markdown(label="Evaluation Result")
            gr.Markdown("> ⏳ Pipeline runs async — results appear in the Dashboard tab in ~2 minutes.")
            eval_btn.click(fn=run_eval, inputs=last_pdf, outputs=eval_result)

        # ── TAB 4: DASHBOARD ──────────────────────────────────────────────────
        with gr.Tab("📊 Dashboard"):
            gr.Markdown("### Evaluation Results Dashboard\nReal-time stats from Supabase — all eval runs, pass rates, root cause breakdown.")
            dash_btn = gr.Button("Refresh Dashboard →", variant="secondary")
            with gr.Row():
                summary_box = gr.Markdown(label="Summary")
            with gr.Row():
                with gr.Column():
                    rc_box = gr.Markdown(label="Root Causes")
                with gr.Column():
                    recent_box = gr.Markdown(label="Recent Runs")
            dash_btn.click(fn=load_dashboard, outputs=[summary_box, rc_box, recent_box])

        # ── TAB 5: ARCHITECTURE ───────────────────────────────────────────────
        with gr.Tab("🏗️ Architecture"):
            gr.Markdown("""
            ### System Architecture

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
                              │  │   documents   │  │  ← vector store
                              │  │  (pgvector)   │  │
                              │  ├───────────────┤  │
                              │  │ eval_results  │  │  ← pass/fail logs
                              │  ├───────────────┤  │
                              │  │ expert_correct│  │  ← golden dataset
                              │  └───────────────┘  │
                              └─────────────────────┘
            ```

            ### The 4 n8n Agent Workflows

            | Agent | n8n Workflow ID | Purpose |
            |-------|----------------|---------|
            | Document Ingestion | `v3kxtfz9PTPPAErR` | PDF → chunks → embeddings → Supabase |
            | RAG Query | *(deployed)* | Question → similarity search → GPT-4o answer |
            | Snorkel Eval Pipeline | `CzPeQdps0o9VB9Ym` | Synthetic QA → programmatic scoring → 90% gate |
            | Results Dashboard | *(deployed)* | Aggregate Supabase stats → JSON |

            ### Snorkel-Inspired Scoring
            ```
            final_score = (citation_score × 0.4) + (rubric_score × 0.6)
            passed      = final_score ≥ 75
            pass_rate   = (passed / total) × 100
            PRODUCTION  = pass_rate ≥ 90%
            ```

            ### Tech Stack
            - **n8n Cloud** — workflow orchestration (aravind5.app.n8n.cloud)
            - **OpenAI GPT-4o** — question generation + RAG answering
            - **OpenAI text-embedding-3-small** — document + query embeddings
            - **Supabase pgvector** — vector similarity search
            - **Gradio** — this UI (hosted on Hugging Face Spaces)
            """)

    gr.Markdown("""
    ---
    **GitHub**: [data-geek-astronomy/snorkel-rag-eval-system](https://github.com/data-geek-astronomy/snorkel-rag-eval-system) |
    **n8n Cloud**: [aravind5.app.n8n.cloud](https://aravind5.app.n8n.cloud) |
    Built with n8n Workflow SDK + Snorkel AI methodology
    """)

if __name__ == "__main__":
    demo.launch()
