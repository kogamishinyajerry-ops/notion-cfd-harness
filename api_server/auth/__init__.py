"""
Authentication Module

JWT-based authentication with session management and RBAC integration.
"""

from api_server.auth.jwt_handler import (
    JWTAuth,
    TokenData,
    jwt_auth,
    create_tokens,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
)
from api_server.auth.session_store import (
    SessionStore,
    UserSession,
    session_store,
)

__all__ = [
    "JWTAuth",
    "TokenData",
    "jwt_auth",
    "create_tokens",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "SessionStore",
    "UserSession",
    "session_store",
]
