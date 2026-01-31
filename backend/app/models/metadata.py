from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Document-level metadata extracted via LLM."""

    topic: str | None = Field(None, description="Primary subject of the document")
    document_type: str | None = Field(
        None, description='e.g. "research paper", "contract", "manual", "report"'
    )
    language: str = Field("en", description="ISO 639-1 language code")


class ChunkKeyTerms(BaseModel):
    """Key terms extracted from a single chunk."""

    key_terms: list[str] = Field(
        default_factory=list,
        description="Up to 5 important keywords or entities from the text",
        max_length=5,
    )


class ChunkMetadata(BaseModel):
    """Combined metadata stored on each chunk."""

    topic: str | None = None
    document_type: str | None = None
    key_terms: list[str] = Field(default_factory=list)
    language: str = "en"
