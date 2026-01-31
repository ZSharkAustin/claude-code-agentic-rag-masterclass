import hashlib
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from postgrest.exceptions import APIError as PostgrestAPIError

from app.auth import get_current_user, get_supabase_client
from app.config import settings
from app.models.documents import DocumentResponse
from app.services.document_service import process_document
from supabase import create_client

router = APIRouter(tags=["documents"])

ALLOWED_MIME_TYPES = {"application/pdf", "text/plain", "text/markdown"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    # Validate mime type
    mime_type = file.content_type or ""
    # Treat .md files that come as application/octet-stream or text/x-markdown
    if file.filename and file.filename.endswith(".md"):
        mime_type = "text/markdown"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {mime_type}. Allowed: PDF, TXT, MD",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

    # Compute content hash for deduplication
    content_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicate: same user, same content, already processed
    existing = (
        supabase.table("documents")
        .select("id")
        .eq("content_hash", content_hash)
        .eq("status", "ready")
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=409,
            detail=f"Document with identical content already exists (id: {existing.data[0]['id']})",
        )

    # Upload to Supabase Storage using service role (user RLS folder path)
    file_id = str(uuid.uuid4())
    storage_path = f"{user.id}/{file_id}/{file.filename}"

    service_client = create_client(
        settings.supabase_url, settings.supabase_service_role_key
    )
    service_client.storage.from_("documents").upload(
        storage_path, content, {"content-type": mime_type}
    )

    # Create document record (via user's RLS client)
    doc_data = {
        "user_id": user.id,
        "filename": file.filename,
        "file_path": storage_path,
        "file_size": len(content),
        "mime_type": mime_type,
        "status": "uploading",
        "content_hash": content_hash,
    }
    result = supabase.table("documents").insert(doc_data).execute()
    doc = result.data[0]

    # Kick off background processing
    background_tasks.add_task(process_document, doc["id"], storage_path, mime_type)

    return doc


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    result = (
        supabase.table("documents")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    try:
        result = (
            supabase.table("documents")
            .select("*")
            .eq("id", document_id)
            .single()
            .execute()
        )
    except PostgrestAPIError:
        raise HTTPException(status_code=404, detail="Document not found")
    return result.data


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    # Get document to find storage path
    try:
        result = (
            supabase.table("documents")
            .select("file_path")
            .eq("id", document_id)
            .single()
            .execute()
        )
    except PostgrestAPIError:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = result.data["file_path"]

    # Delete from storage using service role
    service_client = create_client(
        settings.supabase_url, settings.supabase_service_role_key
    )
    service_client.storage.from_("documents").remove([file_path])

    # Delete document record (chunks cascade automatically)
    supabase.table("documents").delete().eq("id", document_id).execute()
