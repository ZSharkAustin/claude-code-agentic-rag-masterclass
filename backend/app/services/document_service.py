import io
import logging
import threading
from typing import Union

from docling.datamodel.document import DocumentStream
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker import HierarchicalChunker
from docling_core.types.doc.document import DoclingDocument
from langsmith import traceable
from pypdf import PdfReader
from supabase import create_client

from app.config import settings
from app.services.metadata_service import extract_chunk_key_terms, extract_document_metadata
from app.services.openai_service import generate_embeddings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_BATCH_SIZE = 100
KEY_TERMS_BATCH_SIZE = 5

_converter: DocumentConverter | None = None
_converter_lock = threading.Lock()


def _get_converter() -> DocumentConverter:
    """Lazy-init singleton DocumentConverter (expensive to create)."""
    global _converter
    if _converter is None:
        with _converter_lock:
            if _converter is None:
                _converter = DocumentConverter()
    return _converter


def _get_service_client():
    """Create a Supabase client with service role key (bypasses RLS)."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _extract_text_pypdf(file_bytes: bytes) -> str:
    """Extract text from PDF using pypdf (fallback)."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _convert_document(
    file_bytes: bytes, mime_type: str, filename: str
) -> Union[DoclingDocument, str]:
    """Convert a document to a DoclingDocument or plain string.

    - TXT: direct UTF-8 decode → str
    - PDF, DOCX, HTML, MD: docling conversion → DoclingDocument
    - PDF fallback: if docling fails, use pypdf → str
    """
    if mime_type == "text/plain":
        return file_bytes.decode("utf-8")

    try:
        stream = DocumentStream(name=filename, stream=io.BytesIO(file_bytes))
        converter = _get_converter()
        result = converter.convert(stream)
        return result.document
    except Exception as e:
        if mime_type == "application/pdf":
            logger.warning(f"Docling PDF conversion failed, falling back to pypdf: {e}")
            return _extract_text_pypdf(file_bytes)
        raise


def _chunk_document(doc_or_text: Union[DoclingDocument, str]) -> list[str]:
    """Chunk a document using the appropriate strategy.

    - DoclingDocument: HierarchicalChunker for document-aware chunks
    - str (TXT or pypdf fallback): sliding window chunks
    """
    if isinstance(doc_or_text, str):
        chunks = []
        start = 0
        while start < len(doc_or_text):
            end = start + CHUNK_SIZE
            chunks.append(doc_or_text[start:end])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    chunker = HierarchicalChunker()
    chunks = [chunk.text for chunk in chunker.chunk(doc_or_text)]
    return chunks if chunks else [doc_or_text.export_to_text()]


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

        # Fetch filename from document record
        doc_record = (
            client.table("documents")
            .select("filename")
            .eq("id", document_id)
            .single()
            .execute()
        )
        filename = doc_record.data.get("filename", "unknown")

        # Convert document
        doc_or_text = _convert_document(file_bytes, mime_type, filename)
        text = doc_or_text if isinstance(doc_or_text, str) else doc_or_text.export_to_text()
        if not text.strip():
            raise ValueError("No text content extracted from file")

        # Chunk document
        chunks = _chunk_document(doc_or_text)

        # Extract metadata (graceful degradation — failures don't block processing)
        doc_metadata = {}
        chunk_key_terms = [[] for _ in chunks]
        try:
            meta = extract_document_metadata(text, filename)
            doc_metadata = {
                "topic": meta.topic,
                "document_type": meta.document_type,
                "language": meta.language,
            }
        except Exception as e:
            logger.warning(f"Document metadata extraction failed for {document_id}: {e}")

        try:
            all_terms = []
            for i in range(0, len(chunks), KEY_TERMS_BATCH_SIZE):
                batch = chunks[i : i + KEY_TERMS_BATCH_SIZE]
                batch_terms = extract_chunk_key_terms(batch)
                all_terms.extend(batch_terms)
            chunk_key_terms = all_terms
        except Exception as e:
            logger.warning(f"Chunk key_terms extraction failed for {document_id}: {e}")

        # Generate embeddings in batches
        all_embeddings = []
        for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[i : i + EMBEDDING_BATCH_SIZE]
            batch_embeddings = generate_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

        # Build chunk rows with metadata
        rows = [
            {
                "document_id": document_id,
                "content": chunk,
                "embedding": embedding,
                "chunk_index": idx,
                "metadata": {
                    **doc_metadata,
                    "key_terms": chunk_key_terms[idx] if idx < len(chunk_key_terms) else [],
                },
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
