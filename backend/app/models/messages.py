from pydantic import BaseModel
from datetime import datetime


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    created_at: datetime
