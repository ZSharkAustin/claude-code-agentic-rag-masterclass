from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, get_supabase_client
from app.models.threads import ThreadCreate, ThreadUpdate, ThreadResponse

router = APIRouter(tags=["threads"])


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    result = (
        supabase.table("threads")
        .select("*")
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


@router.post("/threads", response_model=ThreadResponse, status_code=201)
async def create_thread(
    body: ThreadCreate,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    result = (
        supabase.table("threads")
        .insert({"title": body.title, "user_id": user.id})
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create thread")
    return result.data[0]


@router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    body: ThreadUpdate,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = (
        supabase.table("threads")
        .update(update_data)
        .eq("id", thread_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    return result.data[0]


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    supabase.table("threads").delete().eq("id", thread_id).execute()
