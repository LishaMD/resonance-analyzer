import re
from typing import Optional
import os
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

def chunk_documents(extracted_files: list[dict]) -> list[dict]:
    """
    Takes the extracted_files list from Flask extraction service.
    Each item: {"filename": "...", "extracted_text": "..."}
    Returns a list of chunk dicts ready for embedding.
    """
    all_chunks = []

    for file in extracted_files:
        filename = file.get("filename", "unknown")
        text = file.get("extracted_text", "")
        doc_type_override = file.get("doc_type_override", "")

        # Pre-interpreted structured chunks pass through as-is
        if doc_type_override in ("spreadsheet", "crm") and file.get("tab_name"):
            chunk = make_chunk(
                text=text,
                filename=filename,
                doc_type=doc_type_override,
                structural_location=file.get("tab_name", "structured")
            )
            if chunk:
                all_chunks.append(chunk)
                print(f"  [chunker] {filename} [{file.get('tab_name')}] → 1 structured chunk")
            continue

        if not text or not text.strip():
            print(f"  [chunker] Skipping {filename} — no extracted text")
            continue

        doc_type = detect_document_type(filename, text)
        print(f"  [chunker] {filename} → type: {doc_type}")

        if doc_type == "spreadsheet":
            chunks = chunk_spreadsheet(text, filename)
        elif doc_type == "slides":
            chunks = chunk_slides(text, filename)
        elif doc_type == "crm":
            chunks = chunk_crm(text, filename)
        else:
            chunks = chunk_narrative(text, filename)

        all_chunks.extend(chunks)
        print(f"  [chunker] {filename} → {len(chunks)} chunks")

    print(f"[chunker] Total chunks produced: {len(all_chunks)}")

    # Tag chunks with relevant metrics from the knowledge graph
    all_chunks = tag_chunks_with_metrics(all_chunks)

    return all_chunks


def detect_document_type(filename: str, text: str) -> str:
    """
    Detects document type from filename extension and text signals.
    Returns: 'spreadsheet' | 'slides' | 'crm' | 'narrative'
    """
    fname = filename.lower()

    if fname.endswith((".xlsx", ".xls", ".csv")):
        # Check for CRM signals before defaulting to spreadsheet
        crm_signals = ["contact", "lead", "deal", "pipeline", "stage",
                       "account", "opportunity", "hubspot", "salesforce", "crm"]
        if any(signal in text.lower() for signal in crm_signals):
            return "crm"
        return "spreadsheet"

    if fname.endswith((".pptx", ".ppt")):
        return "slides"

    if fname.endswith((".pdf", ".docx", ".doc", ".md", ".txt", ".html")):
        return "narrative"

    # Fallback: check text signals
    if "slide" in text.lower()[:500] or "---slide" in text.lower():
        return "slides"
    if re.search(r'\t.*\t.*\t', text[:2000]):
        return "spreadsheet"

    return "narrative"


def detect_force_relevance(text: str, filename: str) -> list[str]:
    """
    Returns which forces this chunk is likely relevant to.
    Uses keyword signals — retriever.py will refine at query time.
    """
    text_lower = (text + " " + filename).lower()
    forces = []

    execution_signals = [
        "roadmap", "product", "engineering", "sprint", "milestone",
        "team", "hiring", "headcount", "org chart", "operations",
        "process", "capacity", "decision", "okr", "objective", "kpi"
    ]
    marketing_signals = [
        "positioning", "messaging", "brand", "marketing", "audience",
        "campaign", "website", "pitch", "value proposition", "tagline",
        "content", "channel", "seo", "social", "advertising"
    ]
    revenue_signals = [
        "revenue", "pricing", "sales", "mrr", "arr", "arpu", "churn",
        "pipeline", "deal", "close", "conversion", "cac", "ltv",
        "burn", "runway", "financial", "p&l", "forecast", "budget",
        "unit economics", "crm", "quota", "commission"
    ]

    if any(s in text_lower for s in execution_signals):
        forces.append("Execution")
    if any(s in text_lower for s in marketing_signals):
        forces.append("Marketing")
    if any(s in text_lower for s in revenue_signals):
        forces.append("Revenue")

    # Default to all forces if no signal detected
    if not forces:
        forces = ["Execution", "Marketing", "Revenue"]

    return forces


def detect_content_signal(text: str, doc_type: str) -> str:
    """
    Classifies the content type for retrieval precision.
    """
    text_lower = text.lower()

    if any(term in text_lower for term in ["p&l", "profit", "loss", "revenue", "expense", "ebitda"]):
        return "financial_statement"
    if any(term in text_lower for term in ["mrr", "arr", "arpu", "churn", "ltv", "cac", "burn rate", "runway"]):
        return "revenue_metrics"
    if any(term in text_lower for term in ["pipeline", "stage", "deal", "close", "won", "lost", "lead"]):
        return "sales_pipeline"
    if any(term in text_lower for term in ["headcount", "org chart", "reporting", "team size", "hire"]):
        return "org_structure"
    if any(term in text_lower for term in ["roadmap", "sprint", "milestone", "feature", "release"]):
        return "product_roadmap"
    if any(term in text_lower for term in ["positioning", "messaging", "tagline", "brand voice"]):
        return "marketing_messaging"
    if doc_type == "spreadsheet":
        return "structured_data"
    if doc_type == "slides":
        return "slide_content"
    if doc_type == "crm":
        return "crm_data"

    return "narrative_text"


def make_chunk(text: str, filename: str, doc_type: str,
               structural_location: str,
               metric_tags: Optional[list] = None) -> dict:
    """
    Assembles a chunk dict with all required metadata fields.
    """
    text = text.strip()
    if not text:
        return None

    return {
        "document_name": filename,
        "document_type": doc_type,
        "structural_location": structural_location,
        "force_relevance": detect_force_relevance(text, filename),
        "content_signal": detect_content_signal(text, doc_type),
        "metric_tags": metric_tags or [],
        "chunk_text": text,
    }


# ── CHUNKING STRATEGIES ───────────────────────────────────────────────────────

def chunk_narrative(text: str, filename: str) -> list[dict]:
    """
    Paragraph-level chunking for narrative documents.
    Splits on double newlines. Merges very short paragraphs with the next.
    Target chunk size: 200–800 words.
    """
    paragraphs = re.split(r'\n{2,}|(?=\n#{1,3} )|(?=\n[A-Z][^a-z\n]{10,}\n)', text)
    chunks = []
    buffer = ""
    para_count = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        buffer += ("\n\n" if buffer else "") + para
        para_count += 1
        word_count = len(buffer.split())

        # Emit chunk when buffer reaches target size
        if word_count >= 100:
            chunk = make_chunk(
                text=buffer,
                filename=filename,
                doc_type="narrative",
                structural_location=f"paragraphs {para_count - len(buffer.split(chr(10)*2)) + 1}–{para_count}"
            )
            if chunk:
                chunks.append(chunk)
            buffer = ""

    # Emit any remaining content
    if buffer.strip():
        chunk = make_chunk(
            text=buffer,
            filename=filename,
            doc_type="narrative",
            structural_location=f"final section"
        )
        if chunk:
            chunks.append(chunk)

    return chunks


def chunk_spreadsheet(text: str, filename: str) -> list[dict]:
    """
    Tab/section-level chunking for spreadsheet data.
    Splits on tab markers produced by openpyxl extraction.
    Each tab becomes one or more chunks depending on size.
    """
    # openpyxl extraction typically produces tab headers like:
    # "=== Sheet: Tab Name ===" or "--- Tab Name ---"
    tab_pattern = re.compile(
        r'(?:={3,}.*?sheet[:\s]+(.+?)={3,}|---\s*(.+?)\s*---)',
        re.IGNORECASE
    )

    sections = re.split(r'\n(?===|---)', text)
    chunks = []

    if len(sections) <= 1:
        # No tab markers found — treat as single block
        chunk = make_chunk(
            text=text,
            filename=filename,
            doc_type="spreadsheet",
            structural_location="full document"
        )
        if chunk:
            chunks.append(chunk)
        return chunks

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Extract tab name from header if present
        match = tab_pattern.search(section[:200])
        tab_name = (match.group(1) or match.group(2)).strip() if match else "unknown tab"

        # Split large tabs into row groups of ~50 lines
        lines = section.split("\n")
        if len(lines) > 60:
            for i in range(0, len(lines), 50):
                group = "\n".join(lines[i:i+50])
                chunk = make_chunk(
                    text=group,
                    filename=filename,
                    doc_type="spreadsheet",
                    structural_location=f"{tab_name} — rows {i+1}–{min(i+50, len(lines))}"
                )
                if chunk:
                    chunks.append(chunk)
        else:
            chunk = make_chunk(
                text=section,
                filename=filename,
                doc_type="spreadsheet",
                structural_location=tab_name
            )
            if chunk:
                chunks.append(chunk)

    return chunks


def chunk_slides(text: str, filename: str) -> list[dict]:
    """
    Slide-level chunking for presentation files.
    Splits on slide markers produced by python-pptx extraction.
    """
    # python-pptx extraction typically produces:
    # "--- Slide 1 ---" or "=== Slide 1 ==="
    slide_pattern = re.compile(r'(?:---|\===)\s*slide\s*(\d+)\s*(?:---|\===)', re.IGNORECASE)
    sections = slide_pattern.split(text)

    chunks = []

    if len(sections) <= 1:
        # No slide markers — treat as single narrative block
        return chunk_narrative(text, filename)

    # sections alternates: [pre-content, slide_num, content, slide_num, content, ...]
    i = 0
    while i < len(sections):
        if i + 1 < len(sections) and sections[i].strip().isdigit():
            slide_num = sections[i].strip()
            content = sections[i+1].strip() if i+1 < len(sections) else ""
            if content:
                chunk = make_chunk(
                    text=content,
                    filename=filename,
                    doc_type="slides",
                    structural_location=f"slide {slide_num}"
                )
                if chunk:
                    chunks.append(chunk)
            i += 2
        else:
            if sections[i].strip():
                chunk = make_chunk(
                    text=sections[i],
                    filename=filename,
                    doc_type="slides",
                    structural_location="pre-slide content"
                )
                if chunk:
                    chunks.append(chunk)
            i += 1

    # Fallback if no chunks produced
    if not chunks:
        return chunk_narrative(text, filename)

    return chunks


def chunk_crm(text: str, filename: str) -> list[dict]:
    """
    Field-group chunking for CRM exports.
    Groups related fields together rather than splitting row by row.
    """
    lines = text.strip().split("\n")
    chunks = []

    # Group into blocks of ~20 lines (captures multiple CRM records per chunk)
    group_size = 20
    for i in range(0, len(lines), group_size):
        group = "\n".join(lines[i:i+group_size]).strip()
        if not group:
            continue
        chunk = make_chunk(
            text=group,
            filename=filename,
            doc_type="crm",
            structural_location=f"records {i+1}–{min(i+group_size, len(lines))}"
        )
        if chunk:
            chunks.append(chunk)

    return chunks

def tag_chunks_with_metrics(chunks: list[dict]) -> list[dict]:
    """
    Queries FalkorDB for all metric definitions.
    Scores each chunk against each metric using keyword matching.
    Populates metric_tags with top matching metrics.
    """
    try:
        client = FalkorDB(
            host=os.getenv("FALKORDB_HOST"),
            port=int(os.getenv("FALKORDB_PORT")),
            password=os.getenv("FALKORDB_PASSWORD"),
            username=os.getenv("FALKORDB_USERNAME")
        )
        graph = client.select_graph("resonance_framework")

        # Fetch all metrics and their definitions from the graph
        result = graph.query(
            "MATCH (m:Metric) RETURN m.name as metric, m.definition as definition"
        )
        metrics = [
            {"metric": r[0], "definition": r[1]}
            for r in result.result_set
        ]
        print(f"[chunker] Loaded {len(metrics)} metrics from FalkorDB for tagging")

    except Exception as e:
        print(f"[chunker] FalkorDB unavailable for metric tagging: {e}")
        return chunks

    for chunk in chunks:
        text_lower = chunk["chunk_text"].lower()
        scores = []

        for m in metrics:
            # Score based on keyword overlap between chunk and metric definition
            definition_words = set(
                w.lower() for w in m["definition"].split()
                if len(w) > 4  # skip short stop words
            )
            metric_words = set(
                w.lower().strip("?.,") for w in m["metric"].split()
                if len(w) > 3
            )
            all_keywords = definition_words | metric_words

            matches = sum(1 for word in all_keywords if word in text_lower)
            if matches > 0:
                scores.append((m["metric"], matches))

        # Sort by match count, take top 5
        scores.sort(key=lambda x: x[1], reverse=True)
        chunk["metric_tags"] = [m for m, _ in scores[:5]]

    return chunks

# ── STANDALONE TEST ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running chunker test...")

    test_files = [
        {
            "filename": "pitch_deck.pptx",
            "extracted_text": "--- Slide 1 ---\nWe help mission-driven founders find coherence.\n\n--- Slide 2 ---\nThe problem: misalignment between execution, marketing, and revenue.\n\n--- Slide 3 ---\nOur solution: The Resonance Analyzer."
        },
        {
            "filename": "financial_model.xlsx",
            "extracted_text": "=== Sheet: P&L ===\nRevenue: $120,000\nBurn: $45,000\nRunway: 8 months\n\n=== Sheet: Unit Economics ===\nCAC: $2,400\nLTV: $10,800\nLTV:CAC ratio: 4.5"
        },
        {
            "filename": "strategy_doc.docx",
            "extracted_text": "Our mission is to democratize strategic coherence for mission-driven founders.\n\nWe believe that most organizational dysfunction is not a people problem — it is a systems problem.\n\nThe Three Forces Framework gives consultants a structured lens to diagnose where execution, marketing, and revenue are pulling against each other."
        }
    ]

    chunks = chunk_documents(test_files)
    print(f"\nTotal chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"\n── Chunk {i+1} ──")
        print(f"  document: {chunk['document_name']}")
        print(f"  type: {chunk['document_type']}")
        print(f"  location: {chunk['structural_location']}")
        print(f"  forces: {chunk['force_relevance']}")
        print(f"  signal: {chunk['content_signal']}")
        print(f"  metrics: {chunk['metric_tags']}")
        print(f"  text preview: {chunk['chunk_text'][:80]}...")