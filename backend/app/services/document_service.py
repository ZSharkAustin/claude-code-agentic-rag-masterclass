import io
import logging

from langsmith import traceable
from pypdf import PdfReader
from supabase import create_client

from app.config import settings
from app.services.openai_service import generate_embeddings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_BATCH_SIZE = 100


def _get_service_client():
    """Create a Supabase client with service role key (bypasses RLS)."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _extract_text(file_bytes: bytes, mime_type: str) -> str:
    """Extract text content from supported file types."""
    if mime_type == "application/pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    elif mime_type in ("text/plain", "text/markdown"):
        return file_bytes.decode("utf-8")
    else:
        raise ValueError(f"Unsupported file type: {mime_type}")


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


@traceable(name="process_document")
def process_document(document_id: str, file_path: str, mime_type: str) -> None:
    """Download, extract, chunk, embed, and store document chunks."""
    client = _get_service_client()

    try:
        # Update status to processing
        client.table("documents").update({"status": "processing"}).eq(
            "id", document_id
        ).execute()

        # Download file from Supabase Storage
        file_bytes = client.storage.from_("documents").download(file_path)

        # Extract text
        text = _extract_text(file_bytes, mime_type)
        if not text.strip():
            raise ValueError("No text content extracted from file")

        # Chunk text
        chunks = _chunk_text(text)

        # Generate embeddings in batches
        all_embeddings = []
        for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[i : i + EMBEDDING_BATCH_SIZE]
            batch_embeddings = generate_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

        # Insert chunks into DB
        rows = [
            {
                "document_id": document_id,
                "content": chunk,
                "embedding": embedding,
                "chunk_index": idx,
            }
            for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings))
        ]

        # Insert in batches of 50 to avoid payload limits
        for i in range(0, len(rows), 50):
            client.table("chunks").insert(rows[i : i + 50]).execute()

        # Update document status to ready
        client.table("documents").update(
            {"status": "ready", "chunk_count": len(chunks)}
        ).eq("id", document_id).execute()

        logger.info(
            f"Document {document_id} processed: {len(chunks)} chunks created"
        )

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        client.table("documents").update(
            {"status": "error", "error_message": str(e)}
        ).eq("id", document_id).execute()
