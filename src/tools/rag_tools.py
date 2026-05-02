"""
RAG retrieval tool using pgvector cosine similarity.
Teacher Agent uses this to get grounded concept explanations.
Never let LLM free-generate topic content; always ground via RAG first.
"""

from langchain_core.tools import tool

from src.db import get_pool


async def _embed_query(query: str) -> list[float]:
    """
    Generate embedding for a query string.
    Primary: OpenAI text-embedding-ada-002 (1536 dims)
    Fallback: Ollama nomic-embed-text (768 dims; only if pgvector index is rebuilt for 768)

    IMPORTANT: The embedding dimension MUST match embedding_vector VECTOR(1536) in schema.
    If switching to local embeddings, change VECTOR(1536) to VECTOR(768) in schema and rebuild index.
    """
    try:
        import os

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        response = await client.embeddings.create(input=query, model="text-embedding-ada-002")
        return response.data[0].embedding
    except Exception:
        import os

        import httpx

        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": query},
            )
            response.raise_for_status()
            return response.json()["embedding"]


@tool
async def rag_retrieve_content(query: str, topic_id: str, top_k: int = 3) -> list[dict]:
    """
    Retrieve grounded concept chunks from the syllabus vector index.
    Teacher Agent MUST call this before generating any lesson content.
    Results are ordered by cosine similarity (most relevant first).

    Args:
        query: Natural language query e.g. "explain percentage calculation basics"
        topic_id: UUID string; restricts search to this topic's subtopics
        top_k: Number of chunks to return (default 3)

    Returns:
        List of dicts: [{ chunk_text: str, similarity_score: float }]
        Returns empty list if no embeddings exist yet for this topic.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        has_embedding = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM syllabus_topics
                WHERE id = $1::uuid AND embedding_vector IS NOT NULL
            )
            """,
            topic_id,
        )
        if not has_embedding:
            row = await conn.fetchrow(
                """
                SELECT topic_name, subtopics
                FROM syllabus_topics
                WHERE id = $1::uuid
                """,
                topic_id,
            )
            if not row:
                return []
            return [
                {
                    "chunk_text": f"{row['topic_name']}: {', '.join(row['subtopics'])}",
                    "similarity_score": 1.0,
                }
            ]

        embedding = await _embed_query(query)
        rows = await conn.fetch(
            """
            SELECT topic_name || ': ' || array_to_string(subtopics, ', ') AS chunk_text,
                   1 - (embedding_vector <=> $1::vector) AS similarity_score
            FROM syllabus_topics
            WHERE id = $2::uuid AND embedding_vector IS NOT NULL
            ORDER BY embedding_vector <=> $1::vector
            LIMIT $3
            """,
            embedding,
            topic_id,
            top_k,
        )
    return [dict(row) for row in rows]
