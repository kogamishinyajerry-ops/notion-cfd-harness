"""Comparison API endpoint smoke tests — PIPE-11."""
import pytest
from fastapi.testclient import TestClient
from api_server.main import app

client = TestClient(app)


def test_get_cases_empty():
    r = client.get("/api/v1/sweep-cases")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_comparisons_empty():
    r = client.get("/api/v1/comparisons")
    assert r.status_code == 200
    assert r.json() == {"comparisons": []}
