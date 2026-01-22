"""
Database connection and Supabase client management.
"""

from typing import Optional
from supabase import create_client, Client
from src.config import settings


# Global Supabase client instances
_supabase_service: Optional[Client] = None
_supabase_anon: Optional[Client] = None


def get_supabase_service() -> Client:
    """
    Get Supabase client with service role key (admin privileges).

    Use for:
    - Background processing jobs
    - Bypassing RLS policies
    - System-level operations

    Returns:
        Supabase client with service role privileges
    """
    global _supabase_service

    if _supabase_service is None:
        _supabase_service = create_client(
            supabase_url=settings.next_public_supabase_url,
            supabase_key=settings.supabase_service_role_key
        )

    return _supabase_service


def get_supabase_anon() -> Client:
    """
    Get Supabase client with anon key (respects RLS policies).

    Use for:
    - User-facing operations
    - Multi-tenant isolation
    - JWT-authenticated requests

    Returns:
        Supabase client with anon key
    """
    global _supabase_anon

    if _supabase_anon is None:
        _supabase_anon = create_client(
            supabase_url=settings.next_public_supabase_url,
            supabase_key=settings.supabase_anon_key
        )

    return _supabase_anon


def get_supabase_for_user(jwt_token: str) -> Client:
    """
    Get Supabase client authenticated as specific user (respects RLS).

    Use for:
    - API endpoints with JWT authentication
    - Operations that should respect user's yacht_id

    Args:
        jwt_token: JWT token from Authorization header

    Returns:
        Supabase client authenticated as user
    """
    client = create_client(
        supabase_url=settings.next_public_supabase_url,
        supabase_key=settings.supabase_anon_key
    )

    # Set JWT token for this request
    client.postgrest.auth(jwt_token)

    return client


def get_bucket_name(upload_type: str) -> str:
    """
    Get storage bucket name for upload type.

    Args:
        upload_type: One of: receiving, shipping_label, discrepancy, part_photo, finance

    Returns:
        Bucket name

    Raises:
        ValueError: If upload_type unknown
    """
    bucket_map = {
        "receiving": settings.storage_bucket_receiving,
        "shipping_label": settings.storage_bucket_receiving,  # Same as receiving
        "discrepancy": settings.storage_bucket_discrepancy,
        "part_photo": settings.storage_bucket_parts,
        "finance": settings.storage_bucket_finance
    }

    if upload_type not in bucket_map:
        raise ValueError(f"Unknown upload_type: {upload_type}")

    return bucket_map[upload_type]
