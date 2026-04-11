"""
API Server Configuration

FastAPI + Uvicorn configuration for the AI-CFD Knowledge Harness API.
"""

import os
from pathlib import Path

# Server configuration
HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# API prefix for versioning
API_PREFIX = "/api/v1"

# OpenAPI settings
OPENAPI_URL = f"{API_PREFIX}/openapi.json"
DOCS_URL = "/docs"
REDOC_URL = "/redoc"

# Job settings
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT_SECONDS", "3600"))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))

# ParaView Web settings
PARAVIEW_WEB_PORT = int(os.getenv("PARAVIEW_WEB_PORT", "8081"))
PARAVIEW_WEB_PORT_RANGE_START = int(os.getenv("PARAVIEW_WEB_PORT_RANGE_START", "8081"))
PARAVIEW_WEB_PORT_RANGE_END = int(os.getenv("PARAVIEW_WEB_PORT_RANGE_END", "8090"))
PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES = int(os.getenv("PARAVIEW_WEB_IDLE_TIMEOUT_MINUTES", "30"))
PARAVIEW_WEB_IMAGE = os.getenv("PARAVIEW_WEB_IMAGE", "openfoam/openfoam10-paraview510")
PARAVIEW_WEB_LAUNCHER_TIMEOUT = int(os.getenv("PARAVIEW_WEB_LAUNCHER_TIMEOUT", "60"))
