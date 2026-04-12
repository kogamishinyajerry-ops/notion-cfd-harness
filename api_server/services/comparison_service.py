"""
ComparisonService — Cross-case comparison engine (PIPE-11).

Provides:
  - Convergence history parsing from solver log files
  - Provenance mismatch detection
  - Delta field computation via pvpython in ParaView container
  - ComparisonResult JSON construction
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api_server.models import (
    ComparisonCreate,
    ComparisonResponse,
    ComparisonListResponse,
    ConvergenceDataPoint,
    MetricsRow,
    ProvenanceMismatchItem,
    ProvenanceMetadata,
    SweepCaseResponse,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Convergence Log Parser
# =============================================================================

def parse_convergence_log(case_output_dir: Path, solver_name: str = "simpleFoam") -> List[Dict[str, Any]]:
    """
    Parse per-iteration residuals from OpenFOAM solver log.

    File: {case_output_dir}/log.{solver_name}

    Confirmed regexes from knowledge_compiler/orchestrator/monitor.py:
      time_pattern = r"Time = ([\d.]+)"
      residual_pattern = r"(Ux|Uy|Uz|p) = ([\d.e+-]+)"

    Returns list of {iteration: int, Ux: float, Uy: float, Uz: float, p: float}.
    Each dict represents one solver iteration.
    """
    log_path = case_output_dir / f"log.{solver_name}"
    if not log_path.exists():
        logger.warning(f"Convergence log not found: {log_path}")
        return []

    content = log_path.read_text(errors="replace")
    time_pattern = re.compile(r"Time = ([\d.]+)")
    residual_pattern = re.compile(r"(Ux|Uy|Uz|p)\s*=\s*([\d.e+-]+)")

    results: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    for line in content.split("\n"):
        time_match = time_pattern.search(line)
        if time_match:
            if current:
                results.append(current)
            current = {"iteration": len(results)}
        residual_match = residual_pattern.search(line)
        if residual_match and current is not None:
            field_name = residual_match.group(1)  # Ux, Uy, Uz, p
            value = float(residual_match.group(2))
            current[field_name] = value

    if current:
        results.append(current)

    return results


# =============================================================================
# Delta Field Computation
# =============================================================================

def compute_delta_field(
    case_a_dir: Path,
    case_b_dir: Path,
    field_name: str,
    output_dir: Path,
) -> Tuple[bool, str, Optional[str]]:
    """
    Compute CaseB.{field_name} - CaseA.{field_name} using pvpython in ParaView container.

    Writes a pvpython script to output_dir and executes it via docker exec.
    The script loads both case directories via OpenFOAMReader, computes the
    point-data delta, and saves as {output_dir}/delta_{hash}.vtu.

    Returns (success: bool, error_message: str, delta_vtu_path: Optional[str]).
    """
    import time as _time
    script_id = uuid.uuid4().hex[:8]
    script_path = output_dir / f"delta_script_{script_id}.py"
    output_vtu = output_dir / f"delta_{script_id}.vtu"

    # Build script without triple-quote f-string nesting issues
    script_lines = [
        "from paraview import simple",
        "import os",
        "",
        f"case_a = r\"{case_a_dir}\"",
        f"case_b = r\"{case_b_dir}\"",
        f"output_vtu = r\"{output_vtu}\"",
        "",
        "# Load both cases",
        "reader_a = simple.OpenFOAMReader(FileName=case_a)",
        "reader_b = simple.OpenFOAMReader(FileName=case_b)",
        "",
        "# Convert cell to point data then extract field",
        "c2p_a = simple.CellDatatoPointData(Input=reader_a)",
        "c2p_b = simple.CellDatatoPointData(Input=reader_b)",
        "calc_a = simple.Calculator(Input=c2p_a)",
        f"calc_a.ResultArrayName = \"{field_name}\"",
        "calc_b = simple.Calculator(Input=c2p_b)",
        f"calc_b.ResultArrayName = \"{field_name}\"",
        "",
        "# ProgrammableFilter to compute delta: b - a",
        "pf = simple.ProgrammableFilter(Input=[calc_a, calc_b])",
        "pf.Script = '''",
        "import numpy as np",
        "inputs = self.GetInputs()",
        "a_arr = inputs[0].GetPointData().GetScalars()",
        "b_arr = inputs[1].GetPointData().GetScalars()",
        "output = self.GetOutput()",
        "numPoints = inputs[0].GetNumberOfPoints()",
        "output.Allocate(numPoints)",
        "for i in range(numPoints):",
        "    output.InsertPoint(i, inputs[0].GetPoint(i))",
        "pd = output.GetPointData()",
        "pd.SetScalars(b_arr - a_arr)",
        "'''",
        "pf.RequestInformationScript = \"\"",
        "pf.RequestUpdateExtentScript = \"\"",
        "",
        "# Write result",
        "writer = simple.CreateWriter(output_vtu, pf)",
        "writer.Update()",
        "print(f\"DELTA_VTU_PATH={output_vtu}\")",
    ]
    script_content = "\n".join(script_lines)

    script_path.write_text(script_content)

    try:
        # Execute via docker exec in the existing ParaView container
        docker_name = os.environ.get("PARAVIEW_CONTAINER_NAME", "cfd-paraview")
        result = subprocess.run(
            ["docker", "exec", docker_name, "pvpython", f"/scripts/{script_path.name}"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(output_dir),
        )
        if result.returncode != 0:
            return False, f"pvpython failed: {result.stderr}", None

        # Find the output path from stdout
        for line in result.stdout.split("\n"):
            if line.startswith("DELTA_VTU_PATH="):
                vtu_path = line.split("=", 1)[1].strip()
                return True, "", vtu_path

        return False, "pvpython did not produce DELTA_VTU_PATH in output", None

    except subprocess.TimeoutExpired:
        return False, "pvpython timed out after 300 seconds", None
    except Exception as e:
        return False, f"docker exec failed: {str(e)}", None
    finally:
        if script_path.exists():
            script_path.unlink()


# =============================================================================
# ComparisonService
# =============================================================================

class ComparisonService:
    """Cross-case comparison engine (PIPE-11)."""

    def __init__(self, sweep_db_service, case_output_base: Path = Path("/tmp/comparisons")):
        self._sweep_db = sweep_db_service
        self._output_base = case_output_base
        self._output_base.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Provenance
    # -------------------------------------------------------------------------

    def check_provenance_mismatch(self, cases: List[SweepCaseResponse]) -> List[ProvenanceMismatchItem]:
        """Return mismatch descriptors for provenance fields that differ across cases."""
        if not cases:
            return []
        fields = ["openfoam_version", "compiler_version", "mesh_seed_hash", "solver_config_hash"]
        mismatches: List[ProvenanceMismatchItem] = []

        # Build provenance dict per case
        provenance_by_case = []
        for case in cases:
            provenance = getattr(case, "provenance", None)
            if provenance is None:
                # Fallback: construct from sweep_cases columns via hasattr
                provenance = {
                    "openfoam_version": getattr(case, "openfoam_version", None),
                    "compiler_version": getattr(case, "compiler_version", None),
                    "mesh_seed_hash": getattr(case, "mesh_seed_hash", None),
                    "solver_config_hash": getattr(case, "solver_config_hash", None),
                }
            provenance_by_case.append(provenance)

        for field in fields:
            values = list(set(p.get(field) for p in provenance_by_case if p.get(field)))
            if len(values) > 1:
                mismatches.append(ProvenanceMismatchItem(field=field, values=values))

        return mismatches

    # -------------------------------------------------------------------------
    # Convergence history
    # -------------------------------------------------------------------------

    def get_convergence_data(self, cases: List[SweepCaseResponse]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse convergence history for each case from solver log file.

        Case output dir pattern (from sweep_runner): sweep_{sweep_id}/{combination_hash}/
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        for case in cases:
            # Determine case output dir from sweep_runner output organization
            # Pattern: {DATA_DIR}/sweep_{sweep_id}/{combination_hash}/
            # Fallback: try to find it from pipeline step output
            case_dir = Path(f"data/sweeps/{case.sweep_id}/{case.combination_hash}")
            if not case_dir.exists():
                case_dir = Path(f"data/sweep_{case.sweep_id}/{case.combination_hash}")
            data = parse_convergence_log(case_dir)
            result[case.id] = data
        return result

    # -------------------------------------------------------------------------
    # Metrics table
    # -------------------------------------------------------------------------

    def build_metrics_table(
        self,
        cases: List[SweepCaseResponse],
        reference_case_id: str,
    ) -> List[MetricsRow]:
        """Build metrics rows with diff_pct vs reference case."""
        rows: List[MetricsRow] = []
        ref_case = next((c for c in cases if c.id == reference_case_id), None)
        ref_residual = None
        if ref_case and ref_case.result_summary:
            ref_residual = ref_case.result_summary.get("final_residual")

        for case in cases:
            params_str = json.dumps(case.param_combination, sort_keys=True)
            final_residual = None
            execution_time = None
            diff_pct = None

            if case.result_summary:
                final_residual = case.result_summary.get("final_residual")
                execution_time = case.result_summary.get("execution_time")

            if ref_residual is not None and final_residual is not None and ref_residual != 0:
                diff_pct = ((final_residual - ref_residual) / abs(ref_residual)) * 100

            rows.append(MetricsRow(
                case_id=case.id,
                params=params_str,
                final_residual=final_residual,
                execution_time=execution_time,
                diff_pct=diff_pct,
            ))

        return rows

    # -------------------------------------------------------------------------
    # Delta field
    # -------------------------------------------------------------------------

    def compute_delta(self, case_a_id: str, case_b_id: str, field_name: str = "p") -> Tuple[bool, str, Optional[str]]:
        """
        Compute delta field for two cases. Returns (success, error, vtu_path).
        """
        case_a = next((c for c in self._sweep_db.get_all_completed_cases() if c.id == case_a_id), None)
        case_b = next((c for c in self._sweep_db.get_all_completed_cases() if c.id == case_b_id), None)

        if not case_a or not case_b:
            return False, "Case not found", None

        case_a_dir = Path(f"data/sweeps/{case_a.sweep_id}/{case_a.combination_hash}")
        if not case_a_dir.exists():
            case_a_dir = Path(f"data/sweep_{case_a.sweep_id}/{case_a.combination_hash}")
        case_b_dir = Path(f"data/sweeps/{case_b.sweep_id}/{case_b.combination_hash}")
        if not case_b_dir.exists():
            case_b_dir = Path(f"data/sweep_{case_b.sweep_id}/{case_b.combination_hash}")

        if not case_a_dir.exists() or not case_b_dir.exists():
            return False, f"Case directory not found: {case_a_dir} or {case_b_dir}", None

        return compute_delta_field(case_a_dir, case_b_dir, field_name, self._output_base)

    # -------------------------------------------------------------------------
    # Comparison CRUD
    # -------------------------------------------------------------------------

    def create_comparison(self, spec: ComparisonCreate) -> ComparisonResponse:
        """Create and persist a comparison result."""
        all_cases = self._sweep_db.get_all_completed_cases()
        cases = [c for c in all_cases if c.id in spec.case_ids]
        if len(cases) != len(spec.case_ids):
            found_ids = {c.id for c in cases}
            missing = [i for i in spec.case_ids if i not in found_ids]
            raise ValueError(f"Cases not found: {missing}")

        # Provenance mismatch check
        provenance_mismatch = self.check_provenance_mismatch(cases)

        # Convergence data
        convergence_data = self.get_convergence_data(cases)

        # Metrics table
        metrics_table = self.build_metrics_table(cases, spec.reference_case_id)

        # Delta field (optional)
        delta_vtu_url = None
        if spec.delta_case_a_id and spec.delta_case_b_id:
            ok, err, vtu_path = self.compute_delta(
                spec.delta_case_a_id, spec.delta_case_b_id, spec.delta_field_name
            )
            if ok and vtu_path:
                delta_vtu_url = f"/comparisons/delta/{Path(vtu_path).name}"
            else:
                logger.warning(f"Delta field computation failed: {err}")

        now = datetime.now(timezone.utc)
        comparison_id = f"COMP-{uuid.uuid4().hex[:8].upper()}"
        comparison = ComparisonResponse(
            id=comparison_id,
            name=spec.name,
            reference_case_id=spec.reference_case_id,
            case_ids=spec.case_ids,
            provenance_mismatch=provenance_mismatch,
            convergence_data={k: [ConvergenceDataPoint(**pt) for pt in v] for k, v in convergence_data.items()},
            metrics_table=metrics_table,
            delta_case_a_id=spec.delta_case_a_id,
            delta_case_b_id=spec.delta_case_b_id,
            delta_field_name=spec.delta_field_name if spec.delta_case_a_id else None,
            delta_vtu_url=delta_vtu_url,
            created_at=now,
            updated_at=now,
        )

        # Persist to SQLite
        self._sweep_db.add_comparison(comparison)
        return comparison

    def get_comparison(self, comparison_id: str) -> Optional[ComparisonResponse]:
        return self._sweep_db.get_comparison(comparison_id)

    def list_comparisons(self) -> List[ComparisonResponse]:
        return self._sweep_db.list_comparisons()
