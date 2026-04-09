#!/usr/bin/env python3
"""
P5-07: Authentication - API Key and JWT token validation

Provides:
- API Key authentication
- JWT token validation
- Secret management with priority (env > file > error)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import threading

# Default secret file location
DEFAULT_SECRET_FILE = Path.home() / ".notion_key"


# ============================================================================
# Auth Methods
# ============================================================================

class AuthMethod(Enum):
    """Authentication method types"""
    API_KEY = "api_key"
    JWT = "jwt"
    NONE = "none"


# ============================================================================
# Authentication Result
# ============================================================================

@dataclass
class AuthResult:
    """Result of authentication attempt"""
    success: bool
    method: AuthMethod
    user_id: Optional[str] = None
    error: Optional[str] = None
    expires_at: Optional[float] = None

    def is_valid(self) -> bool:
        """Check if authentication is valid"""
        if not self.success:
            return False
        if self.expires_at and self.expires_at < time.time():
            return False
        return True


# ============================================================================
# API Key Authentication
# ============================================================================

class APIKeyAuth:
    """
    API Key authentication

    Features:
    - Static key validation
    - Key hashing for comparison
    - Environment variable and file support
    """

    def __init__(self, valid_keys: List[str] | None = None):
        """
        Initialize API Key auth

        Args:
            valid_keys: List of valid API keys (if None, loads from env/file)
        """
        self._valid_keys: set[str] = set()
        self._lock = threading.Lock()

        if valid_keys is not None:
            self._valid_keys.update(valid_keys)
        else:
            # Load from environment or file
            key = self._load_secret()
            if key:
                self._valid_keys.add(key)

    def _load_secret(self) -> Optional[str]:
        """
        Load secret from environment or file

        Priority:
        1. Environment variable NOTION_API_KEY
        2. File ~/.notion_key
        3. Return None

        Returns:
            Secret string or None
        """
        # 1. Environment variable
        env_key = os.environ.get("NOTION_API_KEY")
        if env_key:
            return env_key

        # 2. File
        if DEFAULT_SECRET_FILE.exists():
            try:
                content = DEFAULT_SECRET_FILE.read_text().strip()
                if content:
                    return content
            except Exception:
                pass

        # 3. Not found
        return None

    def add_key(self, key: str) -> None:
        """Add a valid API key"""
        with self._lock:
            self._valid_keys.add(key)

    def remove_key(self, key: str) -> None:
        """Remove an API key"""
        with self._lock:
            self._valid_keys.discard(key)

    def authenticate(self, key: str) -> AuthResult:
        """
        Authenticate with API key

        Args:
            key: API key to validate

        Returns:
            AuthResult with success status
        """
        with self._lock:
            if key in self._valid_keys:
                # Extract user_id from key if possible (format: user_id:hash)
                parts = key.split(":", 1)
                user_id = parts[0] if len(parts) > 1 else "api_user"

                return AuthResult(
                    success=True,
                    method=AuthMethod.API_KEY,
                    user_id=user_id,
                )

            return AuthResult(
                success=False,
                method=AuthMethod.API_KEY,
                error="Invalid API key",
            )

    def has_keys(self) -> bool:
        """Check if any keys are configured"""
        with self._lock:
            return len(self._valid_keys) > 0


# ============================================================================
# JWT Authentication (Simplified)
# ============================================================================

class JWTAuth:
    """
    JWT authentication (simplified implementation)

    Features:
    - Token generation
    - Token validation
    - HS256 signature
    - Expiration handling

    Note: This is a simplified implementation. For production,
    use PyJWT or authlib.
    """

    def __init__(self, secret: str | None = None):
        """
        Initialize JWT auth

        Args:
            secret: Secret key for signing (if None, loads from env/file)
        """
        self.secret = secret or self._load_secret()
        self._lock = threading.Lock()

    def _load_secret(self) -> str:
        """Load JWT secret from environment or generate one"""
        # Try environment
        secret = os.environ.get("JWT_SECRET")
        if secret:
            return secret

        # Try file
        jwt_file = Path.home() / ".jwt_secret"
        if jwt_file.exists():
            return jwt_file.read_text().strip()

        # Generate and save
        import uuid
        secret = str(uuid.uuid4())
        try:
            jwt_file.write_text(secret)
        except Exception:
            pass
        return secret

    def create_token(
        self,
        user_id: str,
        expires_in: int = 3600,
        payload: Dict[str, Any] | None = None,
    ) -> str:
        """
        Create a JWT token

        Args:
            user_id: User identifier
            expires_in: Expiration time in seconds (default: 1 hour)
            payload: Additional payload data

        Returns:
            JWT token string
        """
        now = time.time()

        header = {
            "alg": "HS256",
            "typ": "JWT",
        }

        token_payload = {
            "user_id": user_id,
            "iat": now,
            "exp": now + expires_in,
        }
        if payload:
            token_payload.update(payload)

        # Encode header and payload
        header_b64 = self._base64url_encode(json.dumps(header))
        payload_b64 = self._base64url_encode(json.dumps(token_payload))

        # Create signature
        message = f"{header_b64}.{payload_b64}"
        signature = self._sign(message, self.secret)
        sig_b64 = self._base64url_encode(signature)

        return f"{message}.{sig_b64}"

    def validate_token(self, token: str) -> AuthResult:
        """
        Validate a JWT token

        Args:
            token: JWT token string

        Returns:
            AuthResult with validation status
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return AuthResult(
                    success=False,
                    method=AuthMethod.JWT,
                    error="Invalid token format",
                )

            header_b64, payload_b64, sig_b64 = parts

            # Verify signature
            message = f"{header_b64}.{payload_b64}"
            expected_sig = self._sign(message, self.secret)
            expected_sig_b64 = self._base64url_encode(expected_sig)

            if not hmac.compare_digest(sig_b64, expected_sig_b64):
                return AuthResult(
                    success=False,
                    method=AuthMethod.JWT,
                    error="Invalid signature",
                )

            # Decode payload
            payload = json.loads(self._base64url_decode(payload_b64))

            # Check expiration
            exp = payload.get("exp")
            if exp and exp < time.time():
                return AuthResult(
                    success=False,
                    method=AuthMethod.JWT,
                    error="Token expired",
                    expires_at=exp,
                )

            return AuthResult(
                success=True,
                method=AuthMethod.JWT,
                user_id=payload.get("user_id"),
                expires_at=exp,
            )

        except Exception as e:
            return AuthResult(
                success=False,
                method=AuthMethod.JWT,
                error=f"Validation error: {e}",
            )

    def _base64url_encode(self, data: bytes | str) -> str:
        """Base64 URL-safe encoding"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    def _base64url_decode(self, data: str) -> str:
        """Base64 URL-safe decoding"""
        # Add padding
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data).decode("utf-8")

    def _sign(self, message: str, secret: str) -> bytes:
        """Create HMAC signature"""
        return hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()


# ============================================================================
# Multi-Method Authenticator
# ============================================================================

class Authenticator:
    """
    Multi-method authenticator

    Supports multiple authentication methods with fallback.
    """

    def __init__(
        self,
        api_key_auth: APIKeyAuth | None = None,
        jwt_auth: JWTAuth | None = None,
    ):
        """
        Initialize authenticator

        Args:
            api_key_auth: API Key auth instance (created if None)
            jwt_auth: JWT auth instance (created if None)
        """
        self.api_key = api_key_auth or APIKeyAuth()
        self.jwt = jwt_auth or JWTAuth()

    def authenticate(
        self,
        credential: str,
        method: AuthMethod | None = None,
    ) -> AuthResult:
        """
        Authenticate with credential

        Args:
            credential: API key or JWT token
            method: Specific method to use (auto-detect if None)

        Returns:
            AuthResult
        """
        # Try to detect method if not specified
        if method is None:
            if credential.count(".") == 2:
                method = AuthMethod.JWT
            else:
                method = AuthMethod.API_KEY

        # Route to appropriate auth
        if method == AuthMethod.JWT:
            return self.jwt.validate_token(credential)
        elif method == AuthMethod.API_KEY:
            return self.api_key.authenticate(credential)
        else:
            return AuthResult(
                success=False,
                method=AuthMethod.NONE,
                error="Unknown auth method",
            )

    def create_jwt_token(
        self,
        user_id: str,
        expires_in: int = 3600,
        payload: Dict[str, Any] | None = None,
    ) -> str:
        """Create a JWT token"""
        return self.jwt.create_token(user_id, expires_in, payload)

    def add_api_key(self, key: str) -> None:
        """Add an API key"""
        self.api_key.add_key(key)

    def has_api_keys(self) -> bool:
        """Check if any API keys are configured"""
        return self.api_key.has_keys()


# ============================================================================
# Secret Management
# ============================================================================

def get_notion_api_key() -> Optional[str]:
    """
    Get Notion API key from environment or file

    Priority:
    1. Environment variable NOTION_API_KEY
    2. File ~/.notion_key
    3. None

    Returns:
        API key string or None
    """
    # 1. Environment variable
    key = os.environ.get("NOTION_API_KEY")
    if key:
        return key

    # 2. File
    if DEFAULT_SECRET_FILE.exists():
        try:
            content = DEFAULT_SECRET_FILE.read_text().strip()
            if content:
                return content
        except Exception:
            pass

    # 3. Not found
    return None


def require_notion_api_key() -> str:
    """
    Get Notion API key, raise error if not found

    Returns:
        API key string

    Raises:
        ValueError: If API key not found
    """
    key = get_notion_api_key()
    if not key:
        raise ValueError(
            "NOTION_API_KEY not found. "
            "Set environment variable or create ~/.notion_key file."
        )
    return key


# ============================================================================
# Global Authenticator
# ============================================================================

_global_authenticator: Optional[Authenticator] = None
_auth_lock = threading.Lock()


def get_authenticator() -> Authenticator:
    """Get global authenticator instance"""
    global _global_authenticator

    with _auth_lock:
        if _global_authenticator is None:
            _global_authenticator = Authenticator()

    return _global_authenticator


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "AuthMethod",
    "AuthResult",
    "APIKeyAuth",
    "JWTAuth",
    "Authenticator",
    "get_authenticator",
    "get_notion_api_key",
    "require_notion_api_key",
]
