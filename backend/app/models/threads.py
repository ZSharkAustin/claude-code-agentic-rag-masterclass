from pydantic import BaseModel
from datetime import datetime


class ThreadCreate(BaseModel):
    title: str = "New Chat"


class ThreadUpdate(BaseModel):
    title: str | None = None
    last_response_id: str | None = None


class ThreadResponse(BaseModel):
    id: str
    user_id: str
    title: str
    last_response_id: str | None = None
    created_at: datetime
    updated_at: datetime
