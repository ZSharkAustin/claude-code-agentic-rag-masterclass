import os

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from app.config import settings

os.environ["LANGSMITH_TRACING"] = settings.langsmith_tracing
os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

# OpenRouter client for chat completions
_raw_openrouter = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
)
openrouter_client = wrap_openai(_raw_openrouter)

# OpenAI client for embeddings
_raw_embedding = OpenAI(api_key=settings.openai_api_key)
embedding_client = wrap_openai(_raw_embedding)


@traceable(name="stream_chat_response")
def stream_chat_response(messages: list[dict], tools: list[dict] | None = None):
    """Stream a chat response using Chat Completions via OpenRouter."""
    kwargs = {
        "model": settings.openrouter_model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        kwargs["tools"] = tools

    response = openrouter_client.chat.completions.create(**kwargs)

    for chunk in response:
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            continue

        delta = choice.delta
        if delta.content:
            yield {"event": "delta", "data": delta.content}

        if choice.finish_reason:
            yield {"event": "done", "data": ""}


@traceable(name="chat_completion")
def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Non-streaming chat completion for tool-call detection."""
    kwargs = {
        "model": settings.openrouter_model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    response = openrouter_client.chat.completions.create(**kwargs)
    return response.choices[0].message


@traceable(name="generate_thread_title")
def generate_thread_title(user_message: str, assistant_response: str) -> str:
    """Generate a short title for a thread based on the first exchange."""
    response = openrouter_client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {
                "role": "system",
                "content": "Generate a concise 3-5 word title for a conversation. Return ONLY the title, no quotes or punctuation.",
            },
            {
                "role": "user",
                "content": f"User: {user_message}\nAssistant: {assistant_response}",
            },
        ],
    )
    return response.choices[0].message.content.strip()


@traceable(name="generate_embeddings")
def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using OpenAI text-embedding-3-small."""
    response = embedding_client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]
