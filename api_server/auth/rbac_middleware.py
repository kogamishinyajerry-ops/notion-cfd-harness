"""
RBAC Middleware and Dependencies

FastAPI dependencies for JWT authentication and RBAC authorization.
Integrates with the existing RBAC engine from Phase 5.
"""

from __future__ import annotations

from typing import Optional, List, Callable

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api_server.auth.jwt_handler import JWTAuth, jwt_auth
from api_server.auth.session_store import session_store, UserSession
from knowledge_compiler.security.rbac import RBACEngine, get_rbac, Permission, PermissionLevel


# HTTP Bearer scheme for JWT extraction
bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Current authenticated user context"""

    def __init__(
        self,
        user_id: str,
        username: str,
        role: str,
        permission_level: str,
        session_id: Optional[str] = None,
    ):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.permission_level = permission_level
        self.session_id = session_id

    def has_permission(self, resource: str, action: str, rbac: RBACEngine) -> bool:
        """Check if user has a specific permission via RBAC."""
        # Map permission_level (L0-L3) to RBAC role
        role_mapping = {
            "L0": "reader",
            "L1": "writer",
            "L2": "writer",  # L2 uses writer role permissions
            "L3": "admin",
        }
        rbac_role = role_mapping.get(self.permission_level, "reader")
        return rbac.check_permission(self.user_id, resource, action)

    def to_session(self) -> UserSession:
        """Convert to UserSession for session store."""
        return UserSession(
            user_id=self.user_id,
            username=self.username,
            role=self.role,
            permission_level=self.permission_level,
        )


def extract_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[str]:
    """
    Extract JWT token from Authorization header.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        Token string or None if not present
    """
    if credentials is None:
        return None
    return credentials.credentials


async def get_current_user(
    token: Optional[str] = Depends(extract_token_from_header),
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency to get the current authenticated user.

    Does not raise an error if no token is provided - returns None instead.
    Use require_auth dependency if authentication is mandatory.

    Args:
        token: JWT token from Authorization header

    Returns:
        AuthenticatedUser if valid token, None otherwise
    """
    if token is None:
        return None

    # Verify token
    token_data = JWTAuth.verify_token(token)
    if token_data is None:
        return None

    # Create authenticated user context
    # Note: In a real system, we'd look up the user in a database
    # For this implementation, we create a context from the token data
    return AuthenticatedUser(
        user_id=token_data.user_id,
        username=token_data.user_id,  # Use user_id as username if not in token
        role=token_data.role,
        permission_level=token_data.permission_level,
    )


async def require_auth(
    user: Optional[AuthenticatedUser] = Depends(get_current_user),
) -> AuthenticatedUser:
    """
    FastAPI dependency requiring authentication.

    Raises 401 if no valid token is provided.

    Args:
        user: Current user from get_current_user dependency

    Returns:
        AuthenticatedUser

    Raises:
        HTTPException: 401 if not authenticated
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(
    resource: str,
    action: str,
    rbac: Optional[RBACEngine] = None,
) -> Callable:
    """
    Factory for creating permission-checking dependencies.

    Args:
        resource: Resource to check permission for
        action: Action to check permission for
        rbac: RBAC engine instance (uses global if not provided)

    Returns:
        FastAPI dependency that checks permission
    """
    if rbac is None:
        rbac = get_rbac()

    async def permission_checker(
        user: AuthenticatedUser = Depends(require_auth),
    ) -> AuthenticatedUser:
        """Dependency that verifies user has required permission."""
        if not rbac.check_permission(user.user_id, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource}",
            )
        return user

    return permission_checker


def require_permission_level(
    min_level: str,
) -> Callable:
    """
    Factory for creating PermissionLevel-checking dependencies.

    PermissionLevel hierarchy: L0 < L1 < L2 < L3

    Args:
        min_level: Minimum required permission level (L0-L3)

    Returns:
        FastAPI dependency that checks permission level
    """
    level_order = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}

    async def level_checker(
        user: AuthenticatedUser = Depends(require_auth),
    ) -> AuthenticatedUser:
        """Dependency that verifies user meets minimum permission level."""
        user_level = level_order.get(user.permission_level, 0)
        required_level = level_order.get(min_level, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permission level: {user.permission_level} < {min_level}",
            )
        return user

    return level_checker


# Pre-configured permission dependencies for common resources/actions
def require_read(resource: str) -> Callable:
    """Require read permission on a resource."""
    return require_permission(resource, "read")


def require_write(resource: str) -> Callable:
    """Require write permission on a resource."""
    return require_permission(resource, "write")


def require_execute(resource: str) -> Callable:
    """Require execute permission on a resource."""
    return require_permission(resource, "execute")


def require_admin() -> Callable:
    """Require admin role (L3)."""
    return require_permission_level("L3")


__all__ = [
    "AuthenticatedUser",
    "extract_token_from_header",
    "get_current_user",
    "require_auth",
    "require_permission",
    "require_permission_level",
    "require_read",
    "require_write",
    "require_execute",
    "require_admin",
    "bearer_scheme",
]
