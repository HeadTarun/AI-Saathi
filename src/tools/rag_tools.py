from __future__ import annotations

from langchain_core.tools import tool
from sentence_transformers import SentenceTransformer

from db import get_supabase


MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model: SentenceTransformer | None = None


def _model_instance() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _embed_query(query: str) -> list[float]:
    return _model_instance().encode(query, normalize_embeddings=True).tolist()


def _topic_fallback(query: str, topic_id: str, top_k: int) -> list[dict]:
    if not topic_id:
        return []
    row = (
        get_supabase()
        .table("syllabus_topics")
        .select("topic_name,subtopics")
        .eq("id", topic_id)
        .limit(1)
        .execute()
        .data
    )
    if not row:
        return []
    topic = row[0]
    subtopics = topic.get("subtopics") or []
    chunk = f"{topic['topic_name']}: {', '.join(subtopics) if subtopics else query}"
    return [
        {
            "chunk_text": chunk,
            "similarity_score": 1.0,
            "document_id": None,
            "metadata": {"source": "syllabus_topics", "topic_id": topic_id},
        }
    ][:top_k]


@tool
async def rag_retrieve_content(query: str, topic_id: str = "", top_k: int = 5) -> list[dict]:
    """Retrieve PDF RAG chunks from Supabase using Hugging Face embeddings."""
    try:
        rows = (
            get_supabase()
            .rpc(
                "match_rag_chunks",
                {
                    "query_embedding": _embed_query(query),
                    "match_count": top_k,
                },
            )
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []

    if not rows:
        return _topic_fallback(query, topic_id, top_k)

    return [
        {
            "chunk_text": row["content"],
            "similarity_score": row["similarity"],
            "document_id": row["document_id"],
            "metadata": row.get("metadata") or {},
        }
        for row in rows
    ]

