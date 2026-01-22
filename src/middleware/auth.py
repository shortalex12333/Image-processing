"""
JWT authentication middleware using Supabase client.
Validates JWT tokens via Supabase and extracts user/yacht context.
"""

from fastapi import Header, HTTPException, status
from uuid import UUID

from src.config import settings
from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class AuthContext:
    """Authenticated user context."""

    def __init__(self, user_id: UUID, yacht_id: UUID, role: str, email: str):
        self.user_id = user_id
        self.yacht_id = yacht_id
        self.role = role
        self.email = email

    def is_hod(self) -> bool:
        """Check if user has HOD (Head of Department) privileges."""
        hod_roles = ["chief_engineer", "captain", "manager"]
        return self.role in hod_roles


async def get_auth_context(authorization: str = Header(None)) -> AuthContext:
    """
    Extract and validate JWT using Supabase client.

    This approach uses Supabase's built-in token validation, which handles
    signature verification internally. No JWT_SECRET environment variable needed.

    Args:
        authorization: Authorization header value (Bearer <token>)

    Returns:
        AuthContext with user/yacht information

    Raises:
        HTTPException: If authentication fails

    Usage:
        ```python
        @app.get("/protected")
        async def protected_route(auth: AuthContext = Depends(get_auth_context)):
            print(f"User: {auth.user_id}, Yacht: {auth.yacht_id}")
        ```
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>"
        )

    token = parts[1]

    try:
        # Use Supabase client to validate token
        # This handles signature verification internally - no JWT_SECRET needed!
        supabase = get_supabase_service()

        # Get user from token (Supabase validates signature)
        user_response = supabase.auth.get_user(token)
        user = user_response.user

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: User not found"
            )

        # Extract user info
        user_id = UUID(user.id)
        email = user.email or ""

        # Get yacht_id and role from user metadata
        user_metadata = user.user_metadata or {}
        yacht_id_str = user_metadata.get("yacht_id")
        role = user_metadata.get("role", "crew")

        # If yacht_id not in metadata, try to get from database
        if not yacht_id_str:
            try:
                # Try to find yacht association in database
                # Note: Table name may vary - adjust if needed
                result = supabase.table("pms_yacht_users") \
                    .select("yacht_id, role") \
                    .eq("user_id", str(user_id)) \
                    .limit(1) \
                    .execute()

                if result.data and len(result.data) > 0:
                    yacht_id_str = result.data[0].get("yacht_id")
                    role = result.data[0].get("role", "crew")
            except Exception as e:
                logger.debug("Could not query yacht association", extra={"error": str(e)})
                # If table doesn't exist or query fails, fall back to None
                pass

        # If still no yacht_id, this is an error
        if not yacht_id_str:
            logger.warning("User not associated with any yacht", extra={
                "user_id": str(user_id),
                "email": email
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not associated with any yacht. Please contact support."
            )

        yacht_id = UUID(yacht_id_str)

        logger.debug("User authenticated via Supabase", extra={
            "user_id": str(user_id),
            "yacht_id": str(yacht_id),
            "role": role,
            "email": email
        })

        return AuthContext(user_id, yacht_id, role, email)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.warning("Token validation failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


def require_hod(auth: AuthContext) -> None:
    """
    Require HOD (Head of Department) role.

    Args:
        auth: Auth context

    Raises:
        HTTPException: If user is not HOD
    """
    if not auth.is_hod():
        logger.warning("HOD permission required", extra={
            "user_id": str(auth.user_id),
            "role": auth.role
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires HOD permissions (chief_engineer, captain, or manager)"
        )


# Aliases for backward compatibility
UserContext = AuthContext
get_current_user = get_auth_context
