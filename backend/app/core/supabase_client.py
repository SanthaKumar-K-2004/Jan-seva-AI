"""
Jan-Seva AI — Supabase Client (Singleton)
Provides a single, reusable connection to Supabase for all services.
"""

from supabase import create_client, Client
from functools import lru_cache
from app.config import get_settings


@lru_cache()
def get_supabase_client() -> Client:
    """
    Returns a cached Supabase client instance.
    Uses the service role key for full DB access (backend only).
    """
    settings = get_settings()
    client = create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key or settings.supabase_anon_key,
    )
    return client


async def execute_rpc(function_name: str, params: dict = None) -> dict:
    """Execute a Supabase RPC (stored procedure)."""
    client = get_supabase_client()
    response = client.rpc(function_name, params or {}).execute()
    return response.data


async def vector_search(query_embedding: list[float], match_count: int = 5) -> list[dict]:
    """
    Perform a vector similarity search on scheme_embeddings table.
    Uses pgvector's cosine similarity via Supabase RPC.
    """
    client = get_supabase_client()
    response = client.rpc(
        "match_scheme_embeddings",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
        },
    ).execute()
    return response.data
