"""
JWT authentication middleware.
Validates JWT tokens and extracts user/yacht context.
"""

import jwt
from fastapi import Header, HTTPException, status
from uuid import UUID

from src.config import settings
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
    Extract and validate JWT from Authorization header.

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
        # Decode JWT
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience
        )

        # Extract claims
        user_id = UUID(payload.get("sub"))  # Subject = user ID
        yacht_id = UUID(payload.get("yacht_id"))
        role = payload.get("role", "crew")
        email = payload.get("email", "")

        logger.debug("JWT validated", extra={
            "user_id": str(user_id),
            "yacht_id": str(yacht_id),
            "role": role
        })

        return AuthContext(user_id, yacht_id, role, email)

    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except (KeyError, ValueError) as e:
        logger.error("JWT missing required claims", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims"
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
