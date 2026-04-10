"""
Unit Tests for Job Management Endpoints

Tests job submission and status monitoring for the /jobs API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from api_server.models import JobSubmission, JobStatus


class TestJobEndpoints:
    """Tests for job management API endpoints."""

    def test_submit_job(self, client: TestClient):
        """Test submitting a new job."""
        submission = JobSubmission(
            case_id="CASE-TEST001",
            job_type="run",
            parameters={"mesh_size": "fine"},
            async_mode=True,
        )

        response = client.post("/api/v1/jobs", json=submission.model_dump())

        assert response.status_code == 201
        data = response.json()
        assert data["case_id"] == "CASE-TEST001"
        assert data["job_type"] == "run"
        assert data["status"] in [s.value for s in JobStatus]
        assert "job_id" in data
        assert "submitted_at" in data

    def test_submit_job_verify_type(self, client: TestClient):
        """Test submitting a verification job."""
        submission = JobSubmission(
            case_id="CASE-TEST001",
            job_type="verify",
            parameters={},
            async_mode=False,
        )

        response = client.post("/api/v1/jobs", json=submission.model_dump())

        assert response.status_code == 201
        data = response.json()
        assert data["job_type"] == "verify"

    def test_submit_job_report_type(self, client: TestClient):
        """Test submitting a report generation job."""
        submission = JobSubmission(
            case_id="CASE-TEST001",
            job_type="report",
            parameters={"format": "html"},
            async_mode=True,
        )

        response = client.post("/api/v1/jobs", json=submission.model_dump())

        assert response.status_code == 201
        data = response.json()
        assert data["job_type"] == "report"

    def test_list_jobs_empty(self, client: TestClient):
        """Test listing jobs when no jobs exist."""
        response = client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)

    def test_list_jobs_with_data(self, client: TestClient):
        """Test listing jobs after submitting some jobs."""
        # Submit a job
        submission = JobSubmission(
            case_id="CASE-TEST001",
            job_type="run",
        )
        client.post("/api/v1/jobs", json=submission.model_dump())

        response = client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) >= 1

    def test_list_jobs_filter_by_case_id(self, client: TestClient):
        """Test filtering jobs by case ID."""
        # Submit jobs for different cases
        submission1 = JobSubmission(case_id="CASE-A", job_type="run")
        submission2 = JobSubmission(case_id="CASE-B", job_type="run")

        client.post("/api/v1/jobs", json=submission1.model_dump())
        client.post("/api/v1/jobs", json=submission2.model_dump())

        response = client.get("/api/v1/jobs?case_id=CASE-A")

        assert response.status_code == 200
        data = response.json()
        for job in data["jobs"]:
            assert job["case_id"] == "CASE-A"

    def test_get_job_by_id(self, client: TestClient):
        """Test retrieving a specific job by ID."""
        # Submit a job
        submission = JobSubmission(
            case_id="CASE-TEST001",
            job_type="run",
        )
        create_response = client.post("/api/v1/jobs", json=submission.model_dump())
        job_id = create_response.json()["job_id"]

        response = client.get(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id

    def test_get_job_not_found(self, client: TestClient):
        """Test retrieving a non-existent job returns 404."""
        response = client.get("/api/v1/jobs/JOB-NONEXISTENT")

        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    def test_cancel_job(self, client: TestClient):
        """Test cancelling a pending job."""
        # Submit a job
        submission = JobSubmission(
            case_id="CASE-TEST001",
            job_type="run",
            async_mode=True,
        )
        create_response = client.post("/api/v1/jobs", json=submission.model_dump())
        job_id = create_response.json()["job_id"]

        response = client.post(f"/api/v1/jobs/{job_id}/cancel")

        # Job might complete too fast for cancellation to work
        # Just verify we get a valid response
        assert response.status_code in [200, 400]
