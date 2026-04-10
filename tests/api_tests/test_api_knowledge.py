"""
Unit Tests for Knowledge Registry Endpoints

Tests knowledge unit queries for the /knowledge API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestKnowledgeEndpoints:
    """Tests for knowledge registry API endpoints."""

    def test_search_knowledge(self, client: TestClient):
        """Test searching knowledge units."""
        response = client.get("/api/v1/knowledge/search?query=test")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)

    def test_search_knowledge_with_type_filter(self, client: TestClient):
        """Test searching with unit type filter."""
        response = client.get("/api/v1/knowledge/search?query=test&unit_type=formula")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_get_knowledge_unit(self, client: TestClient):
        """Test getting a specific knowledge unit."""
        # First search to find a valid unit ID
        search_response = client.get("/api/v1/knowledge/search?query=CH")
        search_data = search_response.json()

        if search_data["total"] > 0:
            unit_id = search_data["results"][0]["unit_id"]
            response = client.get(f"/api/v1/knowledge/units/{unit_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["unit_id"] == unit_id
            assert "unit_type" in data
            assert "source_file" in data
        else:
            # If no units exist, test 404 case
            response = client.get("/api/v1/knowledge/units/NONEXISTENT")
            assert response.status_code == 404

    def test_get_knowledge_unit_not_found(self, client: TestClient):
        """Test getting a non-existent knowledge unit returns 404."""
        response = client.get("/api/v1/knowledge/units/NONEXISTENT")

        assert response.status_code == 404
        assert "Knowledge unit not found" in response.json()["detail"]

    def test_query_by_type(self, client: TestClient):
        """Test querying knowledge units by type."""
        response = client.get("/api/v1/knowledge/types/chapter")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data

    def test_query_by_type_with_limit(self, client: TestClient):
        """Test querying with custom limit."""
        response = client.get("/api/v1/knowledge/types/formula?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 5

    def test_get_trace(self, client: TestClient):
        """Test getting trace chain for a knowledge unit."""
        # First search to find a valid unit ID
        search_response = client.get("/api/v1/knowledge/search?query=CH")
        search_data = search_response.json()

        if search_data["total"] > 0:
            unit_id = search_data["results"][0]["unit_id"]
            response = client.get(f"/api/v1/knowledge/trace/{unit_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["unit_id"] == unit_id
            assert "trace" in data
        else:
            # If no units exist, test 404 case
            response = client.get("/api/v1/knowledge/trace/NONEXISTENT")
            assert response.status_code == 404

    def test_get_dependencies(self, client: TestClient):
        """Test getting dependencies for a knowledge unit."""
        # First search to find a valid unit ID
        search_response = client.get("/api/v1/knowledge/search?query=CH")
        search_data = search_response.json()

        if search_data["total"] > 0:
            unit_id = search_data["results"][0]["unit_id"]
            response = client.get(f"/api/v1/knowledge/dependencies/{unit_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["unit_id"] == unit_id
            assert "dependencies" in data
        else:
            # If no units exist, test 404 case
            response = client.get("/api/v1/knowledge/dependencies/NONEXISTENT")
            assert response.status_code == 404
