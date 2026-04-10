"""
Unit Tests for Status and Health Endpoints

Tests system status and health check endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestStatusEndpoints:
    """Tests for status API endpoints."""

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_system_status(self, client: TestClient):
        """Test system status endpoint."""
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "status" in data
        assert "uptime_seconds" in data
        assert "active_jobs" in data
        assert "total_cases" in data
        assert "knowledge_units" in data

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
