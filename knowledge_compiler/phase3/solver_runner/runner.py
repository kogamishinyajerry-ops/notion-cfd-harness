#!/usr/bin/env python3
"""
Phase 3 Solver Runner: 求解器调度器

负责启动、监控和管理 CFD 求解器进程。
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_compiler.phase3.schema import (
    SolverType,
    SolverStatus,
    SolverJob,
    SolverInput,
    SolverResult,
    SolverConfig,
    JobPriority,
)


class SolverRunner:
    """
    求解器运行器

    管理求解器进程的生命周期。
    """

    def __init__(self, workspace: Optional[str] = None):
        """
        Initialize the solver runner

        Args:
            workspace: 工作目录，默认为当前目录
        """
        self.workspace = workspace or os.getcwd()
        self._running_jobs: Dict[str, subprocess.Popen] = {}
        self._job_threads: Dict[str, threading.Thread] = {}

    def prepare_case(self, input_data: SolverInput) -> List[str]:
        """
        准备求解器输入

        Args:
            input_data: 求解器输入数据

        Returns:
            准备步骤列表（用于验证）
        """
        steps = []

        # 检查 case 目录
        case_dir = Path(input_data.case_dir)
        if not case_dir.exists():
            raise FileNotFoundError(f"Case directory not found: {input_data.case_dir}")

        steps.append(f"Case directory found: {input_data.case_dir}")

        # 检查网格目录
        mesh_dir = Path(input_data.mesh_dir)
        if not mesh_dir.exists():
            raise FileNotFoundError(f"Mesh directory not found: {input_data.mesh_dir}")

        steps.append(f"Mesh directory found: {input_data.mesh_dir}")

        # 验证网格文件
        mesh_files = list(mesh_dir.glob("points")) + list(mesh_dir.glob("faces"))
        if not mesh_files:
            raise ValueError("No valid mesh files found")

        steps.append(f"Mesh files validated: {len(mesh_files)} files")

        return steps

    def build_command(
        self,
        input_data: SolverInput,
    ) -> List[str]:
        """
        构建求解器命令

        Args:
            input_data: 求解器输入数据

        Returns:
            命令列表
        """
        config = input_data.solver_config
        if not config:
            raise ValueError("Solver config not provided")

        solver_type = config.solver_type

        if solver_type == SolverType.OPENFOAM:
            cmd = [config.executable_path]
            if config.parallel and config.n_procs > 1:
                cmd = ["mpirun", "-np", str(config.n_procs)] + cmd
            cmd.append("-case")
            cmd.append(input_data.case_dir)

        elif solver_type == SolverType.SU2:
            cmd = [config.executable_path]
            config_file = Path(input_data.case_dir) / "config.cfg"
            if not config_file.exists():
                config_file = Path(input_data.case_dir) / "config.cfg"
            cmd.append(str(config_file))

        else:
            raise ValueError(f"Unsupported solver type: {solver_type}")

        return cmd

    def launch(self, job: SolverJob) -> None:
        """
        启动求解器作业

        Args:
            job: 求解器作业
        """
        if job.input is None:
            raise ValueError("Job input not provided")

        # 准备 case
        self.prepare_case(job.input)

        # 构建命令
        cmd = self.build_command(job.input)

        # 启动进程
        job.start()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.workspace,
            text=True,
        )

        self._running_jobs[job.job_id] = process

        # 启动监控线程
        thread = threading.Thread(
            target=self._monitor_job,
            args=(job, process),
            daemon=True,
        )
        thread.start()
        self._job_threads[job.job_id] = thread

    def _monitor_job(
        self,
        job: SolverJob,
        process: subprocess.Popen,
    ) -> None:
        """
        监控作业执行

        Args:
            job: 求解器作业
            process: 子进程
        """
        try:
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                job.complete(
                    exit_code=0,
                    stdout=stdout,
                    stderr=stderr,
                )
            else:
                job.fail(
                    error=f"Solver failed with exit code {process.returncode}: {stderr[:200]}"
                )

        except Exception as e:
            job.fail(error=f"Job monitoring failed: {str(e)}")

        finally:
            self._running_jobs.pop(job.job_id, None)

    def wait(self, job: SolverJob, timeout: Optional[float] = None) -> SolverResult:
        """
        等待作业完成

        Args:
            job: 求解器作业
            timeout: 超时时间（秒）

        Returns:
            求解器结果
        """
        start_time = time.time()

        while job.status == SolverStatus.RUNNING:
            if timeout and (time.time() - start_time) > timeout:
                self.cancel(job.job_id)
                raise TimeoutError(f"Job {job.job_id} timed out after {timeout}s")

            time.sleep(0.5)

        if job.result is None:
            raise RuntimeError(f"Job {job.job_id} completed without result")

        return job.result

    def cancel(self, job_id: str) -> bool:
        """
        取消作业

        Args:
            job_id: 作业 ID

        Returns:
            是否成功取消
        """
        process = self._running_jobs.get(job_id)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

            return True

        return False

    def get_status(self, job_id: str) -> Optional[SolverStatus]:
        """
        获取作业状态

        Args:
            job_id: 作业 ID

        Returns:
            求解器状态
        """
        process = self._running_jobs.get(job_id)
        if process and process.poll() is None:
            return SolverStatus.RUNNING

        return None

    def get_running_jobs(self) -> List[str]:
        """
        获取正在运行的作业列表

        Returns:
            作业 ID 列表
        """
        return list(self._running_jobs.keys())


class BatchSolverRunner:
    """
    批量求解器运行器

    管理多个求解器作业的并发执行。
    """

    def __init__(
        self,
        workspace: Optional[str] = None,
        max_concurrent: int = 2,
    ):
        """
        Initialize the batch runner

        Args:
            workspace: 工作目录
            max_concurrent: 最大并发数
        """
        self.runner = SolverRunner(workspace)
        self.max_concurrent = max_concurrent
        self._queue: List[SolverJob] = []
        self._running: Dict[str, SolverJob] = {}

    def submit(self, job: SolverJob) -> None:
        """
        提交作业

        Args:
            job: 求解器作业
        """
        self._queue.append(job)

    def run_all(self) -> List[SolverResult]:
        """
        运行所有作业

        Returns:
            求解器结果列表
        """
        results = []

        while self._queue or self._running:
            # 启动新作业
            while self._queue and len(self._running) < self.max_concurrent:
                job = self._queue.pop(0)
                self.runner.launch(job)
                self._running[job.job_id] = job

            # 等待任一作业完成
            if self._running:
                time.sleep(0.5)

                # 检查完成的作业
                completed = []
                for job_id, job in self._running.items():
                    if job.status != SolverStatus.RUNNING:
                        completed.append(job_id)
                        if job.result:
                            results.append(job.result)

                # 移除完成的作业
                for job_id in completed:
                    self._running.pop(job_id, None)

        return results

    def get_progress(self) -> Dict[str, Any]:
        """
        获取进度

        Returns:
            进度信息
        """
        return {
            "total": len(self._queue) + len(self._running),
            "pending": len(self._queue),
            "running": len(self._running),
            "completed": len(self._running) - sum(
                1 for j in self._running.values()
                if j.status == SolverStatus.RUNNING
            ),
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def run_solver(
    case_dir: str,
    solver_type: SolverType = SolverType.OPENFOAM,
    timeout: Optional[float] = None,
) -> SolverResult:
    """
    便捷函数：运行单个求解器

    Args:
        case_dir: Case 目录
        solver_type: 求解器类型
        timeout: 超时时间

    Returns:
        求解器结果
    """
    from knowledge_compiler.phase3.schema import create_solver_job

    job = create_solver_job(case_dir, solver_type)
    runner = SolverRunner()
    runner.launch(job)
    return runner.wait(job, timeout=timeout)


def run_solvers_batch(
    case_dirs: List[str],
    solver_type: SolverType = SolverType.OPENFOAM,
    max_concurrent: int = 2,
) -> List[SolverResult]:
    """
    便捷函数：批量运行求解器

    Args:
        case_dirs: Case 目录列表
        solver_type: 求解器类型
        max_concurrent: 最大并发数

    Returns:
        求解器结果列表
    """
    from knowledge_compiler.phase3.schema import create_solver_job

    batch = BatchSolverRunner(max_concurrent=max_concurrent)

    for case_dir in case_dirs:
        job = create_solver_job(case_dir, solver_type)
        batch.submit(job)

    return batch.run_all()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "SolverRunner",
    "BatchSolverRunner",
    "run_solver",
    "run_solvers_batch",
]
