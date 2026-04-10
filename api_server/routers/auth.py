"""
Authentication Router

Provides login, logout, token refresh, and user info endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Request

from api_server.auth.jwt_handler import jwt_auth, create_tokens, JWT_ACCESS_TOKEN_EXPIRE_MINUTES
from api_server.auth.session_store import session_store
from api_server.auth.rbac_middleware import require_auth, AuthenticatedUser
from api_server.models import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserInfo,
    LogoutResponse,
)


router = APIRouter()


# In-memory user store for demo purposes
# In production, this would be a database lookup
DEMO_USERS = {
    "admin": {
        "password": "admin123",
        "user_id": "user-001",
        "role": "admin",
        "permission_level": "L3",
    },
    "editor": {
        "password": "editor123",
        "user_id": "user-002",
        "role": "writer",
        "permission_level": "L2",
    },
    "user": {
        "password": "user123",
        "user_id": "user-003",
        "role": "writer",
        "permission_level": "L1",
    },
    "guest": {
        "password": "guest123",
        "user_id": "user-004",
        "role": "reader",
        "permission_level": "L0",
    },
}


def verify_credentials(username: str, password: str) -> dict | None:
    """
    Verify username and password.

    Args:
        username: Username
        password: Password

    Returns:
        User data dict if valid, None otherwise
    """
    user = DEMO_USERS.get(username)
    if user and user["password"] == password:
        return user
    return None


@router.post("/login", response_model=TokenResponse, tags=["auth"])
async def login(request: Request, login_data: LoginRequest):
    """
    Authenticate user and return JWT tokens.

    Provides access token and refresh token upon successful authentication.
    """
    # Verify credentials
    user_data = verify_credentials(login_data.username, login_data.password)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get client IP
    client_ip = request.client.host if request.client else None

    # Create session
    session_id = session_store.create_session(
        user_id=user_data["user_id"],
        username=login_data.username,
        role=user_data["role"],
        permission_level=user_data["permission_level"],
        client_ip=client_ip,
    )

    # Create tokens
    tokens = create_tokens(
        user_id=user_data["user_id"],
        role=user_data["role"],
        permission_level=user_data["permission_level"],
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=LogoutResponse, tags=["auth"])
async def logout(user: AuthenticatedUser = Depends(require_auth)):
    """
    Logout current session.

    Invalidates the current session and blacklists the token.
    """
    # Delete current session
    if user.session_id:
        session_store.delete_session(user.session_id)

    return LogoutResponse(
        message="Successfully logged out",
        sessions_terminated=1,
    )


@router.post("/logout-all", response_model=LogoutResponse, tags=["auth"])
async def logout_all(user: AuthenticatedUser = Depends(require_auth)):
    """
    Logout all sessions for the current user.

    Terminates all active sessions across all devices.
    """
    sessions_terminated = session_store.delete_user_sessions(user.user_id)

    return LogoutResponse(
        message=f"Successfully logged out {sessions_terminated} session(s)",
        sessions_terminated=sessions_terminated,
    )


@router.post("/refresh", response_model=TokenResponse, tags=["auth"])
async def refresh_token(refresh_data: RefreshRequest):
    """
    Refresh access token using refresh token.

    Provides a new access token without requiring re-authentication.
    """
    # Verify refresh token
    token_data = jwt_auth.verify_token(refresh_data.refresh_token, token_type="refresh")
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create new tokens
    tokens = create_tokens(
        user_id=token_data.user_id,
        role=token_data.role,
        permission_level=token_data.permission_level,
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserInfo, tags=["auth"])
async def get_current_user_info(user: AuthenticatedUser = Depends(require_auth)):
    """
    Get current authenticated user information.

    Returns user details including role and permission level.
    """
    session_count = session_store.get_user_session_count(user.user_id)

    # Import PermissionLevel enum
    from api_server.models import PermissionLevel

    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        permission_level=PermissionLevel(user.permission_level),
        session_count=session_count,
    )


__all__ = ["router"]
