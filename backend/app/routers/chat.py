import json
from fastapi import APIRouter, Depends, HTTPException
from langsmith import traceable
from openai import AuthenticationError, APIError
from postgrest.exceptions import APIError as PostgrestAPIError
from sse_starlette.sse import EventSourceResponse
from supabase import create_client

from app.auth import get_current_user, get_supabase_client
from app.config import settings
from app.models.chat import ChatRequest
from app.services.openai_service import (
    stream_chat_response,
    chat_completion,
    generate_thread_title,
    generate_embeddings,
)

router = APIRouter(tags=["chat"])

SYSTEM_PROMPT = (
    "You are a helpful assistant. When you use the search_documents tool, "
    "cite relevant information from the results in your response. "
    "If the search results don't contain relevant information, say so."
)

SEARCH_DOCUMENTS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search the user's uploaded documents for relevant information. Use this when the user asks about their documents or needs information that might be in their uploaded files.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant document chunks",
                }
            },
            "required": ["query"],
        },
    },
}


def _execute_search(query: str, user_id: str) -> str:
    """Execute document search via match_chunks RPC using service role."""
    service_client = create_client(
        settings.supabase_url, settings.supabase_service_role_key
    )

    query_embedding = generate_embeddings([query])[0]

    result = service_client.rpc(
        "match_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": 5,
            "filter_user_id": user_id,
        },
    ).execute()

    if not result.data:
        return "No relevant documents found."

    chunks = []
    for chunk in result.data:
        chunks.append(
            f"[Document chunk {chunk['chunk_index']}]\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(chunks)


@router.post("/chat")
@traceable(name="chat_endpoint")
async def chat(
    body: ChatRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    # Verify thread exists
    try:
        supabase.table("threads").select("id").eq("id", body.thread_id).single().execute()
    except PostgrestAPIError:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Insert user message
    supabase.table("messages").insert(
        {"thread_id": body.thread_id, "role": "user", "content": body.message}
    ).execute()

    # Fetch all messages for thread
    msg_result = (
        supabase.table("messages")
        .select("role, content")
        .eq("thread_id", body.thread_id)
        .order("created_at", desc=False)
        .execute()
    )

    is_first_message = len(msg_result.data) == 1

    # Build messages array with system prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in msg_result.data:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Check if user has ready documents — only offer tool if so
    doc_result = (
        supabase.table("documents")
        .select("id")
        .eq("status", "ready")
        .limit(1)
        .execute()
    )
    tools = [SEARCH_DOCUMENTS_TOOL] if doc_result.data else None

    # Tool-call loop (max 3 rounds)
    for _ in range(3):
        try:
            assistant_msg = chat_completion(messages, tools)
        except (AuthenticationError, APIError):
            break

        if not assistant_msg.tool_calls:
            break

        # Append assistant message with tool calls
        messages.append(assistant_msg.model_dump())

        # Execute each tool call
        for tool_call in assistant_msg.tool_calls:
            if tool_call.function.name == "search_documents":
                args = json.loads(tool_call.function.arguments)
                result = _execute_search(args["query"], user.id)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

        # Don't offer tools on subsequent rounds to force a final answer
        tools = None

    async def event_generator():
        full_response = ""

        try:
            for event in stream_chat_response(messages):
                if event["event"] == "delta":
                    full_response += event["data"]
                    yield {
                        "event": "delta",
                        "data": json.dumps({"text": event["data"]}),
                    }
                elif event["event"] == "done":
                    yield {"event": "done", "data": json.dumps({})}
        except AuthenticationError:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Invalid API key. Please check your configuration."}
                ),
            }
            return
        except APIError as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": f"API error: {e.message}"}),
            }
            return
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": f"An error occurred: {str(e)}"}),
            }
            return

        # Insert assistant message
        if full_response:
            supabase.table("messages").insert(
                {
                    "thread_id": body.thread_id,
                    "role": "assistant",
                    "content": full_response,
                }
            ).execute()

        # Auto-generate title for first message
        if is_first_message and full_response:
            try:
                title = generate_thread_title(body.message, full_response)
                supabase.table("threads").update({"title": title}).eq(
                    "id", body.thread_id
                ).execute()
                yield {
                    "event": "title_update",
                    "data": json.dumps({"title": title}),
                }
            except Exception:
                pass

    return EventSourceResponse(event_generator())
