"""
Authentication Endpoint Integration Tests

Tests for /login, /logout, /refresh, /me endpoints using FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient

from api_server.main import create_app


@pytest.fixture
def client():
    """Create test client for the API"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get authentication headers for a test user"""
    response = client.post(
        "/api/v1/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestLoginEndpoint:
    """Tests for POST /api/v1/login"""

    def test_login_success(self, client):
        """Test successful login returns tokens"""
        response = client.post(
            "/api/v1/login",
            json={"username": "admin", "password": "admin123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_invalid_password(self, client):
        """Test login with wrong password returns 401"""
        response = client.post(
            "/api/v1/login",
            json={"username": "admin", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_login_invalid_username(self, client):
        """Test login with unknown username returns 401"""
        response = client.post(
            "/api/v1/login",
            json={"username": "nonexistent", "password": "password123"},
        )

        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        """Test login with missing fields returns 422"""
        response = client.post(
            "/api/v1/login",
            json={"username": "admin"},
        )

        assert response.status_code == 422  # Validation error

    def test_login_all_demo_users(self, client):
        """Test all demo users can login"""
        users = [
            {"username": "admin", "password": "admin123"},
            {"username": "editor", "password": "editor123"},
            {"username": "user", "password": "user123"},
            {"username": "guest", "password": "guest123"},
        ]

        for user in users:
            response = client.post(
                "/api/v1/login",
                json=user,
            )
            assert response.status_code == 200, f"Failed for {user['username']}"
            data = response.json()
            assert "access_token" in data


class TestLogoutEndpoint:
    """Tests for POST /api/v1/logout"""

    def test_logout_success(self, client, auth_headers):
        """Test successful logout"""
        response = client.post(
            "/api/v1/logout",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["sessions_terminated"] == 1

    def test_logout_without_auth(self, client):
        """Test logout without authentication returns 401"""
        response = client.post("/api/v1/logout")
        assert response.status_code == 401

    def test_logout_with_invalid_token(self, client):
        """Test logout with invalid token returns 401"""
        response = client.post(
            "/api/v1/logout",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


class TestLogoutAllEndpoint:
    """Tests for POST /api/v1/logout-all"""

    def test_logout_all_success(self, client, auth_headers):
        """Test logout all sessions"""
        response = client.post(
            "/api/v1/logout-all",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["sessions_terminated"] >= 1

    def test_logout_all_without_auth(self, client):
        """Test logout-all without authentication returns 401"""
        response = client.post("/api/v1/logout-all")
        assert response.status_code == 401


class TestRefreshEndpoint:
    """Tests for POST /api/v1/refresh"""

    def test_refresh_token_success(self, client):
        """Test successful token refresh"""
        # First login to get a refresh token
        login_response = client.post(
            "/api/v1/login",
            json={"username": "admin", "password": "admin123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        response = client.post(
            "/api/v1/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_with_invalid_token(self, client):
        """Test refresh with invalid token returns 401"""
        response = client.post(
            "/api/v1/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        assert response.status_code == 401

    def test_refresh_with_access_token(self, client):
        """Test refresh with access token instead of refresh token fails"""
        # Login to get an access token
        login_response = client.post(
            "/api/v1/login",
            json={"username": "admin", "password": "admin123"},
        )
        access_token = login_response.json()["access_token"]

        # Try to use access token as refresh token
        response = client.post(
            "/api/v1/refresh",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 401


class TestMeEndpoint:
    """Tests for GET /api/v1/me"""

    def test_get_current_user(self, client, auth_headers):
        """Test getting current user info"""
        response = client.get(
            "/api/v1/me",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "username" in data
        assert "role" in data
        assert "permission_level" in data
        assert "session_count" in data

    def test_me_without_auth(self, client):
        """Test /me without authentication returns 401"""
        response = client.get("/api/v1/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client):
        """Test /me with invalid token returns 401"""
        response = client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


class TestHealthEndpoint:
    """Tests for health endpoint (should not require auth)"""

    def test_health_check(self, client):
        """Test health check works without auth"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
