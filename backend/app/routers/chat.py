import json
import re
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
    is_ollama,
)
from app.services.reranker_service import is_reranker_available, rerank_chunks

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
        "description": (
            "Search the user's uploaded documents for relevant information. "
            "Use this when the user asks about their documents or needs information "
            "that might be in their uploaded files. You can optionally filter by "
            "document_type or topic to narrow results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant document chunks",
                },
                "document_type": {
                    "type": "string",
                    "description": (
                        'Optional filter by document type, e.g. "research paper", '
                        '"contract", "manual", "report", "readme", "tutorial". '
                        "Only include if the user explicitly mentions or implies a specific document type."
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": (
                        "Optional filter by topic/subject area. Only include if "
                        "the user asks about a specific topic and you want to narrow results."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}


def _fetch_chunks(
    query: str,
    user_id: str,
    document_type: str | None = None,
    topic: str | None = None,
) -> list[dict]:
    """Fetch matching chunks via match_chunks_hybrid RPC using service role."""
    service_client = create_client(
        settings.supabase_url, settings.supabase_service_role_key
    )

    query_embedding = generate_embeddings([query])[0]

    # Build metadata filter from provided params
    metadata_filter = {}
    if document_type:
        metadata_filter["document_type"] = document_type
    if topic:
        metadata_filter["topic"] = topic

    reranker_enabled = is_reranker_available()
    match_count = 20 if reranker_enabled else 5

    rpc_params = {
        "query_embedding": query_embedding,
        "match_count": match_count,
        "filter_user_id": user_id,
        "query_text": query,
    }
    if metadata_filter:
        rpc_params["metadata_filter"] = json.dumps(metadata_filter)

    result = service_client.rpc("match_chunks_hybrid", rpc_params).execute()

    if not result.data:
        return []

    chunks_data = result.data
    if reranker_enabled:
        chunks_data = rerank_chunks(query, chunks_data, top_n=5)

    return chunks_data


def _format_search_context(chunks_data: list[dict]) -> str:
    """Format chunks into a text string for injection into LLM prompts."""
    if not chunks_data:
        return "No relevant documents found."

    chunks = []
    for chunk in chunks_data:
        metadata = chunk.get("metadata", {}) or {}
        meta_parts = []
        if metadata.get("document_type"):
            meta_parts.append(f"Type: {metadata['document_type']}")
        if metadata.get("topic"):
            meta_parts.append(f"Topic: {metadata['topic']}")
        if metadata.get("key_terms"):
            meta_parts.append(f"Key terms: {', '.join(metadata['key_terms'])}")

        header = f"[Document chunk {chunk['chunk_index']}"
        if meta_parts:
            header += f" | {' | '.join(meta_parts)}"
        header += "]"

        chunks.append(f"{header}\n{chunk['content']}")
    return "\n\n---\n\n".join(chunks)


_MD_PATTERNS = re.compile(
    r"#{1,6}\s+"       # headings
    r"|[*_]{1,3}"      # bold/italic markers
    r"|\[([^\]]*)\]\([^)]*\)"  # links → keep text
    r"|`{1,3}"         # code markers
    r"|^>\s+"          # blockquotes
    r"|^-\s+"          # unordered list markers
    r"|^\d+\.\s+"      # ordered list markers
    r"|\|"             # table pipes
    , re.MULTILINE,
)


def _strip_markdown(text: str) -> str:
    """Remove common markdown formatting characters from text."""
    result = _MD_PATTERNS.sub(lambda m: m.group(1) if m.group(1) else "", text)
    return " ".join(result.split())


def _build_sources(
    chunks_data: list[dict],
    max_sources: int = 3,
    similarity_threshold: float = 0.3,
) -> list[dict]:
    """Build structured sources list, keeping only relevant chunks."""
    sources = []
    for chunk in chunks_data:
        # Use reranker relevance_score if available, otherwise fall back to similarity
        score = chunk.get("relevance_score") or chunk.get("similarity") or 0
        if score < similarity_threshold:
            continue
        metadata = chunk.get("metadata", {}) or {}
        sources.append({
            "content": _strip_markdown(chunk.get("content", ""))[:200],
            "chunk_index": chunk.get("chunk_index", 0),
            "document_id": chunk.get("document_id", ""),
            "metadata": {
                k: v
                for k, v in metadata.items()
                if k in ("topic", "document_type", "key_terms")
            },
        })
        if len(sources) >= max_sources:
            break
    return sources


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
    has_documents = bool(doc_result.data)

    sources_list: list[dict] = []

    if is_ollama() and has_documents:
        # Ollama/Gemma3 doesn't support tool calling — always search and inject context
        chunks_data = _fetch_chunks(query=body.message, user_id=user.id)
        search_result = _format_search_context(chunks_data)
        sources_list = _build_sources(chunks_data)
        messages[0] = {
            "role": "system",
            "content": (
                SYSTEM_PROMPT
                + "\n\nHere are relevant excerpts from the user's documents:\n\n"
                + search_result
            ),
        }
    elif not is_ollama():
        tools = [SEARCH_DOCUMENTS_TOOL] if has_documents else None

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
                    chunks_data = _fetch_chunks(
                        query=args["query"],
                        user_id=user.id,
                        document_type=args.get("document_type"),
                        topic=args.get("topic"),
                    )
                    result = _format_search_context(chunks_data)
                    sources_list = _build_sources(chunks_data)
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

        if sources_list:
            yield {
                "event": "sources",
                "data": json.dumps({"sources": sources_list}),
            }

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
