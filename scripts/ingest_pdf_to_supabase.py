from __future__ import annotations

import argparse
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from dotenv import load_dotenv
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db import get_supabase  # noqa: E402


MODEL_NAME = "BAAI/bge-small-en-v1.5"
EXPECTED_EMBEDDING_DIMENSIONS = 384
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 180
DEFAULT_BATCH_SIZE = 20

_model: SentenceTransformer | None = None


def model_instance() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {page_number}]\n{text}")
    return "\n\n".join(pages)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(normalized):
        chunk = normalized[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def embed(text: str) -> list[float]:
    return model_instance().encode(text, normalize_embeddings=True).tolist()


def batched(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def is_http_url(raw_path: str) -> bool:
    return urlparse(raw_path).scheme in {"http", "https"}


def source_filename(raw_source: str, fallback: str) -> str:
    parsed = urlparse(raw_source)
    if parsed.scheme in {"file", "http", "https"}:
        name = Path(unquote(parsed.path)).name
        if name:
            return name
    return fallback


def download_pdf_url(raw_url: str, destination: Path) -> None:
    with urlopen(raw_url, timeout=120) as response:
        destination.write_bytes(response.read())


def validate_remote_embedding_contract(supabase) -> None:
    probe_embedding = embed("embedding dimension check")
    if len(probe_embedding) != EXPECTED_EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"{MODEL_NAME} produced {len(probe_embedding)} dimensions, "
            f"expected {EXPECTED_EMBEDDING_DIMENSIONS}."
        )

    try:
        supabase.rpc(
            "match_rag_chunks",
            {"query_embedding": probe_embedding, "match_count": 0},
        ).execute()
    except Exception as exc:
        message = str(exc)
        if "expected 1536 dimensions" in message or "expected" in message and "dimensions" in message:
            raise RuntimeError(
                "Supabase RAG schema does not match the local embedding model. "
                f"This project uses {MODEL_NAME} ({EXPECTED_EMBEDDING_DIMENSIONS} dimensions). "
                "Run scripts/fix_supabase_rag_embedding_384.sql in the Supabase SQL editor, "
                "then rerun this ingest command."
            ) from exc
        raise


def resolve_pdf_path(raw_path: str) -> Path:
    parsed = urlparse(raw_path)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc not in {"", "localhost"}:
            path_text = f"//{parsed.netloc}{parsed.path}"
        else:
            path_text = parsed.path

        path_text = unquote(path_text)
        if len(path_text) >= 3 and path_text[0] == "/" and path_text[2] == ":":
            path_text = path_text[1:]
        return Path(path_text).expanduser().resolve()

    return Path(raw_path).expanduser().resolve()


def ingest_pdf(
    pdf_path: Path,
    *,
    title: str | None,
    storage_path: str | None = None,
    chunk_size: int,
    overlap: int,
    batch_size: int,
) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file: {pdf_path}")
    if overlap >= chunk_size:
        raise ValueError("chunk overlap must be smaller than chunk size")

    text = extract_pdf_text(pdf_path)
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        raise ValueError(f"No extractable text found in: {pdf_path}")

    document_id = f"doc-{uuid.uuid4().hex}"
    filename = title or pdf_path.name
    source_ref = storage_path or str(pdf_path)
    supabase = get_supabase()

    validate_remote_embedding_contract(supabase)

    supabase.table("rag_documents").insert(
        {
            "id": document_id,
            "filename": filename,
            "storage_path": source_ref,
        }
    ).execute()

    rows = []
    for index, chunk in enumerate(chunks):
        rows.append(
            {
                "id": f"chunk-{uuid.uuid4().hex}",
                "document_id": document_id,
                "chunk_index": index,
                "content": chunk,
                "metadata": {
                    "filename": filename,
                    "source_path": source_ref,
                    "chunk_index": index,
                    "embedding_model": MODEL_NAME,
                },
                "embedding": embed(chunk),
            }
        )

    try:
        for batch in batched(rows, batch_size):
            supabase.table("rag_chunks").insert(batch).execute()
    except Exception:
        supabase.table("rag_documents").delete().eq("id", document_id).execute()
        raise

    return f"Ingested {filename}: document_id={document_id}, chunks={len(rows)}"


def ingest_pdf_source(
    raw_source: str,
    *,
    title: str | None,
    chunk_size: int,
    overlap: int,
    batch_size: int,
) -> str:
    if is_http_url(raw_source):
        filename = title or source_filename(raw_source, "downloaded.pdf")
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / filename
            if pdf_path.suffix.lower() != ".pdf":
                pdf_path = pdf_path.with_suffix(".pdf")
            download_pdf_url(raw_source, pdf_path)
            return ingest_pdf(
                pdf_path,
                title=title or source_filename(raw_source, pdf_path.name),
                storage_path=raw_source,
                chunk_size=chunk_size,
                overlap=overlap,
                batch_size=batch_size,
            )

    pdf_path = resolve_pdf_path(raw_source)
    return ingest_pdf(
        pdf_path,
        title=title,
        storage_path=str(pdf_path),
        chunk_size=chunk_size,
        overlap=overlap,
        batch_size=batch_size,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a PDF into Supabase RAG tables.")
    parser.add_argument("pdf_path", help="Local path, file:// URI, or http(s) URL to the PDF file.")
    parser.add_argument("--title", help="Optional display filename/title stored in Supabase.")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args()


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    args = parse_args()
    message = ingest_pdf_source(
        args.pdf_path,
        title=args.title,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        batch_size=args.batch_size,
    )
    print(message)


if __name__ == "__main__":
    main()
