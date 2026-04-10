"""
Unit Tests for Case Management Endpoints

Tests CRUD operations for the /cases API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from api_server.models import CaseSpec, ProblemType, PermissionLevel


class TestCaseEndpoints:
    """Tests for case management API endpoints."""

    def test_create_case(self, client: TestClient):
        """Test creating a new case."""
        spec = CaseSpec(
            name="Test Case",
            problem_type=ProblemType.EXTERNAL_FLOW,
            description="A test case for unit testing",
            physics_models=["RANS", "k-epsilon"],
        )

        response = client.post("/api/v1/cases", json=spec.model_dump())

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Case"
        assert data["problem_type"] == "ExternalFlow"
        assert data["description"] == "A test case for unit testing"
        assert data["status"] == "created"
        assert "case_id" in data
        assert "created_at" in data

    def test_create_case_minimal(self, client: TestClient):
        """Test creating a case with minimal parameters."""
        spec = CaseSpec(
            name="Minimal Case",
        )

        response = client.post("/api/v1/cases", json=spec.model_dump())

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Case"
        assert data["problem_type"] == "ExternalFlow"  # default
        assert data["status"] == "created"

    def test_list_cases_empty(self, client: TestClient):
        """Test listing cases when no cases exist."""
        response = client.get("/api/v1/cases")

        assert response.status_code == 200
        data = response.json()
        assert "cases" in data
        assert "total" in data
        assert isinstance(data["cases"], list)

    def test_list_cases_with_data(self, client: TestClient):
        """Test listing cases after creating some cases."""
        # Create two cases
        spec1 = CaseSpec(name="Case 1")
        spec2 = CaseSpec(name="Case 2")

        client.post("/api/v1/cases", json=spec1.model_dump())
        client.post("/api/v1/cases", json=spec2.model_dump())

        response = client.get("/api/v1/cases")

        assert response.status_code == 200
        data = response.json()
        assert len(data["cases"]) >= 2
        assert data["total"] >= 2

    def test_list_cases_pagination(self, client: TestClient):
        """Test pagination parameters for list cases."""
        # Create a case first
        spec = CaseSpec(name="Paginated Case")
        client.post("/api/v1/cases", json=spec.model_dump())

        response = client.get("/api/v1/cases?offset=0&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 0
        assert data["limit"] == 10

    def test_get_case_by_id(self, client: TestClient):
        """Test retrieving a specific case by ID."""
        # Create a case
        spec = CaseSpec(name="Get Test Case")
        create_response = client.post("/api/v1/cases", json=spec.model_dump())
        case_id = create_response.json()["case_id"]

        response = client.get(f"/api/v1/cases/{case_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == case_id
        assert data["name"] == "Get Test Case"

    def test_get_case_not_found(self, client: TestClient):
        """Test retrieving a non-existent case returns 404."""
        response = client.get("/api/v1/cases/CASE-NONEXISTENT")

        assert response.status_code == 404
        assert "Case not found" in response.json()["detail"]

    def test_update_case(self, client: TestClient):
        """Test updating a case."""
        # Create a case
        spec = CaseSpec(name="Update Test Case")
        create_response = client.post("/api/v1/cases", json=spec.model_dump())
        case_id = create_response.json()["case_id"]

        response = client.patch(
            f"/api/v1/cases/{case_id}",
            json={"name": "Updated Name", "status": "running"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["status"] == "running"

    def test_update_case_not_found(self, client: TestClient):
        """Test updating a non-existent case returns 404."""
        response = client.patch(
            "/api/v1/cases/CASE-NONEXISTENT",
            json={"name": "New Name"}
        )

        assert response.status_code == 404

    def test_update_case_invalid_status(self, client: TestClient):
        """Test updating a case with invalid status."""
        # Create a case
        spec = CaseSpec(name="Invalid Status Test")
        create_response = client.post("/api/v1/cases", json=spec.model_dump())
        case_id = create_response.json()["case_id"]

        response = client.patch(
            f"/api/v1/cases/{case_id}",
            json={"status": "invalid_status"}
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_delete_case(self, client: TestClient):
        """Test deleting a case."""
        # Create a case
        spec = CaseSpec(name="Delete Test Case")
        create_response = client.post("/api/v1/cases", json=spec.model_dump())
        case_id = create_response.json()["case_id"]

        # Delete the case
        response = client.delete(f"/api/v1/cases/{case_id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/v1/cases/{case_id}")
        assert get_response.status_code == 404

    def test_delete_case_not_found(self, client: TestClient):
        """Test deleting a non-existent case returns 404."""
        response = client.delete("/api/v1/cases/CASE-NONEXISTENT")

        assert response.status_code == 404
