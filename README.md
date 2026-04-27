# Resonance Analyzer
### Consulting Intelligence by Syntara Intelligence

> Compress 3–4 weeks of manual business analysis into 3–5 days.

---

## What Is This?

The Resonance Analyzer is a proprietary consulting intelligence tool built for Syntara Intelligence. It ingests a client's strategic and key business documents — pitch decks, roadmaps, financial models, org charts, sales strategies, marketing materials — and runs them through a three-force analytical framework to surface coherence gaps, cross-force patterns, and strategic leverage points.

The output is a structured evidence set and a draft Resonance Analysis Report, ready for consultant refinement and client delivery.

**The three forces:**
- **Execution** — How the organization builds and operates (product, operations, team, capacity, decisions)
- **Marketing** — How the organization communicates and positions (messaging, promises, audience clarity)
- **Revenue** — How the organization monetizes (pricing, model alignment, sales motion, financial sustainability)

**The core question:** Are these three forces pulling in the same direction — toward the heart of the business — or undermining each other?

---

## Why It Exists

Mission-driven founders experiencing organizational misalignment typically have two options: pay tens and even hundreds of thousands of dollars on a consulting engagement, or stumble through challenges internally without help. Neither serves them well.

The Resonance Analyzer makes strategic coherence analysis accessible at $1,500 per engagement by compressing the analytical labor from 80–120 hours to 3–6 hours — without sacrificing the depth that makes the insights actionable.

**This tool serves a triple purpose:**
1. Makes Syntara staff dramatically more efficient as consultants today
2. Builds the structured data layer that will power Syntara Intelligence's proprietary cross-client pattern intelligence over time
3. Sets the stage for agents that track these patterns continuously over time with a dashboard view for true coherence across business ecosystems

---

## Current Architecture

The pipeline uses a Python orchestrator with a Knowledge Graph + RAG retrieval layer to drive high-recall evidence extraction across all three forces.

```
Client uploads documents via Lovable portal
         ↓
Flask extraction service (local, M4 Pro) extracts text
from PDF, DOCX, PPTX, XLSX, and image files
         ↓
chunker.py splits extracted text into typed, metadata-tagged chunks
by document structure (narrative, spreadsheet, slides, CRM)
         ↓
embedder.py generates BGE-M3 embeddings (local via Ollama)
and writes chunks to Supabase pgvector
         ↓
retriever.py queries FalkorDB for framework context (metric definitions,
evidence signals, cross-force relationships), then retrieves
relevant document chunks from pgvector per metric
         ↓
orchestrator.py runs three separate Claude API calls — one per force —
using retrieved chunks + graph context (SPOAR loop with quality threshold)
         ↓
Fourth Claude API call detects cross-force patterns
(vicious cycles, leverage points, bottlenecks)
         ↓
Evidence surfaces in Airtable for consultant review and annotation
         ↓
Fifth Claude API call generates 6-section report draft
         ↓
Consultant refines in Lovable report editor
         ↓
DocRaptor renders branded PDF for client delivery
```

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Frontend | Lovable | Client upload portal, internal dashboard, report editor |
| Database | Supabase PostgreSQL | Clients, evidence, patterns, report drafts |
| Vector Store | Supabase pgvector | Document chunk embeddings for RAG retrieval |
| Knowledge Graph | FalkorDB (Cloud, us-east-1) | Three Forces Framework as queryable graph |
| File Storage | Supabase Storage | Raw documents and generated PDFs |
| Orchestration | Python (orchestrator.py) | All pipeline logic and API coordination |
| Document Extraction | Python Flask + ngrok | Local extraction service (pdfplumber, python-docx, python-pptx, openpyxl, Tesseract OCR) |
| Document Chunking | chunker.py | Typed, metadata-tagged chunking by document structure |
| Embedding Model | BGE-M3 via Ollama (local) | 1024-dimension embeddings — no data leaves local machine |
| Retrieval | retriever.py + LangChain | Graph query + vector search per metric |
| AI Analysis | Claude API (Sonnet 4) | Evidence extraction, pattern detection, report generation |
| Evidence Review | Airtable | Consultant annotation and review interface |
| PDF Rendering | DocRaptor | HTML to branded PDF |
| Email | SendGrid | Client confirmations and pipeline alerts |

---

## Local Setup

### Prerequisites
- Python 3.13+
- Homebrew (macOS)
- ngrok account (free tier)
- Ollama installed (ollama.com) with BGE-M3 pulled
- Accounts: Anthropic, Supabase, FalkorDB, Airtable, SendGrid, DocRaptor

### 1. Clone the repository
```bash
git clone https://github.com/[your-username]/resonance-analyzer.git
cd resonance-analyzer
```

### 2. Create and activate virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt. Always activate this before running any project commands.

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Tesseract OCR
```bash
brew install tesseract
```

### 5. Install Ollama and pull BGE-M3
Download Ollama from ollama.com and install it. Then:
```bash
ollama pull bge-m3
```

### 6. Configure environment variables

Create a `.env` file in the project root — never commit this file. It is listed in `.gitignore`.

```
ANTHROPIC_API_KEY=your_key_here
SUPABASE_URL=your_project_url
SUPABASE_SERVICE_KEY=your_service_role_key
FALKORDB_HOST=your_instance_host
FALKORDB_PORT=your_port
FALKORDB_USERNAME=falkordb
FALKORDB_PASSWORD=your_password
NGROK_URL=your_ngrok_forwarding_url
```

### 7. Seed the Knowledge Graph (one-time)

This populates FalkorDB with the Three Forces Framework — all forces, sub-layers, metrics, and relationships. Run once after setup; only re-run if the framework itself changes.

```bash
python3 build_graph.py
```

Expected output:
```
Framework graph build complete.
  Force: 3 nodes
  Metric: 30 nodes
  SubLayer: 6 nodes
  DOWNSTREAM_OF: 2 relationships
  HAS_METRIC: 30 relationships
  HAS_SUBLAYER: 6 relationships
  PAIRS_WITH: 3 relationships
```

### 8. Run the Flask extraction service
```bash
python app.py
```

The service runs on `http://localhost:5000`

### 9. Expose to pipeline via ngrok
```bash
ngrok http 5000
```

Copy the HTTPS forwarding URL and set it as `NGROK_URL` in your `.env`.

### 10. Run the pipeline
```bash
python3 orchestrator.py
```

---

## Project File Structure

```
resonance-analyzer/
├── orchestrator.py        # Main pipeline — Pass 1A/B/C + Pass 2 + SPOAR loop
├── build_graph.py         # One-time script to seed FalkorDB with framework graph
├── chunker.py             # Document chunking by type and structure (in progress)
├── embedder.py            # BGE-M3 embedding + Supabase pgvector write (in progress)
├── retriever.py           # LangChain — graph query + vector retrieval (in progress)
├── app.py                 # Flask extraction service
├── pipeline_outputs/      # JSON output from pipeline runs
├── .env                   # Environment variables (never commit)
├── .gitignore             # Excludes .env, venv, __pycache__
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

---

## Framework Structure

The Three Forces Framework is stored as a knowledge graph in FalkorDB and drives all retrieval and analysis.

**Execution Force — 13 metrics across 3 sub-layers:**
- Product: Product-Purpose Alignment, Product Vision Clarity, Roadmap-Capacity Match, Product Decision Structure, Product-Market Competitive Fit
- Operations: Organizational Structure Clarity, Hiring-Roadmap Alignment, Process Documentation, Operational Capacity Planning, Cross-functional Resource Conflicts
- Integration: Resource Allocation Coherence, Decision Velocity, Strategic Alignment

**Marketing Force — 7 metrics, no sub-layers (singular diagnostic force):**
Positioning Consistency, Promise-Reality Gaps, Audience Segmentation Clarity, Value Proposition Coherence, Messaging-Product Alignment, Transformation Claims vs. Delivery Capability, Sales Activation of Marketing Messaging

**Revenue Force — 10 metrics across 3 sub-layers:**
- Revenue Architecture: Revenue Model Alignment, Pricing-Value Coherence, Revenue-Mission Integrity, Revenue Model Sustainability
- Sales Motion: Sales Process Clarity, Sales-to-Close Friction, Pipeline and Conversion Visibility
- Financial Coherence: Unit Economics Sustainability, Financial Model Coherence, Revenue Metrics vs. Targets

**Key principle:** Sales Motion is a downstream symptom layer — it surfaces where Execution and Marketing dysfunction lands. It does not originate incoherence. One narrow exception: founder-led sales bottlenecks can be a root cause.

---

## Architecture Decisions

Key decisions made during build, documented for future contributors:

- **n8n abandoned in favor of Python orchestrator** — orchestrator.py replaced all n8n pipeline logic after the MVP validation phase. Python gives full control, easier debugging, and direct integration with the Knowledge Graph + RAG layer.

- **Knowledge Graph + RAG architecture** — FalkorDB stores the Three Forces Framework as a queryable graph. Supabase pgvector stores client document embeddings. retriever.py queries both before each Claude API call. This replaced direct injection after TerraLoop golden set testing showed ~46% overall recall on data-embedded signals (P&L anomalies, CRM field-level data, unit economics tabs) using direct injection alone.

- **BGE-M3 via Ollama for embeddings** — local embedding model chosen over OpenAI text-embedding-3-small for ethical appropriateness when handling client financial data. No client data leaves the local machine during embedding. BGE-M3 produces 1024-dimension vectors.

- **SPOAR loop in orchestrator.py** — pipeline uses a Sense→Plan→Observe→Act→Reflect loop for each pass. The Reflect stage evaluates output quality against a threshold (minimum evidence count per metric, minimum confidence levels) and loops back to Sense with enriched state if the threshold is not met, rather than moving on with insufficient evidence. SPOAR extends the OODA loop by adding an explicit Reflect stage, making the agent self-correcting rather than purely reactive.

- **Three separate Claude API calls for evidence extraction** — one per force (Execution, Marketing, Revenue). Three prompts outperform one merged prompt for recall quality. Confirmed by instructor feedback.

- **Chunking by document type** — chunker.py applies different chunking strategies by document structure: paragraph-level for narrative docs, tab/row-group for spreadsheets, slide-level for decks, field-group for CRM exports. Each chunk carries metadata tags: document name, document type, force relevance, structural location, metric tags, and content signal.

- **Flask + ngrok for extraction** — Python extraction runs locally on M4 Pro, exposed via ngrok tunnel. Migration to Modal.com planned post-pilot when pipeline needs to run without local machine.

- **Airtable as evidence review UI for MVP** — replaced by custom Lovable interface in Phase 2.

---

## Recall Baseline (TerraLoop Golden Set — April 2026)

First end-to-end pipeline run using direct injection (pre-RAG):

| Force | Found | Total | Miss Rate |
|---|---|---|---|
| Execution | 7 | 18 | 61% |
| Marketing | 6 | 14 | 57% |
| Revenue | 10 | 21 | 52% |
| Patterns | 4 | 6 | 33% |
| **Overall** | **27** | **59** | **~46%** |

Narrative text caught well. Data-embedded signals (P&L anomalies, CRM field-level, unit economics tabs) missed consistently. Knowledge Graph + RAG architecture introduced to close this gap. Recall target: ≥90% per force.

---

## Current Build Status

**Complete:**
- Flask extraction service (app.py)
- Three force prompts finalized with sub-layer tagging, Sales Motion metrics, and few-shot examples
- Pass 2 cross-force pattern detection prompt
- orchestrator.py — full pipeline running end-to-end
- TerraLoop golden set test completed
- FalkorDB instance live (us-east-1) — framework graph seeded (build_graph.py)
- Ollama + BGE-M3 installed and verified

**In progress:**
- chunker.py — typed document chunking
- embedder.py — embedding pipeline to Supabase pgvector
- retriever.py — LangChain graph + vector retrieval
- Supabase pgvector tables (document_chunks, retrieval_log)
- SPOAR loop integration into orchestrator.py

**Deferred to post-pilot:**
- Analyzer Chat (Pass 4)
- Automated anonymization pipeline
- 90-day retention automation
- Audit log UI
- Stripe-to-Wave sync
- Migration from ngrok to Modal.com

**Go/No-Go decision** after 5+ paid pilot engagements, evaluating:
- Evidence recall ≥90%
- Pattern detection ≥85%
- Client satisfaction ≥8/10
- Consultant time ≤6 hours per engagement

---

## API Endpoints (Flask Extraction Service)

### POST /extract

Accepts a JSON body with a list of file URLs and filenames. Downloads each file, extracts text, and returns a compiled response.

**Request:**
```json
{
  "files": [
    {"url": "https://your-supabase-url/storage/file.pdf", "filename": "pitch_deck.pdf"}
  ]
}
```

**Response:**
```json
{
  "files": [
    {"filename": "pitch_deck.pdf", "extracted_text": "..."},
    {"filename": "broken_file.pdf", "error": "Failed to download"}
  ]
}
```

### GET /

Health check — returns service status and supported file formats.

---

## Supported File Formats

- PDF (pdfplumber)
- DOCX (python-docx)
- PPTX (python-pptx)
- XLSX (openpyxl)
- PNG, JPG, JPEG (Tesseract OCR)

---

## Privacy & Data Handling

- All client documents and analysis stored in Supabase with encryption at rest
- BGE-M3 embeddings generated locally via Ollama — financial data never sent to third-party embedding APIs
- Anthropic Claude API does not train on customer API data
- No client data shared with third parties beyond Anthropic API calls
- Default retention: 90 days after delivery
- Anonymized patterns used only for internal methodology improvement

---

## License

Proprietary — Syntara Intelligence / The Resonance Field LLC. All rights reserved.

---

*"The goal is a working system serving real clients, not a perfect system sitting unused. Ship fast. Learn fast. Iterate."*
