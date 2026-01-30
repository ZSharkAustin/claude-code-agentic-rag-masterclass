from fastapi import Depends, HTTPException, Request
from supabase import create_client

from app.config import settings


async def get_current_user(request: Request):
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header.split(" ", 1)[1]

    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_response.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")


def get_supabase_client(request: Request):
    """Create a per-request Supabase client using the user's JWT for RLS."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else ""

    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    supabase.postgrest.auth(token)
    return supabase
