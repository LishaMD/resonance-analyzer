import os
import uuid
from dotenv import load_dotenv
from supabase import create_client
import ollama

load_dotenv()

# ── Supabase client ───────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EMBEDDING_MODEL = "bge-m3"


def embed_chunks(chunks: list[dict], client_id: str = None, engagement_id: str = None) -> list[dict]:
    """
    Takes a list of chunk dicts from chunker.py.
    Generates BGE-M3 embeddings via Ollama.
    Writes each chunk to Supabase document_chunks table.
    Returns list of chunks with their assigned Supabase IDs.
    """
    if not chunks:
        print("[embedder] No chunks to embed.")
        return []

    # Generate IDs if not provided
    client_id = client_id or str(uuid.uuid4())
    engagement_id = engagement_id or str(uuid.uuid4())

    print(f"[embedder] Embedding {len(chunks)} chunks...")
    print(f"[embedder] client_id: {client_id}")
    print(f"[embedder] engagement_id: {engagement_id}")

    embedded = []
    failed = []

    for i, chunk in enumerate(chunks):
        chunk_text = chunk.get("chunk_text", "").strip()
        if not chunk_text:
            print(f"  [embedder] Skipping chunk {i+1} — empty text")
            continue

        try:
            # Generate embedding locally via Ollama
            response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=chunk_text)
            embedding = response["embedding"]

            # Build Supabase record
            record = {
                "client_id": client_id,
                "engagement_id": engagement_id,
                "document_name": chunk.get("document_name", "unknown"),
                "document_type": chunk.get("document_type", "narrative"),
                "structural_location": chunk.get("structural_location", ""),
                "force_relevance": chunk.get("force_relevance", []),
                "metric_tags": chunk.get("metric_tags", []),
                "content_signal": chunk.get("content_signal", "narrative_text"),
                "chunk_text": chunk_text,
                "embedding": embedding,
            }

            # Write to Supabase
            result = supabase.table("document_chunks").insert(record).execute()

            if result.data:
                chunk_id = result.data[0]["id"]
                embedded.append({**chunk, "supabase_id": chunk_id})
                print(f"  [embedder] Chunk {i+1}/{len(chunks)} — {chunk.get('document_name')} [{chunk.get('structural_location')}] → written")
            else:
                print(f"  [embedder] Chunk {i+1}/{len(chunks)} — write returned no data")
                failed.append(chunk)

        except Exception as e:
            print(f"  [embedder] Chunk {i+1}/{len(chunks)} — ERROR: {e}")
            failed.append(chunk)

    print(f"\n[embedder] Complete — {len(embedded)} written, {len(failed)} failed")
    return embedded


def clear_engagement_chunks(engagement_id: str):
    """
    Deletes all chunks for a given engagement_id.
    Used when re-running the pipeline on the same engagement.
    """
    result = supabase.table("document_chunks").delete().eq("engagement_id", engagement_id).execute()
    print(f"[embedder] Cleared chunks for engagement {engagement_id}")
    return result


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from chunker import chunk_documents

    print("Running embedder test...")
    print("=" * 50)

    test_files = [
        {
            "filename": "financial_model.xlsx",
            "extracted_text": "=== Sheet: P&L ===\nRevenue: $120,000\nBurn: $45,000\nRunway: 8 months\n\n=== Sheet: Unit Economics ===\nCAC: $2,400\nLTV: $10,800\nLTV:CAC ratio: 4.5"
        },
        {
            "filename": "strategy_doc.docx",
            "extracted_text": "Our mission is to democratize strategic coherence for mission-driven founders.\n\nWe believe that most organizational dysfunction is not a people problem — it is a systems problem.\n\nThe Three Forces Framework gives consultants a structured lens to diagnose where execution, marketing, and revenue are pulling against each other."
        }
    ]

    # Step 1: Chunk
    chunks = chunk_documents(test_files)
    print(f"\nChunker produced {len(chunks)} chunks")

    # Step 2: Embed and write to Supabase
    test_client_id = str(uuid.uuid4())
    test_engagement_id = str(uuid.uuid4())

    embedded = embed_chunks(
        chunks=chunks,
        client_id=test_client_id,
        engagement_id=test_engagement_id
    )

    print(f"\n[test] Embedding complete — {len(embedded)} chunks in Supabase")
    print(f"[test] engagement_id for verification: {test_engagement_id}")

    # Step 3: Verify by reading back from Supabase
    print("\n[test] Reading back from Supabase...")
    result = supabase.table("document_chunks").select(
        "id, document_name, structural_location, force_relevance, content_signal"
    ).eq("engagement_id", test_engagement_id).execute()

    print(f"[test] Found {len(result.data)} chunks in Supabase:")
    for row in result.data:
        print(f"  {row['document_name']} [{row['structural_location']}] — {row['content_signal']} — forces: {row['force_relevance']}")