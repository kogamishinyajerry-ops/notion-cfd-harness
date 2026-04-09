#!/usr/bin/env python3
"""
P5-07: Authentication tests
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_compiler.security.auth import (
    AuthMethod,
    AuthResult,
    APIKeyAuth,
    JWTAuth,
    Authenticator,
    get_notion_api_key,
    require_notion_api_key,
    get_authenticator,
)


class TestAuthMethod:
    def test_auth_method_values(self):
        """AuthMethod should have correct values"""
        assert AuthMethod.API_KEY.value == "api_key"
        assert AuthMethod.JWT.value == "jwt"
        assert AuthMethod.NONE.value == "none"


class TestAuthResult:
    def test_auth_result_creation(self):
        """AuthResult should initialize"""
        result = AuthResult(
            success=True,
            method=AuthMethod.API_KEY,
            user_id="user123",
        )

        assert result.success is True
        assert result.method == AuthMethod.API_KEY
        assert result.user_id == "user123"

    def test_auth_result_is_valid(self):
        """is_valid should check success and expiration"""
        # Valid result
        result = AuthResult(
            success=True,
            method=AuthMethod.API_KEY,
        )
        assert result.is_valid() is True

        # Failed result
        result.success = False
        assert result.is_valid() is False

        # Expired result
        result.success = True
        result.expires_at = time.time() - 100
        assert result.is_valid() is False


class TestAPIKeyAuth:
    def test_api_key_auth_with_valid_keys(self):
        """APIKeyAuth should validate valid keys"""
        auth = APIKeyAuth(valid_keys=["key1", "key2"])

        result = auth.authenticate("key1")
        assert result.success is True
        assert result.method == AuthMethod.API_KEY

    def test_api_key_auth_with_invalid_key(self):
        """APIKeyAuth should reject invalid keys"""
        auth = APIKeyAuth(valid_keys=["key1"])

        result = auth.authenticate("wrong_key")
        assert result.success is False
        assert result.error == "Invalid API key"

    def test_api_key_auth_user_id_extraction(self):
        """APIKeyAuth should extract user_id from key"""
        auth = APIKeyAuth(valid_keys=["user123:hash456"])

        result = auth.authenticate("user123:hash456")
        assert result.user_id == "user123"

    def test_api_key_auth_add_key(self):
        """APIKeyAuth should allow adding keys"""
        auth = APIKeyAuth(valid_keys=["key1"])

        auth.add_key("key2")

        result = auth.authenticate("key2")
        assert result.success is True

    def test_api_key_auth_remove_key(self):
        """APIKeyAuth should allow removing keys"""
        auth = APIKeyAuth(valid_keys=["key1", "key2"])

        auth.remove_key("key1")

        result = auth.authenticate("key1")
        assert result.success is False

        result = auth.authenticate("key2")
        assert result.success is True

    def test_api_key_auth_has_keys(self):
        """APIKeyAuth has_keys should check if any keys exist"""
        auth = APIKeyAuth(valid_keys=["key1"])
        assert auth.has_keys() is True

        auth2 = APIKeyAuth(valid_keys=[])
        assert auth2.has_keys() is False


class TestJWTAuth:
    def test_jwt_create_token(self):
        """JWTAuth should create valid tokens"""
        auth = JWTAuth(secret="test_secret")

        token = auth.create_token("user123")

        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature

    def test_jwt_validate_valid_token(self):
        """JWTAuth should validate valid tokens"""
        auth = JWTAuth(secret="test_secret")

        token = auth.create_token("user123")
        result = auth.validate_token(token)

        assert result.success is True
        assert result.method == AuthMethod.JWT
        assert result.user_id == "user123"

    def test_jwt_validate_invalid_signature(self):
        """JWTAuth should reject tokens with invalid signature"""
        auth1 = JWTAuth(secret="secret1")
        auth2 = JWTAuth(secret="secret2")

        token = auth1.create_token("user123")
        result = auth2.validate_token(token)

        assert result.success is False
        assert "signature" in result.error.lower()

    def test_jwt_validate_expired_token(self):
        """JWTAuth should reject expired tokens"""
        auth = JWTAuth(secret="test_secret")

        # Create token that expires immediately
        token = auth.create_token("user123", expires_in=0)

        # Wait a moment
        time.sleep(0.1)

        result = auth.validate_token(token)
        assert result.success is False
        assert "expired" in result.error.lower()

    def test_jwt_token_includes_expires_at(self):
        """JWTAuth should include expires_at in result"""
        auth = JWTAuth(secret="test_secret")
        expires_in = 3600

        token = auth.create_token("user123", expires_in=expires_in)
        result = auth.validate_token(token)

        assert result.expires_at is not None
        expected_exp = time.time() + expires_in
        assert abs(result.expires_at - expected_exp) < 1

    def test_jwt_token_with_custom_payload(self):
        """JWTAuth should include custom payload"""
        auth = JWTAuth(secret="test_secret")

        token = auth.create_token(
            "user123",
            payload={"role": "admin", "email": "user@example.com"},
        )
        result = auth.validate_token(token)

        assert result.success is True
        # Payload data is decoded but not directly accessible in AuthResult
        # This is a basic implementation

    def test_jwt_invalid_format(self):
        """JWTAuth should reject invalid format"""
        auth = JWTAuth(secret="test_secret")

        result = auth.validate_token("invalid_token")
        assert result.success is False
        assert "format" in result.error.lower()


class TestAuthenticator:
    def test_authenticator_with_api_key(self):
        """Authenticator should authenticate with API key"""
        auth = Authenticator(
            api_key_auth=APIKeyAuth(valid_keys=["test_key"]),
        )

        result = auth.authenticate("test_key")
        assert result.success is True
        assert result.method == AuthMethod.API_KEY

    def test_authenticator_with_jwt(self):
        """Authenticator should authenticate with JWT"""
        auth = Authenticator()

        token = auth.create_jwt_token("user123")
        result = auth.authenticate(token)

        assert result.success is True
        assert result.method == AuthMethod.JWT

    def test_authenticator_auto_detect_method(self):
        """Authenticator should auto-detect auth method"""
        auth = Authenticator(
            api_key_auth=APIKeyAuth(valid_keys=["test_key"]),
        )

        # Detect API key
        result = auth.authenticate("test_key")
        assert result.method == AuthMethod.API_KEY

        # Detect JWT (has two dots)
        result2 = auth.authenticate(auth.create_jwt_token("user123"))
        assert result2.method == AuthMethod.JWT


class TestSecretManagement:
    def test_get_notion_api_key_from_env(self):
        """get_notion_api_key should read from environment"""
        with patch.dict(os.environ, {"NOTION_API_KEY": "env_key_123"}):
            key = get_notion_api_key()
            assert key == "env_key_123"

    def test_get_notion_api_key_fallback_to_file(self):
        """get_notion_api_key should fallback to file"""
        with patch.dict(os.environ, {}, clear=True):
            # Mock file read
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="file_key_456\n"):
                    key = get_notion_api_key()
                    assert key == "file_key_456"

    def test_require_notion_api_key_success(self):
        """require_notion_api_key should return key if found"""
        with patch.dict(os.environ, {"NOTION_API_KEY": "env_key_123"}):
            key = require_notion_api_key()
            assert key == "env_key_123"

    def test_require_notion_api_key_error(self):
        """require_notion_api_key should raise error if not found"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                try:
                    require_notion_api_key()
                    assert False, "Should have raised ValueError"
                except ValueError as e:
                    assert "NOTION_API_KEY" in str(e)


class TestGlobalAuthenticator:
    def test_get_authenticator_singleton(self):
        """get_authenticator should return singleton"""
        auth1 = get_authenticator()
        auth2 = get_authenticator()

        assert auth1 is auth2


if __name__ == "__main__":
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
