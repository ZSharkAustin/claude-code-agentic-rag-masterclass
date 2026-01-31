from fastapi import APIRouter, Depends

from app.auth import get_current_user, get_supabase_client
from app.models.messages import MessageResponse

router = APIRouter(tags=["messages"])


@router.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    thread_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    result = (
        supabase.table("messages")
        .select("*")
        .eq("thread_id", thread_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data
