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

## How It Works

The following decisions were made deliberately for the MVP and pilot phase (Sessions 1–10, up to 5 paid engagements). They optimize for speed of validation over production scalability. Each decision includes the planned migration path for when scale requires it.

```
Client uploads documents via Lovable portal
         ↓
Supabase Storage triggers n8n pipeline
         ↓
Flask extraction service (local, M4 Pro) extracts text
from PDF, DOCX, PPTX, XLSX, and image files
         ↓
Three separate Claude API calls — one per force —
extract structured evidence against framework metrics
         ↓
Fourth Claude API call detects cross-force patterns
(vicious cycles, leverage points, bottlenecks)
         ↓
Evidence surfaces in Airtable for consultant review
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
| File Storage | Supabase Storage | Raw documents and generated PDFs |
| Workflow Orchestration | n8n Cloud | All pipeline logic and API coordination |
| Document Extraction | Python Flask + ngrok | Local extraction service (pdfplumber, python-docx, python-pptx, openpyxl, Tesseract OCR) |
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
- Accounts: Anthropic, Supabase, n8n Cloud, Airtable, SendGrid, DocRaptor

### 1. Clone the repository
```bash
git clone https://github.com/[your-username]/resonance-analyzer.git
cd resonance-analyzer
```

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Tesseract OCR
```bash
brew install tesseract
```

### 4. Configure environment variables

Create a `.env` file in the project root — never commit this file:

```
ANTHROPIC_API_KEY=your_key_here
SUPABASE_URL=your_project_url
SUPABASE_SERVICE_KEY=your_service_role_key
SENDGRID_API_KEY=your_key_here
DOCRAPTOR_API_KEY=your_key_here
```

### 5. Run the Flask extraction service
```bash
python app.py
```

The service runs on `http://localhost:5000`

### 6. Expose to n8n via ngrok
```bash
ngrok http 5000
```

Copy the HTTPS forwarding URL and update the extraction service URL in your n8n Pipeline Trigger workflow.

---

## API Endpoints

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

## Architecture Decisions

Key decisions made during MVP build, documented for future contributors:

- **Three separate Claude API calls for evidence extraction** one per force (Execution, Marketing, Revenue). Execution findings are tagged to Product or Operations sub-layers. Revenue findings are tagged to Revenue Architecture, Sales Motion, or Financial Coherence sub-layers. Marketing is a singular diagnostic force with no sub-layers. A seventh Marketing metric — Sales Activation of Marketing Messaging — was added to surface the Marketing to Sales handoff breakdown. Pass 2 explicitly checks the connection between Marketing's Sales Activation findings and Revenue's Sales Motion findings as the most common cross-force breakdown in founder-led organizations. Recall target is ≥90% per force.
- **Direct injection over RAG for Phase 1** — Claude's 200K context window handles 20+ documents in a single pass. RAG evaluation triggers if cross-force pattern miss rate exceeds 15% across 3+ pilots.
- **Flask + ngrok for MVP** — Python extraction runs locally on M4 Pro, exposed to n8n Cloud via ngrok tunnel. Migration to Modal.com planned post-pilot when pipeline needs to run without local machine.
- **Airtable as evidence review UI for MVP** — replaced by custom Lovable interface in Phase 2.
- **Prompts hardcoded in n8n HTTP Request nodes** — no Supabase prompts table. Simpler architecture for MVP volume.

---

## Project Status

Currently in active MVP build. Phase 1 (extraction service) complete. Phase 2 in progress — extraction service complete, three force prompts finalized with sub-layer tagging and Sales Motion metrics, wiring into n8n in Session 3.

**Go/No-Go decision** after 5+ paid pilot engagements, evaluating:
- Evidence recall ≥90%
- Pattern detection ≥85%
- Client satisfaction ≥8/10
- Consultant time ≤6 hours per engagement

---

## Privacy & Data Handling

- All client documents and analysis stored in Supabase with encryption at rest
- Anthropic Claude API does not train on customer API data
- No client data shared with third parties
- Default retention: 90 days after delivery
- Anonymized patterns used only for internal methodology improvement

---

## License

Proprietary — Syntara Intelligence / The Resonance Field LLC. All rights reserved.

---

*"The goal is a working system serving real clients, not a perfect system sitting unused. Ship fast. Learn fast. Iterate."*
```