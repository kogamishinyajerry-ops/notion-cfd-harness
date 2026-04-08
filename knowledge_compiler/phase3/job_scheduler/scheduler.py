#!/usr/bin/env python3
"""
Phase 3: Job Scheduler

管理 CFD 作业的优先级调度、依赖解析和并发控制。

核心组件:
- JobScheduler: 单作业调度器（优先级队列 + 依赖解析）
- BatchJobScheduler: 批量并发调度器
- 便捷函数: create_scheduled_job, schedule_from_solver_jobs
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from knowledge_compiler.phase3.schema import (
    JobPriority,
    ScheduledJob,
    SchedulerState,
    SolverJob,
    SolverStatus,
)

logger = logging.getLogger(__name__)


# 优先级数值映射（越高越优先）
_PRIORITY_ORDER = {
    JobPriority.CRITICAL: 4,
    JobPriority.HIGH: 3,
    JobPriority.MEDIUM: 2,
    JobPriority.LOW: 1,
}


class JobScheduler:
    """作业调度器

    管理作业的提交、优先级排序、依赖解析和状态跟踪。

    调度策略:
    1. 只调度依赖已满足的作业
    2. CRITICAL > HIGH > MEDIUM > LOW
    3. 同优先级按提交顺序（FIFO）
    4. 受 max_concurrent 并发限制

    并发安全:
    - 非线程安全：内部使用 OrderedDict 和 list，无锁保护
    - 单线程设计：适用于单进程 CFD 工作流编排
    - 多线程场景需外部加锁或使用线程安全包装器
    """

    def __init__(self, max_concurrent: int = 2):
        self._state = SchedulerState(max_concurrent=max_concurrent)
        self._jobs: OrderedDict[str, ScheduledJob] = OrderedDict()
        self._results: Dict[str, Dict[str, Any]] = {}

    @property
    def state(self) -> SchedulerState:
        return self._state

    def submit(self, job: ScheduledJob) -> None:
        """提交作业到调度队列

        Args:
            job: 已调度的作业

        Raises:
            ValueError: 重复 job_id
        """
        if job.job_id in self._jobs:
            raise ValueError(f"重复的 job_id: {job.job_id}")

        job.scheduled_at = time.time()
        self._jobs[job.job_id] = job
        self._state.pending_jobs.append(job.job_id)
        logger.info("作业已提交: %s (priority=%s)", job.job_id, job.priority.value)

    def schedule_next(self) -> Optional[ScheduledJob]:
        """调度下一个可执行作业

        Returns:
            下一个可执行的作业，或 None（无可调度作业）
        """
        if not self._state.can_schedule():
            return None

        # 从待执行队列中找到优先级最高且依赖已满足的作业
        candidates = []
        for job_id in self._state.pending_jobs:
            job = self._jobs[job_id]
            if self._dependencies_met(job):
                candidates.append(job)

        if not candidates:
            return None

        # 按优先级排序（降序），同优先级保持 FIFO
        candidates.sort(key=lambda j: _PRIORITY_ORDER[j.priority], reverse=True)

        selected = candidates[0]
        return selected

    def mark_started(self, job_id: str) -> None:
        """标记作业为运行中

        Args:
            job_id: 作业 ID

        Raises:
            KeyError: 作业不存在
        """
        if job_id not in self._jobs:
            raise KeyError(f"未知 job_id: {job_id}")

        job = self._jobs[job_id]
        job.status = SolverStatus.RUNNING
        job.started_at = time.time()

        self._state.pending_jobs.remove(job_id)
        self._state.running_jobs.append(job_id)
        logger.info("作业已启动: %s", job_id)

    def mark_completed(self, job_id: str, success: bool = True) -> None:
        """标记作业为已完成

        Args:
            job_id: 作业 ID
            success: 是否成功

        Raises:
            KeyError: 作业不存在
        """
        if job_id not in self._jobs:
            raise KeyError(f"未知 job_id: {job_id}")

        job = self._jobs[job_id]
        job.status = SolverStatus.COMPLETED if success else SolverStatus.FAILED

        if job_id in self._state.running_jobs:
            self._state.running_jobs.remove(job_id)

        if success:
            self._state.completed_jobs.append(job_id)
            logger.info("作业完成: %s", job_id)
        else:
            self._state.failed_jobs.append(job_id)
            logger.warning("作业失败: %s", job_id)

    def cancel(self, job_id: str) -> bool:
        """取消待执行作业

        Args:
            job_id: 作业 ID

        Returns:
            是否成功取消（运行中的作业不可取消）
        """
        if job_id not in self._jobs:
            return False

        if job_id in self._state.running_jobs:
            return False  # 运行中不可取消

        if job_id in self._state.pending_jobs:
            self._state.pending_jobs.remove(job_id)
            job = self._jobs[job_id]
            job.status = SolverStatus.CANCELLED
            self._state.failed_jobs.append(job_id)
            logger.info("作业已取消: %s", job_id)
            return True

        return False

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """获取作业信息"""
        return self._jobs.get(job_id)

    def get_pending_count(self) -> int:
        """待执行作业数"""
        return len(self._state.pending_jobs)

    def is_done(self) -> bool:
        """所有作业是否完成"""
        return (
            len(self._state.pending_jobs) == 0
            and len(self._state.running_jobs) == 0
        )

    def _dependencies_met(self, job: ScheduledJob) -> bool:
        """检查作业的所有依赖是否已完成"""
        if not job.dependencies:
            return True
        return all(dep in self._state.completed_jobs for dep in job.dependencies)


class BatchJobScheduler:
    """批量并发调度器

    管理一批作业的并发执行，支持进度查询和结果汇总。
    """

    def __init__(self, max_concurrent: int = 2):
        self._scheduler = JobScheduler(max_concurrent=max_concurrent)

    @property
    def state(self) -> SchedulerState:
        return self._scheduler.state

    def submit_batch(self, jobs: List[ScheduledJob]) -> int:
        """批量提交作业

        Args:
            jobs: 作业列表

        Returns:
            成功提交的作业数
        """
        count = 0
        for job in jobs:
            try:
                self._scheduler.submit(job)
                count += 1
            except ValueError:
                logger.warning("跳过重复作业: %s", job.job_id)
        logger.info("批量提交完成: %d/%d", count, len(jobs))
        return count

    def schedule_ready(self) -> List[ScheduledJob]:
        """返回所有当前可执行的作业

        在 max_concurrent 限制内，返回所有可调度的作业。
        调用者需手动 mark_started。
        """
        ready = []
        while self._scheduler.state.can_schedule():
            job = self._scheduler.schedule_next()
            if job is None:
                break
            ready.append(job)
            # 预占并发槽位
            self._scheduler.state.running_jobs.append(job.job_id)
            self._scheduler.state.pending_jobs.remove(job.job_id)
        return ready

    def get_progress(self) -> Dict[str, int]:
        """获取进度摘要"""
        state = self._scheduler.state
        return {
            "pending": len(state.pending_jobs),
            "running": len(state.running_jobs),
            "completed": len(state.completed_jobs),
            "failed": len(state.failed_jobs),
            "total": (
                len(state.pending_jobs)
                + len(state.running_jobs)
                + len(state.completed_jobs)
                + len(state.failed_jobs)
            ),
        }

    def run_all(
        self,
        executor: Callable[[ScheduledJob], bool],
        poll_interval: float = 0.1,
    ) -> Dict[str, Any]:
        """阻塞式批量执行所有作业

        Args:
            executor: 作业执行函数，返回是否成功
            poll_interval: 调度间隔（秒）

        Returns:
            执行结果摘要
        """
        results: Dict[str, Any] = {
            "completed": [],
            "failed": [],
            "cancelled": [],
            "total_time": 0.0,
        }
        start_time = time.time()

        while not self._scheduler.is_done():
            # 调度新作业
            job = self._scheduler.schedule_next()
            if job is None:
                # 没有可调度的作业但还有 pending（依赖未满足）→ 死锁检测
                if self._scheduler.get_pending_count() > 0:
                    logger.error("检测到死锁: 待执行作业依赖无法满足")
                    for jid in list(self._scheduler.state.pending_jobs):
                        self._scheduler.cancel(jid)
                        results["cancelled"].append(jid)
                    break
                break  # No more work

            self._scheduler.mark_started(job.job_id)
            try:
                success = executor(job)
                self._scheduler.mark_completed(job.job_id, success)
                if success:
                    results["completed"].append(job.job_id)
                else:
                    results["failed"].append(job.job_id)
            except Exception as e:
                logger.error("作业执行异常: %s - %s", job.job_id, e)
                self._scheduler.mark_completed(job.job_id, success=False)
                results["failed"].append(job.job_id)

        results["total_time"] = time.time() - start_time
        results["success_rate"] = (
            len(results["completed"])
            / max(1, len(results["completed"]) + len(results["failed"]))
        )

        logger.info(
            "批量调度完成: %d 成功, %d 失败, %.1fs",
            len(results["completed"]),
            len(results["failed"]),
            results["total_time"],
        )
        return results


# ============================================================================
# Convenience Functions
# ============================================================================

def create_scheduled_job(
    job_id: str,
    priority: JobPriority = JobPriority.MEDIUM,
    estimated_duration: float = 0.0,
    dependencies: Optional[List[str]] = None,
    resource_requirements: Optional[Dict[str, Any]] = None,
) -> ScheduledJob:
    """创建调度作业的便捷函数"""
    return ScheduledJob(
        job_id=job_id,
        priority=priority,
        estimated_duration=estimated_duration,
        dependencies=dependencies or [],
        resource_requirements=resource_requirements or {},
    )


def schedule_from_solver_jobs(
    solver_jobs: List[SolverJob],
) -> List[ScheduledJob]:
    """从 SolverJob 列表创建 ScheduledJob 列表

    保持原有优先级映射，作业之间无依赖。
    """
    scheduled = []
    for sj in solver_jobs:
        priority = _map_solver_priority(sj)
        scheduled.append(
            ScheduledJob(
                job_id=sj.job_id,
                priority=priority,
                estimated_duration=0.0,
                dependencies=[],
            )
        )
    return scheduled


def _map_solver_priority(solver_job: SolverJob) -> JobPriority:
    """将 SolverJob 的优先级映射到 JobPriority"""
    # SolverJob 使用字符串优先级
    priority_str = getattr(solver_job, "priority", "medium")
    mapping = {
        "critical": JobPriority.CRITICAL,
        "high": JobPriority.HIGH,
        "medium": JobPriority.MEDIUM,
        "low": JobPriority.LOW,
    }
    return mapping.get(str(priority_str).lower(), JobPriority.MEDIUM)
