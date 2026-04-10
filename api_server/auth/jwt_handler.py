"""
JWT Authentication Handler

Provides JWT token generation and validation for API authentication.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

# Configuration from environment
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


class TokenData:
    """Data encoded in JWT tokens"""

    def __init__(
        self,
        user_id: str,
        role: str,
        permission_level: str,
        exp_delta: Optional[timedelta] = None,
    ):
        self.user_id = user_id
        self.role = role
        self.permission_level = permission_level

        now = datetime.now(timezone.utc)
        self.issued_at = now
        self.expires_at = now + (exp_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "role": self.role,
            "permission_level": self.permission_level,
            "iat": self.issued_at,
            "exp": self.expires_at,
        }


class JWTAuth:
    """JWT token handler for creating and validating tokens"""

    @staticmethod
    def create_access_token(token_data: TokenData) -> str:
        """
        Create a new JWT access token.

        Args:
            token_data: Token data to encode

        Returns:
            Encoded JWT token string
        """
        payload = token_data.to_dict()
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(token_data: TokenData) -> str:
        """
        Create a new JWT refresh token with longer expiration.

        Args:
            token_data: Token data to encode

        Returns:
            Encoded JWT refresh token string
        """
        refresh_data = TokenData(
            user_id=token_data.user_id,
            role=token_data.role,
            permission_level=token_data.permission_level,
            exp_delta=timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        payload = refresh_data.to_dict()
        payload["token_type"] = "refresh"
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string
            token_type: Expected token type ("access" or "refresh")

        Returns:
            TokenData if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

            # Verify token type if specified
            if token_type == "refresh":
                if payload.get("token_type") != "refresh":
                    return None

            return TokenData(
                user_id=payload["user_id"],
                role=payload["role"],
                permission_level=payload["permission_level"],
            )
        except ExpiredSignatureError:
            return None
        except InvalidTokenError:
            return None

    @staticmethod
    def decode_token_unsafe(token: str) -> Optional[dict]:
        """
        Decode token without verification (for debugging/logging).

        Args:
            token: JWT token string

        Returns:
            Decoded payload or None if malformed
        """
        try:
            return jwt.decode(
                token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"verify_exp": False}
            )
        except Exception:
            return None


# Global instance
jwt_auth = JWTAuth()


def create_tokens(user_id: str, role: str, permission_level: str) -> dict:
    """
    Convenience function to create both access and refresh tokens.

    Args:
        user_id: User identifier
        role: User role
        permission_level: Permission level (L0-L3)

    Returns:
        Dict with access_token, refresh_token, and token_type
    """
    token_data = TokenData(
        user_id=user_id,
        role=role,
        permission_level=permission_level,
    )
    return {
        "access_token": JWTAuth.create_access_token(token_data),
        "refresh_token": JWTAuth.create_refresh_token(token_data),
        "token_type": "bearer",
    }


__all__ = [
    "JWTAuth",
    "TokenData",
    "jwt_auth",
    "create_tokens",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
]
