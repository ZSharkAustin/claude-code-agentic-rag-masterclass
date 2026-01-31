from pydantic import BaseModel
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    status: str
    chunk_count: int
    content_hash: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
