import logging

from langsmith import traceable

from app.models.metadata import ChunkKeyTerms, DocumentMetadata
from app.services.openai_service import openrouter_client
from app.config import settings

logger = logging.getLogger(__name__)

DOC_METADATA_PROMPT = """Analyze this document and extract metadata.

Filename: {filename}

Text (first ~2000 characters):
{text_sample}

Extract:
- topic: The primary subject of the document (e.g. "machine learning", "contract law", "API documentation")
- document_type: The type of document (e.g. "research paper", "contract", "manual", "report", "readme", "tutorial", "email")
- language: ISO 639-1 language code (e.g. "en", "es", "fr")
"""

CHUNK_KEY_TERMS_PROMPT = """Extract up to 5 important keywords or named entities from this text. Focus on specific, meaningful terms that would be useful for searching.

Text:
{chunk_text}
"""


@traceable(name="extract_document_metadata")
def extract_document_metadata(text: str, filename: str) -> DocumentMetadata:
    """Extract document-level metadata using LLM structured output."""
    text_sample = text[:2000]

    response = openrouter_client.beta.chat.completions.parse(
        model=settings.openrouter_model,
        messages=[
            {
                "role": "system",
                "content": "You are a document analysis assistant. Extract structured metadata from documents accurately and concisely.",
            },
            {
                "role": "user",
                "content": DOC_METADATA_PROMPT.format(
                    filename=filename, text_sample=text_sample
                ),
            },
        ],
        response_format=DocumentMetadata,
    )

    return response.choices[0].message.parsed


@traceable(name="extract_chunk_key_terms")
def extract_chunk_key_terms(chunk_texts: list[str]) -> list[list[str]]:
    """Extract key terms for a batch of chunks (up to 5 chunks per call).

    Returns a list of key_terms lists, one per input chunk.
    """
    if not chunk_texts:
        return []

    # Build a single prompt with numbered chunks
    numbered_chunks = []
    for i, text in enumerate(chunk_texts):
        numbered_chunks.append(f"--- Chunk {i + 1} ---\n{text}")

    combined = "\n\n".join(numbered_chunks)

    prompt = (
        f"For each of the {len(chunk_texts)} chunks below, extract up to 5 important "
        "keywords or named entities. Return a JSON array of arrays, where each inner array "
        "contains the key terms for the corresponding chunk. Example for 2 chunks: "
        '[[\"term1\", \"term2\"], [\"term3\", \"term4\"]]\n\n'
        f"{combined}"
    )

    response = openrouter_client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {
                "role": "system",
                "content": "You are a keyword extraction assistant. Return ONLY valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    import json

    content = response.choices[0].message.content
    parsed = json.loads(content)

    # Handle both {"key_terms": [[...]]} and [[...]] formats
    if isinstance(parsed, dict):
        # Find the first list value in the dict
        for v in parsed.values():
            if isinstance(v, list):
                parsed = v
                break

    # Validate and normalize
    result = []
    for i in range(len(chunk_texts)):
        if i < len(parsed) and isinstance(parsed[i], list):
            terms = [str(t) for t in parsed[i][:5]]
            result.append(terms)
        else:
            result.append([])

    return result
