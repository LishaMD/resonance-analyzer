"""
TerraLoop RAG pipeline test — extracts local files directly,
bypassing Flask/ngrok for local testing.
"""

import requests
import os
import sys
import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from structured_extractor import extract_structured

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chunker import chunk_documents
from embedder import embed_chunks, clear_engagement_chunks
from retriever import retrieve_for_force, retrieve_for_pass2
from orchestrator import (
    PASS1A_TEMPLATE, PASS1B_TEMPLATE, PASS1C_TEMPLATE, PASS2_TEMPLATE,
    fill_pass1_template, fill_pass2_template, call_claude,
    write_to_supabase, write_to_airtable,
    build_evidence_supabase_record, build_evidence_airtable_record,
    build_pattern_supabase_record, build_pattern_airtable_record,
    update_supabase_pipeline_status, log,
    AIRTABLE_EVIDENCE_TABLE, AIRTABLE_PATTERNS_TABLE,
)

DOCS_FOLDER = "/Users/elishadavison/Desktop/resonance-analyzer/TerraLoop Documents"
CLIENT_ID = os.getenv("TEST_CLIENT_ID") or str(uuid.uuid4())

CLIENT_CONTEXT = {
    "company_name": "TerraLoop",
    "stage": "Series A",
    "core_purpose": "Recover and convert organic waste into high-value biological products that regenerate soil health and reduce landfill dependence.",
    "vision": "Become the leading organic waste recovery platform in the DC-Baltimore metro area, operating 3 facilities and processing 500 tons per month by 2027.",
    "objectives": "Close Series A funding, sign 3 municipal waste contracts, achieve operational breakeven at primary facility.",
    "founder_tension": "Balancing investor pressure for rapid scaling against the operational complexity of waste processing at new sites.",
}


def extract_local_files(folder_path: str) -> list:
    """Upload local files to Modal extraction service."""
    import base64
    supported = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".png", ".jpg", ".jpeg"}
    folder = Path(folder_path)
    modal_url = os.getenv("MODAL_URL")
    extracted = []

    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in supported:
            continue
        print(f"  Extracting: {f.name}")

        # Route xlsx and csv through structured extractor locally
        if f.suffix.lower() in ('.xlsx', '.xls', '.csv'):
            try:
                structured_chunks = extract_structured(str(f), f.name)
                for chunk in structured_chunks:
                    extracted.append({
                        "filename": chunk["filename"],
                        "extracted_text": chunk["extracted_text"],
                        "tab_name": chunk.get("tab_name", ""),
                        "doc_type_override": chunk.get("doc_type_override", "")
                    })
            except Exception as e:
                print(f"  ERROR extracting {f.name}: {e}")
            continue

        # Send other files to Modal
        try:
            with open(f, "rb") as fh:
                file_bytes = fh.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")

            response = requests.post(
                modal_url,
                json={"files": [{"filename": f.name, "content_b64": b64}]},
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            files = result.get("files", [])
            if files:
                extracted.append({
                    "filename": files[0].get("filename", f.name),
                    "extracted_text": files[0].get("extracted_text", "")
                })
        except Exception as e:
            print(f"  ERROR extracting {f.name}: {e}")
            extracted.append({"filename": f.name, "extracted_text": "", "error": str(e)})

    return extracted


if __name__ == "__main__":
    start = datetime.now()
    engagement_id = str(uuid.uuid4())

    print("=== TerraLoop RAG Pipeline Test ===")
    print(f"Client ID     : {CLIENT_ID}")
    print(f"Engagement ID : {engagement_id}")
    print(f"Docs folder   : {DOCS_FOLDER}")
    print("")

    # Step 1: Extract
    print("Step 1: Extracting documents...")
    extracted_docs = extract_local_files(DOCS_FOLDER)
    print(f"  {len(extracted_docs)} documents extracted")

    # Step 2: Chunk
    print("\nStep 2: Chunking documents...")
    chunks = chunk_documents(extracted_docs)
    print(f"  {len(chunks)} chunks produced")

    # Step 3: Embed
    print("\nStep 3: Embedding chunks → Supabase pgvector...")
    clear_engagement_chunks(engagement_id)
    embed_chunks(chunks, client_id=CLIENT_ID, engagement_id=engagement_id)

    # Step 4: Retrieve + Pass 1A (Execution)
    print("\nStep 4: Retrieving + Pass 1A (Execution)...")
    exec_context = retrieve_for_force("Execution", engagement_id)
    exec_findings = call_claude(
        prompt=fill_pass1_template(PASS1A_TEMPLATE, CLIENT_CONTEXT, exec_context),
        label="Pass 1A — Execution Force",
    )

    # Step 5: Retrieve + Pass 1B (Marketing)
    print("\nStep 5: Retrieving + Pass 1B (Marketing)...")
    mkt_context = retrieve_for_force("Marketing", engagement_id)
    mkt_findings = call_claude(
        prompt=fill_pass1_template(PASS1B_TEMPLATE, CLIENT_CONTEXT, mkt_context),
        label="Pass 1B — Marketing Force",
    )

    # Step 6: Retrieve + Pass 1C (Revenue)
    print("\nStep 6: Retrieving + Pass 1C (Revenue)...")
    rev_context = retrieve_for_force("Revenue", engagement_id)
    rev_findings = call_claude(
        prompt=fill_pass1_template(PASS1C_TEMPLATE, CLIENT_CONTEXT, rev_context),
        label="Pass 1C — Revenue Force",
    )

    # Step 7: Pass 2 (Cross-Force Patterns)
    print("\nStep 7: Retrieving + Pass 2 (Cross-Force Patterns)...")
    pass2_context = retrieve_for_pass2(engagement_id)
    all_findings = exec_findings + mkt_findings + rev_findings

    pass2_chunks_text = []
    for pair in pass2_context.get("pairs", []):
        pass2_chunks_text.append(f"\n── {pair['pair_name']} ──")
        for chunk in pair["retrieved_chunks"]:
            pass2_chunks_text.append(
                f"[{chunk['document_name']} / {chunk['structural_location']}]\n{chunk['chunk_text']}"
            )
    pass2_retrieved_text = "\n".join(pass2_chunks_text)

    patterns = call_claude(
        prompt=fill_pass2_template(PASS2_TEMPLATE, all_findings, pass2_retrieved_text),
        label="Pass 2 — Cross-Force Pattern Detection",
    )

    # Step 8: Save output
    print("\nStep 8: Saving output...")
    os.makedirs("pipeline_outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"pipeline_outputs/terraloop-rag-test-001_{timestamp}.json"
    with open(output_path, "w") as f:
        json.dump({
            "client_id": CLIENT_ID,
            "engagement_id": engagement_id,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_findings": exec_findings,
            "marketing_findings": mkt_findings,
            "revenue_findings": rev_findings,
            "cross_force_patterns": patterns,
        }, f, indent=2)
    print(f"  ✓ Output saved → {output_path}")

    # Step 9: Store
    print("\nStep 9: Writing to Supabase and Airtable...")
    write_to_supabase("evidence_items", [build_evidence_supabase_record(f, CLIENT_ID) for f in all_findings])
    write_to_supabase("cross_force_patterns", [build_pattern_supabase_record(p, CLIENT_ID) for p in patterns])
    write_to_airtable(AIRTABLE_EVIDENCE_TABLE, [build_evidence_airtable_record(f, CLIENT_ID) for f in all_findings])
    write_to_airtable(AIRTABLE_PATTERNS_TABLE, [build_pattern_airtable_record(p, CLIENT_ID) for p in patterns])

    elapsed = (datetime.now() - start).seconds
    print(f"\n=== Pipeline Complete in {elapsed}s ===")
    print(f"  Execution findings  : {len(exec_findings)}")
    print(f"  Marketing findings  : {len(mkt_findings)}")
    print(f"  Revenue findings    : {len(rev_findings)}")
    print(f"  Cross-force patterns: {len(patterns)}")
    print(f"  Output file         : {output_path}")