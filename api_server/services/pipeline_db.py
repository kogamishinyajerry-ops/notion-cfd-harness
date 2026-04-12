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


import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from api_server.models import (
    JobStatus,
    PipelineCreate,
    PipelineResponse,
    PipelineStatus,
    PipelineStep,
    PipelineUpdate,
    StepType,
)

logger = logging.getLogger(__name__)


class PipelineDBService:
    """CRUD operations for Pipeline and PipelineStep entities using SQLite."""

    def __init__(self):
        init_pipeline_db()

    # --- Pipeline CRUD ---

    def create_pipeline(self, spec: PipelineCreate) -> PipelineResponse:
        """Create a new pipeline with its steps."""
        pipeline_id = f"PIPELINE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        config_json = json.dumps(spec.config)
        status = PipelineStatus.PENDING.value

        conn = get_pipeline_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO pipelines (id, name, description, status, config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pipeline_id, spec.name, spec.description, status, config_json, now, now))

        # Insert steps
        for step in spec.steps:
            step_type_val = step.step_type.value if hasattr(step.step_type, 'value') else step.step_type
            cursor.execute("""
                INSERT INTO pipeline_steps (pipeline_id, step_id, step_type, step_order, depends_on, params, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pipeline_id,
                step.step_id,
                step_type_val,
                step.step_order,
                json.dumps(step.depends_on),
                json.dumps(step.params),
                JobStatus.PENDING.value,
            ))

        conn.commit()
        conn.close()

        logger.info(f"Created pipeline: {pipeline_id}")
        return self.get_pipeline(pipeline_id)

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineResponse]:
        """Get a pipeline by ID with all its steps."""
        conn = get_pipeline_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        # Load steps
        cursor.execute("SELECT * FROM pipeline_steps WHERE pipeline_id = ? ORDER BY step_order", (pipeline_id,))
        step_rows = cursor.fetchall()
        conn.close()

        steps = []
        for sr in step_rows:
            depends_on = json.loads(sr["depends_on"])
            params = json.loads(sr["params"])
            steps.append(PipelineStep(
                step_id=sr["step_id"],
                step_type=StepType(sr["step_type"]),
                step_order=sr["step_order"],
                depends_on=depends_on,
                params=params,
                status=JobStatus(sr["status"]),
            ))

        config = json.loads(row["config"])
        return PipelineResponse(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=PipelineStatus(row["status"]),
            steps=steps,
            config=config,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_pipelines(self) -> List[PipelineResponse]:
        """List all pipelines."""
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pipelines ORDER BY created_at DESC")
        ids = [r["id"] for r in cursor.fetchall()]
        conn.close()

        results = []
        for pid in ids:
            p = self.get_pipeline(pid)
            if p:
                results.append(p)
        return results

    def update_pipeline(self, pipeline_id: str, update: PipelineUpdate) -> Optional[PipelineResponse]:
        """Update a PENDING pipeline's name/description/config/status."""
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM pipelines WHERE id = ?", (pipeline_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        current_status = row["status"]
        if current_status != PipelineStatus.PENDING.value:
            conn.close()
            raise ValueError(f"Cannot update pipeline with status '{current_status}'. Only PENDING pipelines can be updated.")

        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []

        if update.name is not None:
            fields.append("name = ?")
            values.append(update.name)
        if update.description is not None:
            fields.append("description = ?")
            values.append(update.description)
        if update.config is not None:
            fields.append("config = ?")
            values.append(json.dumps(update.config))
        if update.status is not None:
            fields.append("status = ?")
            values.append(update.status.value)

        fields.append("updated_at = ?")
        values.append(now)
        values.append(pipeline_id)

        cursor.execute(f"UPDATE pipelines SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        conn.close()

        logger.info(f"Updated pipeline: {pipeline_id}")
        return self.get_pipeline(pipeline_id)

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a pipeline and all its steps (ON DELETE CASCADE)."""
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pipelines WHERE id = ?", (pipeline_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            logger.info(f"Deleted pipeline: {pipeline_id}")
        return deleted


# --- Module-level singleton getter (matches CaseService pattern) ---

_pipeline_service: Optional[PipelineDBService] = None


def get_pipeline_db_service() -> PipelineDBService:
    """Get or create the PipelineDBService singleton."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineDBService()
    return _pipeline_service
