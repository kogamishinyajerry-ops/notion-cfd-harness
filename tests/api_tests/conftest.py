"""
Pytest Configuration for API Tests

Provides FastAPI TestClient fixture for API endpoint testing.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
_project_root = str(Path(__file__).parent.parent.parent.resolve())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from fastapi.testclient import TestClient
from api_server.main import app


@pytest.fixture
def client():
    """
    FastAPI test client fixture.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def anyio_backend():
    """Configure anyio to use the asyncio backend."""
    return "asyncio"
