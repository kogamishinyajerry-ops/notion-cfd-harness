#!/usr/bin/env python3
"""
Phase 3 Solver Runner Tests
"""

import tempfile
import time
from pathlib import Path

import pytest

from knowledge_compiler.phase3.solver_runner import (
    SolverRunner,
    BatchSolverRunner,
    run_solver,
    run_solvers_batch,
)
from knowledge_compiler.phase3.schema import (
    SolverType,
    SolverStatus,
    SolverJob,
    SolverInput,
    SolverConfig,
    JobPriority,
    BoundaryCondition,
)


class TestSolverRunner:
    """Test SolverRunner"""

    def test_runner_init(self):
        """Test runner initialization"""
        runner = SolverRunner()
        assert runner.workspace is not None
        assert len(runner._running_jobs) == 0

    def test_runner_with_workspace(self):
        """Test runner with custom workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SolverRunner(workspace=tmpdir)
            assert runner.workspace == tmpdir

    def test_prepare_case_missing_directory(self):
        """Test prepare_case with missing directory"""
        runner = SolverRunner()
        input_data = SolverInput(case_dir="/nonexistent/path")

        with pytest.raises(FileNotFoundError):
            runner.prepare_case(input_data)

    def test_prepare_case_valid_structure(self):
        """Test prepare_case with valid case structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create OpenFOAM case structure
            case_dir = Path(tmpdir) / "case"
            case_dir.mkdir()
            (case_dir / "constant").mkdir()
            mesh_dir = case_dir / "constant" / "polyMesh"
            mesh_dir.mkdir()
            (mesh_dir / "points").touch()
            (mesh_dir / "faces").touch()

            runner = SolverRunner()
            input_data = SolverInput(
                case_dir=str(case_dir),
                mesh_dir=str(mesh_dir),
            )

            steps = runner.prepare_case(input_data)
            assert len(steps) >= 2
            assert any("Mesh files validated" in s for s in steps)

    def test_build_command_openfoam(self):
        """Test building OpenFOAM command"""
        runner = SolverRunner()
        config = SolverConfig(
            solver_type=SolverType.OPENFOAM,
            executable_path="simpleFoam",
        )
        input_data = SolverInput(
            case_dir="/tmp/test",
            solver_config=config,
        )

        cmd = runner.build_command(input_data)
        assert "simpleFoam" in cmd
        assert "-case" in cmd
        assert "/tmp/test" in cmd

    def test_build_command_openfoam_parallel(self):
        """Test building parallel OpenFOAM command"""
        runner = SolverRunner()
        config = SolverConfig(
            solver_type=SolverType.OPENFOAM,
            executable_path="simpleFoam",
            parallel=True,
            n_procs=4,
        )
        input_data = SolverInput(
            case_dir="/tmp/test",
            solver_config=config,
        )

        cmd = runner.build_command(input_data)
        assert "mpirun" in cmd
        assert "-np" in cmd
        assert "4" in cmd
        assert "simpleFoam" in cmd

    def test_build_command_su2(self):
        """Test building SU2 command"""
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir)
            config_file = case_dir / "config.cfg"
            config_file.touch()

            runner = SolverRunner()
            config = SolverConfig(
                solver_type=SolverType.SU2,
                executable_path="SU2_CFD",
            )
            input_data = SolverInput(
                case_dir=str(case_dir),
                solver_config=config,
            )

            cmd = runner.build_command(input_data)
            assert "SU2_CFD" in cmd
            assert str(config_file) in cmd

    def test_launch_without_input(self):
        """Test launching job without input"""
        runner = SolverRunner()
        job = SolverJob()

        with pytest.raises(ValueError, match="Job input not provided"):
            runner.launch(job)

    def test_launch_invalid_case(self):
        """Test launching job with invalid case"""
        runner = SolverRunner()
        config = SolverConfig(
            solver_type=SolverType.OPENFOAM,
            executable_path="simpleFoam",
        )
        input_data = SolverInput(
            case_dir="/nonexistent",
            solver_config=config,
        )
        job = SolverJob(input=input_data)

        with pytest.raises(FileNotFoundError):
            runner.launch(job)

    def test_get_status_no_job(self):
        """Test get_status for non-existent job"""
        runner = SolverRunner()
        status = runner.get_status("nonexistent")
        assert status is None

    def test_get_running_jobs_empty(self):
        """Test get_running_jobs when no jobs running"""
        runner = SolverRunner()
        jobs = runner.get_running_jobs()
        assert jobs == []

    def test_cancel_nonexistent_job(self):
        """Test canceling non-existent job"""
        runner = SolverRunner()
        result = runner.cancel("nonexistent")
        assert result is False


class TestSolverJob:
    """Test SolverJob"""

    def test_job_creation(self):
        """Test job creation"""
        job = SolverJob()
        assert job.job_id.startswith("SOLVER-")
        assert job.status == SolverStatus.PENDING
        assert job.result is None
        assert job.priority == JobPriority.MEDIUM

    def test_job_start(self):
        """Test starting a job"""
        job = SolverJob()
        job.start()

        assert job.status == SolverStatus.RUNNING
        assert job.result is not None
        assert job.result.status == SolverStatus.RUNNING

    def test_job_complete_success(self):
        """Test completing a job successfully"""
        job = SolverJob()
        job.start()

        job.complete(exit_code=0, stdout="Success", stderr="")

        assert job.status == SolverStatus.COMPLETED
        assert job.result.exit_code == 0
        assert job.result.stdout == "Success"
        assert job.result.is_success()

    def test_job_complete_failure(self):
        """Test completing a job with failure"""
        job = SolverJob()
        job.start()

        job.complete(exit_code=1, stdout="", stderr="Error occurred")

        assert job.status == SolverStatus.FAILED
        assert job.result.exit_code == 1
        assert not job.result.is_success()

    def test_job_fail(self):
        """Test failing a job"""
        job = SolverJob()
        job.start()

        job.fail("Test failure")

        assert job.status == SolverStatus.FAILED
        assert job.result.error_message == "Test failure"

    def test_job_runtime(self):
        """Test job runtime calculation"""
        job = SolverJob()
        job.start()
        time.sleep(0.1)  # Small delay
        job.complete(exit_code=0)

        assert job.result.runtime_seconds >= 0.1


class TestBatchSolverRunner:
    """Test BatchSolverRunner"""

    def test_batch_init(self):
        """Test batch runner initialization"""
        batch = BatchSolverRunner(max_concurrent=2)
        assert batch.max_concurrent == 2
        assert batch._queue == []
        assert batch._running == {}

    def test_batch_submit(self):
        """Test submitting jobs to batch"""
        batch = BatchSolverRunner()
        job = SolverJob()
        batch.submit(job)

        assert len(batch._queue) == 1
        assert batch._queue[0] == job

    def test_batch_get_progress(self):
        """Test getting batch progress"""
        batch = BatchSolverRunner()

        # Submit some jobs
        for i in range(3):
            batch.submit(SolverJob())

        progress = batch.get_progress()
        assert progress["total"] == 3
        assert progress["pending"] == 3
        assert progress["running"] == 0

    def test_batch_run_all_empty(self):
        """Test running batch with no jobs"""
        batch = BatchSolverRunner()
        results = batch.run_all()
        assert results == []

    def test_batch_max_concurrent(self):
        """Test batch runner respects max concurrent"""
        batch = BatchSolverRunner(max_concurrent=2)

        # Submit more jobs than max_concurrent
        for i in range(5):
            batch.submit(SolverJob())

        assert batch.max_concurrent == 2


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_create_solver_job(self):
        """Test create_solver_job function"""
        from knowledge_compiler.phase3.schema import create_solver_job

        job = create_solver_job(
            case_dir="/tmp/test",
            solver_type=SolverType.OPENFOAM,
            priority=JobPriority.HIGH,
        )

        assert job.input is not None
        assert job.input.case_dir == "/tmp/test"
        assert job.input.solver_config is not None
        assert job.input.solver_config.solver_type == SolverType.OPENFOAM
        assert job.priority == JobPriority.HIGH

    def test_get_solver_executable(self):
        """Test get_solver_executable function"""
        from knowledge_compiler.phase3.schema import get_solver_executable

        openfoam_cmd = get_solver_executable(SolverType.OPENFOAM)
        assert openfoam_cmd == "simpleFoam"

        su2_cmd = get_solver_executable(SolverType.SU2)
        assert su2_cmd == "SU2_CFD"

    def test_run_solver_missing_case(self):
        """Test run_solver with missing case"""
        with pytest.raises(FileNotFoundError):
            run_solver(case_dir="/nonexistent")


class TestSolverConfig:
    """Test SolverConfig"""

    def test_config_defaults(self):
        """Test config default values"""
        config = SolverConfig(
            solver_type=SolverType.OPENFOAM,
            executable_path="simpleFoam",
        )

        assert config.version == ""
        assert config.parallel is False
        assert config.n_procs == 1
        assert config.additional_args == {}


class TestSolverInput:
    """Test SolverInput"""

    def test_input_defaults(self):
        """Test input default values"""
        input_data = SolverInput(
            case_dir="/tmp/test",
            mesh_dir="/tmp/test/constant/polyMesh",
        )

        assert input_data.boundary_conditions == []
        assert input_data.solver_config is None
        assert input_data.control_dict == {}

    def test_input_with_solver_config(self):
        """Test input with solver config"""
        config = SolverConfig(
            solver_type=SolverType.OPENFOAM,
            executable_path="simpleFoam",
        )
        input_data = SolverInput(
            case_dir="/tmp/test",
            mesh_dir="/tmp/test/constant/polyMesh",
            solver_config=config,
        )

        assert input_data.solver_config == config


class TestBoundaryCondition:
    """Test BoundaryCondition"""

    def test_boundary_condition_creation(self):
        """Test creating boundary condition"""
        bc = BoundaryCondition(
            name="inlet",
            type="inlet",
            values={"velocity": "(10 0 0)", "pressure": 0},
        )

        assert bc.name == "inlet"
        assert bc.type == "inlet"
        assert bc.values["velocity"] == "(10 0 0)"
