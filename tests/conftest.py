"""
Root conftest for AI-CFD Knowledge Harness tests.

Sets up Python path for api_server imports.
"""

import sys
from pathlib import Path

# Add project root to path for api_server imports
_project_root = Path(__file__).parent.parent.resolve()
_str_root = str(_project_root)
if _str_root not in sys.path:
    sys.path.insert(0, _str_root)

# =============================================================================
# Comparison Service Fixtures (PIPE-11)
# =============================================================================

import pytest, sqlite3, json, tempfile, os
from pathlib import Path as _Path

@pytest.fixture
def temp_db():
    """In-memory SQLite DB with schema v4 applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Minimal schema: schema_version + sweep_cases + comparisons
    cur.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))")
    cur.execute("""CREATE TABLE sweep_cases (
        id TEXT PRIMARY KEY, sweep_id TEXT, param_combination TEXT, combination_hash TEXT,
        pipeline_id TEXT, status TEXT, result_summary TEXT, created_at TEXT, updated_at TEXT,
        openfoam_version TEXT, compiler_version TEXT, mesh_seed_hash TEXT, solver_config_hash TEXT
    )""")
    cur.execute("""CREATE TABLE comparisons (
        id TEXT PRIMARY KEY, name TEXT, reference_case_id TEXT NOT NULL, case_ids TEXT NOT NULL,
        provenance_mismatch TEXT, convergence_data TEXT, metrics_table TEXT,
        delta_case_a_id TEXT, delta_case_b_id TEXT, delta_field_name TEXT, delta_vtu_path TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    cur.execute("INSERT INTO schema_version VALUES (4, datetime('now'))")
    conn.commit()
    yield conn
    conn.close()

@pytest.fixture
def sample_cases(temp_db):
    """Two completed sweep cases for comparison tests."""
    cur = temp_db.cursor()
    cases = [
        ("CASE-A00001", "SWP-001", '{"velocity":1.0}', "hash0001", "PIPE-001", "COMPLETED", '{"final_residual":1e-5,"execution_time":120}', "2025-01-01T00:00:00", "2025-01-01T00:02:00", "v10", "gcc11", "meshhash1", "solverhash1"),
        ("CASE-B00002", "SWP-001", '{"velocity":2.0}', "hash0002", "PIPE-001", "COMPLETED", '{"final_residual":2e-5,"execution_time":115}', "2025-01-01T00:01:00", "2025-01-01T00:03:00", "v10", "gcc11", "meshhash1", "solverhash1"),
    ]
    for c in cases:
        cur.execute("""INSERT INTO sweep_cases
            (id, sweep_id, param_combination, combination_hash, pipeline_id, status, result_summary, created_at, updated_at, openfoam_version, compiler_version, mesh_seed_hash, solver_config_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", c)
    temp_db.commit()
    return cases
