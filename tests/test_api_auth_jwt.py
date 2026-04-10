"""
Authentication Tests

Tests for JWT authentication, RBAC middleware, and auth endpoints.
"""

import time
import pytest
from datetime import datetime, timedelta, timezone

from api_server.auth.jwt_handler import JWTAuth, TokenData, create_tokens
from api_server.auth.session_store import SessionStore, UserSession
from api_server.auth.rbac_middleware import AuthenticatedUser
from knowledge_compiler.security.rbac import RBACEngine


class TestJWTAuth:
    """Tests for JWT token handling"""

    def test_create_and_verify_access_token(self):
        """Test creating and verifying an access token"""
        token_data = TokenData(
            user_id="user-123",
            role="admin",
            permission_level="L3",
        )
        token = JWTAuth.create_access_token(token_data)

        assert token is not None
        assert isinstance(token, str)

        # Verify the token
        decoded = JWTAuth.verify_token(token)
        assert decoded is not None
        assert decoded.user_id == "user-123"
        assert decoded.role == "admin"
        assert decoded.permission_level == "L3"

    def test_create_and_verify_refresh_token(self):
        """Test creating and verifying a refresh token"""
        token_data = TokenData(
            user_id="user-456",
            role="writer",
            permission_level="L2",
        )
        token = JWTAuth.create_refresh_token(token_data)

        assert token is not None
        decoded = JWTAuth.verify_token(token, token_type="refresh")
        assert decoded is not None
        assert decoded.user_id == "user-456"

    def test_verify_invalid_token(self):
        """Test that invalid tokens return None"""
        result = JWTAuth.verify_token("invalid.token.here")
        assert result is None

    def test_verify_token_with_wrong_type(self):
        """Test that access token fails refresh verification"""
        token_data = TokenData(
            user_id="user-789",
            role="reader",
            permission_level="L0",
        )
        access_token = JWTAuth.create_access_token(token_data)

        # Access token should fail refresh verification
        result = JWTAuth.verify_token(access_token, token_type="refresh")
        assert result is None

    def test_create_tokens_convenience(self):
        """Test the create_tokens convenience function"""
        tokens = create_tokens(
            user_id="user-test",
            role="admin",
            permission_level="L3",
        )

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"

        # Verify access token works
        decoded = JWTAuth.verify_token(tokens["access_token"])
        assert decoded is not None
        assert decoded.user_id == "user-test"

    def test_token_contains_expiration(self):
        """Test that tokens contain expiration info"""
        token_data = TokenData(
            user_id="user-exp",
            role="writer",
            permission_level="L1",
        )
        token = JWTAuth.create_access_token(token_data)

        decoded = JWTAuth.decode_token_unsafe(token)
        assert decoded is not None
        assert "exp" in decoded
        assert "iat" in decoded


class TestSessionStore:
    """Tests for session management"""

    def test_create_and_get_session(self):
        """Test creating and retrieving a session"""
        store = SessionStore()

        session_id = store.create_session(
            user_id="user-001",
            username="testuser",
            role="admin",
            permission_level="L3",
        )

        assert session_id is not None
        session = store.get_session(session_id)
        assert session is not None
        assert session.user_id == "user-001"
        assert session.username == "testuser"
        assert session.role == "admin"
        assert session.permission_level == "L3"

    def test_delete_session(self):
        """Test deleting a session"""
        store = SessionStore()

        session_id = store.create_session(
            user_id="user-002",
            username="testuser2",
            role="writer",
            permission_level="L2",
        )

        # Delete session
        result = store.delete_session(session_id)
        assert result is True

        # Session should not be found
        session = store.get_session(session_id)
        assert session is None

    def test_delete_nonexistent_session(self):
        """Test deleting a non-existent session returns False"""
        store = SessionStore()
        result = store.delete_session("nonexistent-session-id")
        assert result is False

    def test_delete_user_sessions(self):
        """Test deleting all sessions for a user"""
        store = SessionStore()

        # Create multiple sessions for same user
        session_id1 = store.create_session(
            user_id="user-multi",
            username="multiuser",
            role="reader",
            permission_level="L0",
        )
        session_id2 = store.create_session(
            user_id="user-multi",
            username="multiuser",
            role="reader",
            permission_level="L0",
        )

        # Delete all user sessions
        count = store.delete_user_sessions("user-multi")
        assert count == 2

        # Both sessions should be gone
        assert store.get_session(session_id1) is None
        assert store.get_session(session_id2) is None

    def test_get_user_session_count(self):
        """Test getting session count for a user"""
        store = SessionStore()

        # Create sessions for different users
        store.create_session(
            user_id="user-a",
            username="usera",
            role="admin",
            permission_level="L3",
        )
        store.create_session(
            user_id="user-b",
            username="userb",
            role="writer",
            permission_level="L1",
        )
        store.create_session(
            user_id="user-b",
            username="userb",
            role="writer",
            permission_level="L1",
        )

        assert store.get_user_session_count("user-a") == 1
        assert store.get_user_session_count("user-b") == 2
        assert store.get_user_session_count("nonexistent") == 0

    def test_token_blacklisting(self):
        """Test token blacklisting"""
        store = SessionStore()

        # Blacklist some tokens
        store.blacklist_token("token-1")
        store.blacklist_token("token-2")

        assert store.is_token_blacklisted("token-1") is True
        assert store.is_token_blacklisted("token-2") is True
        assert store.is_token_blacklisted("token-3") is False


class TestAuthenticatedUser:
    """Tests for AuthenticatedUser"""

    def test_create_authenticated_user(self):
        """Test creating an AuthenticatedUser"""
        user = AuthenticatedUser(
            user_id="user-test",
            username="testuser",
            role="admin",
            permission_level="L3",
            session_id="session-123",
        )

        assert user.user_id == "user-test"
        assert user.username == "testuser"
        assert user.role == "admin"
        assert user.permission_level == "L3"
        assert user.session_id == "session-123"

    def test_to_session_conversion(self):
        """Test converting AuthenticatedUser to UserSession"""
        user = AuthenticatedUser(
            user_id="user-conv",
            username="convuser",
            role="writer",
            permission_level="L2",
        )

        session = user.to_session()
        assert isinstance(session, UserSession)
        assert session.user_id == "user-conv"
        assert session.username == "convuser"
        assert session.role == "writer"
        assert session.permission_level == "L2"


class TestRBACIntegration:
    """Tests for RBAC integration"""

    def test_rbac_engine_user_management(self):
        """Test RBAC engine user creation and role assignment"""
        rbac = RBACEngine()

        # Create user
        user = rbac.create_user("test-user")
        assert user is not None
        assert user.user_id == "test-user"

        # Assign role
        result = rbac.assign_role("test-user", "admin")
        assert result is True

        # Check permission
        can_access = rbac.check_permission("test-user", "memory_network", "read")
        assert can_access is True

    def test_rbac_permission_levels(self):
        """Test RBAC with different permission levels"""
        rbac = RBACEngine()

        # Create users with different roles
        admin = rbac.create_user("admin-user")
        writer = rbac.create_user("writer-user")
        reader = rbac.create_user("reader-user")

        rbac.assign_role("admin-user", "admin")
        rbac.assign_role("writer-user", "writer")
        rbac.assign_role("reader-user", "reader")

        # Admin should have all permissions
        assert rbac.check_permission("admin-user", "memory_network", "read") is True
        assert rbac.check_permission("admin-user", "memory_network", "write") is True
        assert rbac.check_permission("admin-user", "memory_network", "delete") is True

        # Writer should have read and write
        assert rbac.check_permission("writer-user", "memory_network", "read") is True
        assert rbac.check_permission("writer-user", "memory_network", "write") is True
        assert rbac.check_permission("writer-user", "memory_network", "delete") is False

        # Reader should only have read
        assert rbac.check_permission("reader-user", "memory_network", "read") is True
        assert rbac.check_permission("reader-user", "memory_network", "write") is False
        assert rbac.check_permission("reader-user", "memory_network", "delete") is False


class TestTokenData:
    """Tests for TokenData"""

    def test_token_data_creation(self):
        """Test creating TokenData"""
        token_data = TokenData(
            user_id="user-td",
            role="tester",
            permission_level="L1",
        )

        assert token_data.user_id == "user-td"
        assert token_data.role == "tester"
        assert token_data.permission_level == "L1"
        assert token_data.issued_at is not None
        assert token_data.expires_at is not None
        assert token_data.expires_at > token_data.issued_at

    def test_token_data_with_custom_expiration(self):
        """Test TokenData with custom expiration delta"""
        custom_delta = timedelta(hours=2)
        token_data = TokenData(
            user_id="user-custom",
            role="custom",
            permission_level="L0",
            exp_delta=custom_delta,
        )

        # Expiration should be approximately 2 hours from now
        expected_exp = datetime.now(timezone.utc) + custom_delta
        diff = abs((token_data.expires_at - expected_exp).total_seconds())
        assert diff < 5  # Within 5 seconds tolerance

    def test_token_data_to_dict(self):
        """Test TokenData serialization to dict"""
        token_data = TokenData(
            user_id="user-dict",
            role="dict-role",
            permission_level="L2",
        )

        data = token_data.to_dict()
        assert data["user_id"] == "user-dict"
        assert data["role"] == "dict-role"
        assert data["permission_level"] == "L2"
        assert "iat" in data
        assert "exp" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
