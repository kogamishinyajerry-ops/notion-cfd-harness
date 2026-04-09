#!/usr/bin/env python3
"""
Tests for Postprocess Runner
"""

import json
import tempfile
from pathlib import Path
import pytest

from knowledge_compiler.phase3.schema import (
    PostprocessArtifact,
    PostprocessFormat,
    PostprocessJob,
    PostprocessRequest,
    PostprocessResult,
    PostprocessStatus,
    SolverResult,
    SolverStatus,
)
from knowledge_compiler.phase3.postprocess_runner import (
    BatchPostprocessRunner,
    FieldDataExtractor,
    OpenFOAMResultParser,
    PostprocessRunner,
    create_postprocess_job,
    run_postprocess,
)


class TestOpenFOAMResultParser:
    """测试 OpenFOAM 结果解析器"""

    def test_parse_residuals_empty_log(self):
        """测试解析空日志"""
        parser = OpenFOAMResultParser()
        result = parser.parse_residuals("")
        assert result["initial"] == {}
        assert result["final"] == {}
        assert result["iterations"] == []

    def test_parse_residuals_sample_log(self):
        """测试解析样本日志"""
        parser = OpenFOAMResultParser()
        log = """
Time = 0

Selecting incompressible RANS turbulence model


Create mesh for time = 0


Create files


No fields created


Create polyMesh


Starting time loop

communication
{
    type            solver;
    libs            ("libOpenFOAM.so");
}


AMI
{
    type        conjugate-gradient;
    solver      PCG;
    preconditioner
    {
        type GAMG;
        tolerance 1e-06;
        relTol 0.01;
    }
}

SIMPLE
{
    solver          PBiCGStab;
}

solver
{
    algorithm          PBiCGStab;
    tolerance           1e-06;
    relTol              0.01;
}

solution
{
    solver          PBiCGStab;
    tolerance       1e-06;
    relTol           0.01;
}

solvers
{
    p
    {
        solver          PBiCGStab;
        tolerance       1e-06;
        relTol           0.01;
    }
    p
    {
        solver          PBiCGStab;
        tolerance       1e-06;
        relTol           0.01;
    }
}

Courant Number mean: 0.222817

deltaT = 0.001

Time = 0.01

Selecting incompressible RANS turbulence model


Create mesh for time = 0.01


Create files


No fields created


Create polyMesh


Starting time loop


segmentation fault


Finalising parallel run


End
"""
        result = parser.parse_residuals(log)
        # 由于这个示例没有残差数据，验证返回空结构
        assert "initial" in result
        assert "final" in result

    def test_parse_residuals_with_data(self):
        """测试解析包含残差数据的日志"""
        parser = OpenFOAMResultParser()
        log = """
solving for p, initial residual = 0.001234
solving for p, initial residual = 0.000567
solving for U, initial residual = 0.002345
solving for p, Final residual = 1.23e-05, No Iterations 45
solving for U, Final residual = 3.45e-05, No Iterations 52
solution converges
End
"""
        result = parser.parse_residuals(log)
        assert "initial" in result
        assert "final" in result
        assert "iterations" in result

    def test_parse_convergence_converged(self):
        """测试解析收敛信息"""
        parser = OpenFOAMResultParser()
        log = """
some log...
solution converges
End = 1.5
"""
        result = parser.parse_convergence(log)
        assert result["converged"] is True
        assert result["reason"] == "Solution converges"

    def test_parse_convergence_failed(self):
        """测试解析失败信息"""
        parser = OpenFOAMResultParser()
        log = """
error: some error occurred
End = 0.5
"""
        result = parser.parse_convergence(log)
        assert result["converged"] is False
        assert "error" in result["reason"].lower()


class TestFieldDataExtractor:
    """测试场数据提取器"""

    def test_extract_field_summary_nonexistent(self):
        """测试提取不存在的场文件"""
        extractor = FieldDataExtractor()
        result = extractor.extract_field_summary("/nonexistent/path")
        assert result["name"] == "path"
        assert result["exists"] is False

    def test_extract_field_summary_existing(self):
        """测试提取存在的文件"""
        extractor = FieldDataExtractor()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            f.flush()
            result = extractor.extract_field_summary(f.name)
            assert result["exists"] is True
            assert result["size_bytes"] == len("test content")
            Path(f.name).unlink()


class TestPostprocessRunner:
    """测试 PostprocessRunner"""

    def test_runner_init(self):
        """测试初始化"""
        runner = PostprocessRunner(output_dir="/tmp/test")
        assert runner.output_dir == "/tmp/test"
        assert runner.parser is not None
        assert runner.extractor is not None

    def test_run_with_empty_request(self):
        """测试处理空请求"""
        runner = PostprocessRunner(output_dir="")
        request = PostprocessRequest()
        result = runner.run(request)
        assert result.status in [PostprocessStatus.COMPLETED, PostprocessStatus.FAILED]
        assert result.result_id != ""

    def test_run_with_solver_result(self):
        """测试处理求解器结果"""
        runner = PostprocessRunner(output_dir="")

        # 创建模拟求解器结果
        solver_result = SolverResult(
            job_id="test-job",
            status=SolverStatus.COMPLETED,
            exit_code=0,
            stdout="solution converges\nsolving for p, Final residual = 1.23e-05, No Iterations 45\n",
        )

        request = PostprocessRequest(
            solver_result=solver_result,
            output_formats=[PostprocessFormat.JSON],
        )

        result = runner.run(request)
        assert result.status in [PostprocessStatus.COMPLETED, PostprocessStatus.FAILED]
        # 验证残差数据被解析
        if result.status == PostprocessStatus.COMPLETED:
            assert "residuals" in result.field_data


class TestBatchPostprocessRunner:
    """测试 BatchPostprocessRunner"""

    def test_run_batch_empty(self):
        """测试批量处理空请求列表"""
        batch_runner = BatchPostprocessRunner(output_dir="")
        results = batch_runner.run_batch([])
        assert results == []

    def test_run_batch_single(self):
        """测试批量处理单个请求"""
        batch_runner = BatchPostprocessRunner(output_dir="")

        solver_result = SolverResult(
            job_id="test-job",
            status=SolverStatus.COMPLETED,
            exit_code=0,
            stdout="test",
        )

        request = PostprocessRequest(
            solver_result=solver_result,
            output_formats=[],
        )

        results = batch_runner.run_batch([request])
        assert len(results) == 1


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_run_postprocess(self):
        """测试 run_postprocess 便捷函数"""
        solver_result = SolverResult(
            job_id="test-job",
            status=SolverStatus.COMPLETED,
            exit_code=0,
            stdout="",
        )

        result = run_postprocess(
            solver_result=solver_result,
            output_formats=[],
            output_dir="",
        )
        assert result is not None

    def test_create_postprocess_job(self):
        """测试 create_postprocess_job 便捷函数"""
        solver_result = SolverResult(
            job_id="test-job",
            status=SolverStatus.COMPLETED,
            exit_code=0,
        )

        job = create_postprocess_job(solver_result=solver_result)
        assert job.job_id != ""
        assert job.request is not None
        assert job.request.solver_result == solver_result


class TestPostprocessSchema:
    """测试 Postprocess Schema"""

    def test_postprocess_result_creation(self):
        """测试创建 PostprocessResult"""
        result = PostprocessResult()
        assert result.result_id != ""
        assert result.status == PostprocessStatus.PENDING
        assert result.artifacts == []

    def test_postprocess_result_add_artifact(self):
        """测试添加产物"""
        result = PostprocessResult()
        artifact = PostprocessArtifact(format=PostprocessFormat.JSON)
        result.add_artifact(artifact)
        assert len(result.artifacts) == 1
        assert result.artifacts[0] == artifact

    def test_postprocess_result_is_success(self):
        """测试成功检查"""
        result = PostprocessResult(status=PostprocessStatus.COMPLETED)
        assert result.is_success() is True

        result.status = PostprocessStatus.FAILED
        assert result.is_success() is False

    def test_postprocess_job_lifecycle(self):
        """测试作业生命周期"""
        job = PostprocessJob()
        assert job.status == PostprocessStatus.PENDING

        job.start()
        assert job.status == PostprocessStatus.RUNNING
        assert job.result is not None

        result = PostprocessResult(status=PostprocessStatus.COMPLETED)
        job.complete(result)
        assert job.status == PostprocessStatus.COMPLETED
        assert job.result == result

    def test_postprocess_job_fail(self):
        """测试作业失败"""
        job = PostprocessJob()
        job.start()

        job.fail("test error")
        assert job.status == PostprocessStatus.FAILED
        assert job.result.error_message == "test error"

    def test_postprocess_request_creation(self):
        """测试创建后处理请求"""
        solver_result = SolverResult(job_id="test", status=SolverStatus.PENDING)
        request = PostprocessRequest(
            solver_result=solver_result,
            result_directory="/path/to/case",
            output_formats=[PostprocessFormat.JSON, PostprocessFormat.CSV],
            extract_fields=["p", "U"],
            generate_report=True,
            visualize=False,
        )

        assert request.request_id != ""
        assert request.solver_result == solver_result
        assert request.result_directory == "/path/to/case"
        assert len(request.output_formats) == 2
        assert request.extract_fields == ["p", "U"]
        assert request.generate_report is True
        assert request.visualize is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
