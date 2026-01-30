import json
from fastapi import APIRouter, Depends, HTTPException
from langsmith import traceable
from openai import AuthenticationError, APIError
from postgrest.exceptions import APIError as PostgrestAPIError
from sse_starlette.sse import EventSourceResponse

from app.auth import get_current_user, get_supabase_client
from app.models.chat import ChatRequest
from app.services.openai_service import stream_chat_response, generate_thread_title

router = APIRouter(tags=["chat"])


@router.post("/chat")
@traceable(name="chat_endpoint")
async def chat(
    body: ChatRequest,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    # Look up thread to get last_response_id
    try:
        thread_result = (
            supabase.table("threads")
            .select("*")
            .eq("id", body.thread_id)
            .single()
            .execute()
        )
        thread = thread_result.data
    except PostgrestAPIError:
        raise HTTPException(status_code=404, detail="Thread not found")

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    previous_response_id = thread.get("last_response_id")
    is_first_message = previous_response_id is None

    async def event_generator():
        full_response = ""
        new_response_id = None

        try:
            for event in stream_chat_response(body.message, previous_response_id):
                if event["event"] == "delta":
                    full_response += event["data"]
                    yield {"event": "delta", "data": json.dumps({"text": event["data"]})}
                elif event["event"] == "done":
                    new_response_id = event["data"]
                    yield {"event": "done", "data": json.dumps({"response_id": new_response_id})}
        except AuthenticationError:
            yield {"event": "error", "data": json.dumps({"error": "Invalid OpenAI API key. Please check your configuration."})}
            return
        except APIError as e:
            yield {"event": "error", "data": json.dumps({"error": f"OpenAI error: {e.message}"})}
            return
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": f"An error occurred: {str(e)}"})}
            return

        # Update thread with new response_id
        if new_response_id:
            supabase.table("threads").update(
                {"last_response_id": new_response_id}
            ).eq("id", body.thread_id).execute()

        # Auto-generate title for first message
        if is_first_message and full_response:
            try:
                title = generate_thread_title(body.message, full_response)
                supabase.table("threads").update(
                    {"title": title}
                ).eq("id", body.thread_id).execute()
                yield {
                    "event": "title_update",
                    "data": json.dumps({"title": title}),
                }
            except Exception:
                pass

    return EventSourceResponse(event_generator())
