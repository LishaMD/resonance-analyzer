import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from falkordb import FalkorDB
from supabase import create_client
import ollama
import numpy as np

load_dotenv()

# ── Clients ───────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

falkor = FalkorDB(
    host=os.getenv("FALKORDB_HOST"),
    port=int(os.getenv("FALKORDB_PORT")),
    password=os.getenv("FALKORDB_PASSWORD"),
    username=os.getenv("FALKORDB_USERNAME")
)
graph = falkor.select_graph("resonance_framework")

EMBEDDING_MODEL = "bge-m3"
TOP_K = 5  # chunks retrieved per metric


# ── Graph queries ─────────────────────────────────────────────────────────────

def get_force_metrics(force_name: str) -> list[dict]:
    """
    Queries FalkorDB for all metrics belonging to a force.
    Returns list of dicts with metric name, definition, and sub_layer.
    """
    result = graph.query(
        """
        MATCH (f:Force {name: $force})-[:HAS_SUBLAYER]->(s:SubLayer)-[:HAS_METRIC]->(m:Metric)
        RETURN m.name as metric, m.definition as definition, s.name as sub_layer
        UNION
        MATCH (f:Force {name: $force})-[:HAS_METRIC]->(m:Metric)
        RETURN m.name as metric, m.definition as definition, 'none' as sub_layer
        """,
        {"force": force_name}
    )
    metrics = []
    for record in result.result_set:
        metrics.append({
            "metric": record[0],
            "definition": record[1],
            "sub_layer": record[2]
        })
    return metrics


def get_cross_force_pairs() -> list[dict]:
    """
    Queries FalkorDB for all cross-force pair relationships.
    Used to drive Pass 2 retrieval.
    """
    result = graph.query(
        """
        MATCH (f1:Force)-[r:PAIRS_WITH]->(f2:Force)
        RETURN f1.name as force_1, f2.name as force_2, r.pair_name as pair_name
        """
    )
    pairs = []
    for record in result.result_set:
        pairs.append({
            "force_1": record[0],
            "force_2": record[1],
            "pair_name": record[2]
        })
    return pairs


def get_sales_motion_context() -> str:
    """
    Retrieves the Sales Motion downstream note from the graph.
    Injected into Revenue pass context.
    """
    result = graph.query(
        """
        MATCH (s:SubLayer {name: 'Sales_Motion'})
        RETURN s.note as note
        """
    )
    if result.result_set:
        return result.result_set[0][0]
    return ""


# ── Vector retrieval ──────────────────────────────────────────────────────────

def cosine_similarity(vec1: list, vec2: list) -> float:
    """Computes cosine similarity between two vectors."""
    # Handle case where Supabase returns embedding as a string
    if isinstance(vec2, str):
        vec2 = [float(x) for x in vec2.strip("[]").split(",")]
    if isinstance(vec1, str):
        vec1 = [float(x) for x in vec1.strip("[]").split(",")]
    a = np.array(vec1)
    b = np.array(vec2)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def retrieve_chunks_for_metric(
    metric_name: str,
    metric_definition: str,
    engagement_id: str,
    top_k: int = TOP_K
) -> list[dict]:
    """
    Generates an embedding for the metric definition,
    fetches all chunks for this engagement from Supabase,
    ranks by cosine similarity, returns top_k most relevant.
    """
    # Embed the metric definition as the query vector
    query_text = f"{metric_name}: {metric_definition}"
    response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=query_text)
    query_vector = response["embedding"]

   # First try chunks tagged for this specific metric
    tagged_result = supabase.table("document_chunks").select(
        "id, document_name, structural_location, force_relevance, "
        "content_signal, metric_tags, chunk_text, embedding"
    ).eq("engagement_id", engagement_id).contains("metric_tags", [metric_name]).execute()

    # Fall back to all chunks if no tagged chunks found
    if tagged_result.data and len(tagged_result.data) >= 2:
        result_data = tagged_result.data
    else:
        all_result = supabase.table("document_chunks").select(
            "id, document_name, structural_location, force_relevance, "
            "content_signal, metric_tags, chunk_text, embedding"
        ).eq("engagement_id", engagement_id).execute()
        result_data = all_result.data

    if not result_data:
        return []

    # Score each chunk by cosine similarity
    scored = []
    for chunk in result_data:
        embedding = chunk.get("embedding")
        if not embedding:
            continue
        score = cosine_similarity(query_vector, embedding)
        scored.append({**chunk, "similarity_score": score})

    # Sort by score descending, return top_k
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:top_k]


# ── Retrieval log ─────────────────────────────────────────────────────────────

def log_retrieval(
    engagement_id: str,
    pass_name: str,
    metric_queried: str,
    retrieved_chunks: list[dict]
):
    """Writes retrieval results to retrieval_log table for debugging."""
    chunk_ids = [c["id"] for c in retrieved_chunks]
    scores = [round(c["similarity_score"], 4) for c in retrieved_chunks]

    supabase.table("retrieval_log").insert({
        "engagement_id": engagement_id,
        "pass": pass_name,
        "metric_queried": metric_queried,
        "chunks_retrieved": chunk_ids,
        "retrieval_score": scores,
    }).execute()


# ── Main retrieval functions ──────────────────────────────────────────────────

def retrieve_for_force(
    force_name: str,
    engagement_id: str,
    log: bool = True
) -> dict:
    """
    Main function for Pass 1 retrieval.
    Queries FalkorDB for all metrics in a force,
    retrieves relevant chunks per metric from pgvector,
    returns structured context ready for Claude.
    """
    print(f"\n[retriever] Retrieving for {force_name} force...")

    metrics = get_force_metrics(force_name)
    print(f"[retriever] {len(metrics)} metrics found in graph")

    metric_contexts = []

    for m in metrics:
        chunks = retrieve_chunks_for_metric(
            metric_name=m["metric"],
            metric_definition=m["definition"],
            engagement_id=engagement_id
        )

        if log and chunks:
            log_retrieval(
                engagement_id=engagement_id,
                pass_name=f"pass_1_{force_name.lower()}",
                metric_queried=m["metric"],
                retrieved_chunks=chunks
            )

        metric_contexts.append({
            "metric": m["metric"],
            "sub_layer": m["sub_layer"],
            "definition": m["definition"],
            "retrieved_chunks": [
                {
                    "document_name": c["document_name"],
                    "structural_location": c["structural_location"],
                    "content_signal": c["content_signal"],
                    "chunk_text": c["chunk_text"],
                    "similarity_score": round(c["similarity_score"], 4)
                }
                for c in chunks
            ]
        })

        chunk_count = len(chunks)
        top_score = round(chunks[0]["similarity_score"], 4) if chunks else 0
        print(f"  {m['metric']}: {chunk_count} chunks retrieved (top score: {top_score})")

    # Add Sales Motion context note if Revenue force
    sales_motion_note = ""
    if force_name == "Revenue":
        sales_motion_note = get_sales_motion_context()

    return {
        "force": force_name,
        "metrics": metric_contexts,
        "sales_motion_note": sales_motion_note
    }


def retrieve_for_pass2(engagement_id: str, log: bool = True) -> dict:
    """
    Retrieval for Pass 2 cross-force pattern detection.
    Queries FalkorDB for force pairs,
    retrieves chunks relevant to each pair.
    """
    print(f"\n[retriever] Retrieving for Pass 2 cross-force patterns...")

    pairs = get_cross_force_pairs()
    pair_contexts = []

    for pair in pairs:
        query_text = (
            f"Cross-force patterns between {pair['force_1']} and {pair['force_2']}: "
            f"contradictions, resource mismatches, promise-delivery gaps, reinforcing cycles"
        )
        response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=query_text)
        query_vector = response["embedding"]

        # Fetch all chunks for this engagement
        result = supabase.table("document_chunks").select(
            "id, document_name, structural_location, force_relevance, "
            "content_signal, chunk_text, embedding"
        ).eq("engagement_id", engagement_id).execute()

        if not result.data:
            continue

        # Score and filter to chunks relevant to either force in the pair
        scored = []
        for chunk in result.data:
            embedding = chunk.get("embedding")
            if not embedding:
                continue
            forces = chunk.get("force_relevance", [])
            if pair["force_1"] not in forces and pair["force_2"] not in forces:
                continue
            score = cosine_similarity(query_vector, embedding)
            scored.append({**chunk, "similarity_score": score})

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_chunks = scored[:TOP_K]

        if log and top_chunks:
            log_retrieval(
                engagement_id=engagement_id,
                pass_name="pass_2",
                metric_queried=pair["pair_name"],
                retrieved_chunks=top_chunks
            )

        pair_contexts.append({
            "pair_name": pair["pair_name"],
            "force_1": pair["force_1"],
            "force_2": pair["force_2"],
            "retrieved_chunks": [
                {
                    "document_name": c["document_name"],
                    "structural_location": c["structural_location"],
                    "content_signal": c["content_signal"],
                    "chunk_text": c["chunk_text"],
                    "similarity_score": round(c["similarity_score"], 4)
                }
                for c in top_chunks
            ]
        })

        print(f"  {pair['pair_name']}: {len(top_chunks)} chunks retrieved")

    return {"pairs": pair_contexts}


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from chunker import chunk_documents
    from embedder import embed_chunks

    print("Running retriever test...")
    print("=" * 50)

    # Step 1: Chunk and embed test documents
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

    engagement_id = str(uuid.uuid4())
    print(f"Test engagement_id: {engagement_id}")

    chunks = chunk_documents(test_files)
    embed_chunks(chunks, engagement_id=engagement_id)

    # Step 2: Test force retrieval
    print("\n── Testing Revenue force retrieval ──")
    revenue_context = retrieve_for_force("Revenue", engagement_id)

    print(f"\nRevenue context summary:")
    for m in revenue_context["metrics"]:
        chunk_count = len(m["retrieved_chunks"])
        if chunk_count > 0:
            top_score = m["retrieved_chunks"][0]["similarity_score"]
            print(f"  {m['metric']}: {chunk_count} chunks (top: {top_score})")

    # Step 3: Test Pass 2 retrieval
    print("\n── Testing Pass 2 retrieval ──")
    pass2_context = retrieve_for_pass2(engagement_id)

    print(f"\nPass 2 context summary:")
    for pair in pass2_context["pairs"]:
        print(f"  {pair['pair_name']}: {len(pair['retrieved_chunks'])} chunks")

    print("\n[test] Retriever test complete.")