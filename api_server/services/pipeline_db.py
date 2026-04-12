"""
Pipeline Database Layer

SQLite schema initialization and connection factory for pipelines.db.
Handles table creation and provides a shared connection factory.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from api_server.config import DATA_DIR

_DB_PATH: Optional[Path] = None
_INITIALIZED: bool = False


def get_pipeline_db_path() -> Path:
    """Return the path to pipelines.db."""
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = DATA_DIR / "pipelines.db"
    return _DB_PATH


def get_pipeline_db_connection() -> sqlite3.Connection:
    """
    Get a SQLite connection for pipeline operations.

    Returns:
        sqlite3.Connection with row_factory=sqlite3.Row
    """
    db_path = get_pipeline_db_path()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_pipeline_db() -> None:
    """
    Initialize the pipelines.db schema if not already done.

    Creates:
        - pipelines table
        - pipeline_steps table
        - schema_version table (for tracking)
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    db_path = get_pipeline_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_pipeline_db_connection()
    cursor = conn.cursor()

    # Schema version tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Pipelines table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            config TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Pipeline steps table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            step_type TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            depends_on TEXT NOT NULL DEFAULT '[]',
            params TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE,
            UNIQUE(pipeline_id, step_id)
        )
    """)

    # Record schema version (1)
    cursor.execute("SELECT COUNT(*) as cnt FROM schema_version")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("INSERT INTO schema_version (version) VALUES (1)")

    conn.commit()
    conn.close()

    _INITIALIZED = True
