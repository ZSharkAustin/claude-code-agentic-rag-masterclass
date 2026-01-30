import os

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from app.config import settings

os.environ["LANGSMITH_TRACING"] = settings.langsmith_tracing
os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

_raw_client = OpenAI(api_key=settings.openai_api_key)
client = wrap_openai(_raw_client)


@traceable(name="chat_completion")
def stream_chat_response(message: str, previous_response_id: str | None = None):
    """Stream a chat response using the OpenAI Responses API."""
    response = client.responses.create(
        model=settings.openai_model,
        input=message,
        previous_response_id=previous_response_id,
        stream=True,
    )

    response_id = None
    for event in response:
        if event.type == "response.output_text.delta":
            yield {"event": "delta", "data": event.delta}
        elif event.type == "response.completed":
            response_id = event.response.id
            yield {"event": "done", "data": response_id}

    if response_id is None:
        yield {"event": "done", "data": ""}


@traceable(name="generate_thread_title")
def generate_thread_title(user_message: str, assistant_response: str) -> str:
    """Generate a short title for a thread based on the first exchange."""
    response = client.responses.create(
        model=settings.openai_model,
        input=(
            f"Generate a concise 3-5 word title for a conversation that starts with:\n"
            f"User: {user_message}\n"
            f"Assistant: {assistant_response}\n\n"
            f"Return ONLY the title, no quotes or punctuation."
        ),
    )
    return response.output_text.strip()
