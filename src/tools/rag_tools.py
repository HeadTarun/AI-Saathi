"""
RAG retrieval tool using pgvector cosine similarity.
Teacher Agent uses this to get grounded concept explanations.
Never let LLM free-generate topic content; always ground via RAG first.
"""

from langchain_core.tools import tool

from db import get_pool


async def _embed_query(query: str) -> list[float]:
    """
    Generate embedding for a query string.

    Priority order:
      1. HuggingFace sentence-transformers (local, free, no API key)
      2. OpenAI text-embedding-ada-002 (paid, 1536 dims)
      3. Ollama nomic-embed-text (local, 768 dims)

    The query model must match the model used during ingestion.
    Default: BAAI/bge-large-en-v1.5 (1024 dims; requires VECTOR(1024)).
    """
    import os

    embedder_type = os.environ.get("EMBED_PROVIDER", "huggingface")

    if embedder_type == "huggingface":
        try:
            import asyncio

            from sentence_transformers import SentenceTransformer  # type: ignore

            model_name = os.environ.get("HF_EMBED_MODEL", "BAAI/bge-large-en-v1.5")

            if (
                not hasattr(_embed_query, "_hf_model")
                or _embed_query._hf_model_name != model_name
            ):
                _embed_query._hf_model = SentenceTransformer(model_name)
                _embed_query._hf_model_name = model_name

            model = _embed_query._hf_model
            loop = asyncio.get_event_loop()

            def _encode():
                vec = model.encode(
                    query,
                    normalize_embeddings=True,
                )
                return vec.tolist()

            return await loop.run_in_executor(None, _encode)
        except ImportError:
            pass

    if embedder_type in {"openai", "huggingface"}:
        try:
            from openai import AsyncOpenAI  # type: ignore

            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            response = await client.embeddings.create(
                input=query,
                model="text-embedding-ada-002",
            )
            return response.data[0].embedding
        except Exception:
            pass

    import httpx  # type: ignore

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
