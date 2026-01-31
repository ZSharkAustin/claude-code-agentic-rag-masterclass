from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import threads, chat, messages, documents

app = FastAPI(title="RAG Masterclass API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(threads.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(documents.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
