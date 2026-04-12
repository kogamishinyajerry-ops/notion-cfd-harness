"""
Pipeline Database Layer

SQLite schema initialization and connection factory for pipelines.db.
Handles table creation and provides a shared connection factory.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from api_server.config import DATA_DIR
from api_server.models import (
    PipelineCreate,
    PipelineResponse,
    PipelineStatus,
    PipelineStep,
    PipelineUpdate,
    StepResult,
    StepResultStatus,
    StepStatus,
    StepType,
    SweepStatus,
    SweepCaseStatus,
    SweepCreate,
    SweepResponse,
    SweepCaseResponse,
    # Comparison models (PIPE-11)
    ComparisonResponse,
    ComparisonListResponse,
    ConvergenceDataPoint,
    MetricsRow,
    ProvenanceMismatchItem,
    ProvenanceMetadata,
)

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
        - sweeps + sweep_cases tables (schema v3)
        - provenance columns on sweep_cases + comparisons table (schema v4)
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

    # Schema v2: add result_json and updated_at columns to pipeline_steps
    cursor.execute("SELECT COUNT(*) as cnt FROM schema_version WHERE version >= 2")
    if cursor.fetchone()["cnt"] == 0:
        try:
            cursor.execute("ALTER TABLE pipeline_steps ADD COLUMN result_json TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            cursor.execute("ALTER TABLE pipeline_steps ADD COLUMN updated_at TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")

    # Schema v3: sweep tables (PIPE-10)
    cursor.execute("SELECT COUNT(*) as cnt FROM schema_version WHERE version >= 3")
    if cursor.fetchone()["cnt"] == 0:
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sweeps (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    base_pipeline_id TEXT NOT NULL,
                    param_grid TEXT NOT NULL DEFAULT '{}',
                    max_concurrent INTEGER NOT NULL DEFAULT 2,
                    status TEXT NOT NULL DEFAULT 'pending',
                    total_combinations INTEGER NOT NULL DEFAULT 0,
                    completed_combinations INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        except sqlite3.OperationalError:
            pass  # table already exists
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sweep_cases (
                    id TEXT PRIMARY KEY,
                    sweep_id TEXT NOT NULL,
                    param_combination TEXT NOT NULL DEFAULT '{}',
                    combination_hash TEXT NOT NULL,
                    pipeline_id TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    result_summary TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (sweep_id) REFERENCES sweeps(id) ON DELETE CASCADE
                )
            """)
        except sqlite3.OperationalError:
            pass  # table already exists
        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")
        conn.commit()

    # Schema v4: provenance columns on sweep_cases + comparisons table (PIPE-11)
    cursor.execute("SELECT COUNT(*) as cnt FROM schema_version WHERE version >= 4")
    if cursor.fetchone()["cnt"] == 0:
        # Provenance columns on sweep_cases
        for col, col_type in [
            ("openfoam_version", "TEXT"),
            ("compiler_version", "TEXT"),
            ("mesh_seed_hash", "TEXT"),
            ("solver_config_hash", "TEXT"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE sweep_cases ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # column already exists

        # Comparisons table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comparisons (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    reference_case_id TEXT NOT NULL,
                    case_ids TEXT NOT NULL,  -- JSON list
                    provenance_mismatch TEXT,  -- JSON list of {field, values}
                    convergence_data TEXT,     -- JSON: {case_id: [{iteration, Ux, Uy, Uz, p}, ...]}
                    metrics_table TEXT,        -- JSON: [{case_id, params, final_residual, execution_time, diff_pct}, ...]
                    delta_case_a_id TEXT,
                    delta_case_b_id TEXT,
                    delta_field_name TEXT,
                    delta_vtu_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        except sqlite3.OperationalError:
            pass  # table already exists
        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (4)")
        conn.commit()

    conn.commit()
    conn.close()

    _INITIALIZED = True


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
                StepStatus.PENDING.value,
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
                status=StepStatus(sr["status"]),
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

    def update_step_status(
        self,
        pipeline_id: str,
        step_id: str,
        status: StepStatus,
        result_json: Optional[str] = None,
    ) -> None:
        """Update a step's execution status and optional result JSON."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        if result_json is not None:
            cursor.execute(
                "UPDATE pipeline_steps SET status=?, result_json=?, updated_at=? "
                "WHERE pipeline_id=? AND step_id=?",
                (status.value, result_json, now, pipeline_id, step_id),
            )
        else:
            cursor.execute(
                "UPDATE pipeline_steps SET status=?, updated_at=? "
                "WHERE pipeline_id=? AND step_id=?",
                (status.value, now, pipeline_id, step_id),
            )
        conn.commit()
        conn.close()

    def update_pipeline_status(self, pipeline_id: str, status: PipelineStatus) -> None:
        """Update a pipeline's overall status."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE pipelines SET status=?, updated_at=? WHERE id=?",
            (status.value, now, pipeline_id),
        )
        conn.commit()
        conn.close()

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


# =============================================================================
# SweepDBService — CRUD for sweeps and sweep_cases (PIPE-10)
# =============================================================================


class SweepDBService:
    """CRUD operations for Sweep and SweepCase entities using SQLite."""

    def __init__(self):
        init_pipeline_db()

    def create_sweep(self, spec: SweepCreate, total_combinations: int) -> SweepResponse:
        """Create a new sweep with initial QUEUED cases for each param combination."""
        import itertools
        import uuid as _uuid

        sweep_id = f"SWEEP-{_uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        conn = get_pipeline_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sweeps (id, name, description, base_pipeline_id, param_grid, max_concurrent, status, total_combinations, completed_combinations, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sweep_id,
            spec.name,
            spec.description,
            spec.base_pipeline_id,
            json.dumps(spec.param_grid),
            spec.max_concurrent,
            SweepStatus.PENDING.value,
            total_combinations,
            0,
            now,
            now,
        ))

        # Create one SweepCase per param combination
        for combo in itertools.product(*spec.param_grid.values()):
            param_dict = dict(zip(spec.param_grid.keys(), combo))
            combo_str = json.dumps(param_dict, sort_keys=True)
            combo_hash = _uuid.uuid5(_uuid.NAMESPACE_DNS, combo_str).hex[:8]
            case_id = f"CASE-{_uuid.uuid4().hex[:8].upper()}"
            cursor.execute("""
                INSERT INTO sweep_cases (id, sweep_id, param_combination, combination_hash, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                case_id,
                sweep_id,
                combo_str,
                combo_hash,
                SweepCaseStatus.QUEUED.value,
                now,
                now,
            ))

        conn.commit()
        conn.close()

        logger.info(f"Created sweep: {sweep_id} with {total_combinations} combinations")
        return self.get_sweep(sweep_id)

    def get_sweep(self, sweep_id: str) -> Optional[SweepResponse]:
        """Get a sweep by ID."""
        conn = get_pipeline_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sweeps WHERE id = ?", (sweep_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return SweepResponse(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            base_pipeline_id=row["base_pipeline_id"],
            param_grid=json.loads(row["param_grid"]),
            max_concurrent=row["max_concurrent"],
            status=SweepStatus(row["status"]),
            total_combinations=row["total_combinations"],
            completed_combinations=row["completed_combinations"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_sweeps(self) -> List[SweepResponse]:
        """List all sweeps."""
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sweeps ORDER BY created_at DESC")
        ids = [r["id"] for r in cursor.fetchall()]
        conn.close()

        results = []
        for sid in ids:
            s = self.get_sweep(sid)
            if s:
                results.append(s)
        return results

    def update_sweep_status(self, sweep_id: str, status: SweepStatus) -> None:
        """Update a sweep's status."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sweeps SET status=?, updated_at=? WHERE id=?",
            (status.value, now, sweep_id),
        )
        conn.commit()
        conn.close()

    def increment_completed(self, sweep_id: str) -> int:
        """Atomically increment completed_combinations counter. Returns new count."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sweeps SET completed_combinations = completed_combinations + 1, updated_at=? WHERE id=?",
            (now, sweep_id),
        )
        conn.commit()
        cursor.execute("SELECT completed_combinations FROM sweeps WHERE id=?", (sweep_id,))
        count = cursor.fetchone()["completed_combinations"]
        conn.close()
        return count

    def delete_sweep(self, sweep_id: str) -> bool:
        """Delete a sweep and all its cases (ON DELETE CASCADE)."""
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sweeps WHERE id = ?", (sweep_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        if deleted:
            logger.info(f"Deleted sweep: {sweep_id}")
        return deleted

    def get_sweep_cases(self, sweep_id: str) -> List[SweepCaseResponse]:
        """Get all cases for a sweep."""
        conn = get_pipeline_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sweep_cases WHERE sweep_id = ? ORDER BY combination_hash", (sweep_id,))
        rows = cursor.fetchall()
        conn.close()

        cases = []
        for row in rows:
            result_summary = json.loads(row["result_summary"]) if row["result_summary"] else None
            cases.append(SweepCaseResponse(
                id=row["id"],
                sweep_id=row["sweep_id"],
                param_combination=json.loads(row["param_combination"]),
                combination_hash=row["combination_hash"],
                pipeline_id=row["pipeline_id"],
                status=SweepCaseStatus(row["status"]),
                result_summary=result_summary,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            ))
        return cases

    def get_case(self, case_id: str) -> Optional[SweepCaseResponse]:
        """Get a single sweep case by ID."""
        conn = get_pipeline_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sweep_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        result_summary = json.loads(row["result_summary"]) if row["result_summary"] else None
        return SweepCaseResponse(
            id=row["id"],
            sweep_id=row["sweep_id"],
            param_combination=json.loads(row["param_combination"]),
            combination_hash=row["combination_hash"],
            pipeline_id=row["pipeline_id"],
            status=SweepCaseStatus(row["status"]),
            result_summary=result_summary,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def update_case_pipeline_id(self, case_id: str, pipeline_id: str) -> None:
        """Assign a pipeline_id to a queued case and set status to RUNNING."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sweep_cases SET pipeline_id=?, status=?, updated_at=? WHERE id=?",
            (pipeline_id, SweepCaseStatus.RUNNING.value, now, case_id),
        )
        conn.commit()
        conn.close()

    def update_case_result(self, case_id: str, status: SweepCaseStatus, result_summary: Optional[Dict[str, Any]]) -> None:
        """Update case status and result summary."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sweep_cases SET status=?, result_summary=?, updated_at=? WHERE id=?",
            (status.value, json.dumps(result_summary) if result_summary else None, now, case_id),
        )
        conn.commit()
        conn.close()

    # -------------------------------------------------------------------------
    # Comparison support (PIPE-11)
    # -------------------------------------------------------------------------

    def get_all_completed_cases(self) -> List[SweepCaseResponse]:
        """Get all completed cases across all sweeps (for case selector)."""
        conn = get_pipeline_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sweep_cases
            WHERE status = 'COMPLETED'
            ORDER BY sweep_id, combination_hash
        """)
        rows = cursor.fetchall()
        conn.close()
        cases = []
        for row in rows:
            result_summary = json.loads(row["result_summary"]) if row["result_summary"] else None
            provenance = ProvenanceMetadata(
                openfoam_version=row["openfoam_version"],
                compiler_version=row["compiler_version"],
                mesh_seed_hash=row["mesh_seed_hash"],
                solver_config_hash=row["solver_config_hash"],
            )
            cases.append(SweepCaseResponse(
                id=row["id"],
                sweep_id=row["sweep_id"],
                param_combination=json.loads(row["param_combination"]),
                combination_hash=row["combination_hash"],
                pipeline_id=row["pipeline_id"],
                status=SweepCaseStatus(row["status"]),
                result_summary=result_summary,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                provenance=provenance,
            ))
        return cases

    def add_comparison(self, comparison: ComparisonResponse) -> ComparisonResponse:
        """Persist a ComparisonResult to the comparisons table."""
        conn = get_pipeline_db_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Serialize convergence_data: {case_id: [datapoints]} -> stored as JSON
        conv_data_json = json.dumps({
            k: [pt.model_dump() for pt in v] for k, v in comparison.convergence_data.items()
        })

        cursor.execute("""
            INSERT INTO comparisons
            (id, name, reference_case_id, case_ids, provenance_mismatch,
             convergence_data, metrics_table, delta_case_a_id, delta_case_b_id,
             delta_field_name, delta_vtu_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comparison.id,
            comparison.name,
            comparison.reference_case_id,
            json.dumps(comparison.case_ids),
            json.dumps([m.model_dump() for m in comparison.provenance_mismatch]),
            conv_data_json,
            json.dumps([r.model_dump() for r in comparison.metrics_table]),
            comparison.delta_case_a_id,
            comparison.delta_case_b_id,
            comparison.delta_field_name,
            comparison.delta_vtu_url,  # stored as path
            now, now,
        ))
        conn.commit()
        conn.close()
        return comparison

    def get_comparison(self, comparison_id: str) -> Optional[ComparisonResponse]:
        """Get a comparison by ID."""
        conn = get_pipeline_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM comparisons WHERE id = ?", (comparison_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_comparison(row)

    def list_comparisons(self) -> List[ComparisonResponse]:
        """List all comparisons."""
        conn = get_pipeline_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM comparisons ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_comparison(r) for r in rows]

    def _row_to_comparison(self, row: sqlite3.Row) -> ComparisonResponse:
        """Convert a comparisons DB row to ComparisonResponse."""
        return ComparisonResponse(
            id=row["id"],
            name=row["name"],
            reference_case_id=row["reference_case_id"],
            case_ids=json.loads(row["case_ids"]),
            provenance_mismatch=[ProvenanceMismatchItem(**m) for m in json.loads(row["provenance_mismatch"] or "[]")],
            convergence_data=json.loads(row["convergence_data"] or "{}"),
            metrics_table=[MetricsRow(**r) for r in json.loads(row["metrics_table"] or "[]")],
            delta_case_a_id=row["delta_case_a_id"],
            delta_case_b_id=row["delta_case_b_id"],
            delta_field_name=row["delta_field_name"],
            delta_vtu_url=row["delta_vtu_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# --- Module-level singleton getter ---

_sweep_service: Optional[SweepDBService] = None


def get_sweep_db_service() -> SweepDBService:
    """Get or create the SweepDBService singleton."""
    global _sweep_service
    if _sweep_service is None:
        _sweep_service = SweepDBService()
    return _sweep_service
