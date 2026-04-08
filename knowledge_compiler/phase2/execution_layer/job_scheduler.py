#!/usr/bin/env python3
"""
Job Scheduler - 作业调度器

管理求解器作业队列，支持优先级调度、依赖管理、并发控制。
对应 G4 运行 Gate 的调度核心。
"""

from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from queue import Empty, Queue


class JobStatus(Enum):
    """作业状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"  # 等待依赖完成


class JobPriority(Enum):
    """作业优先级"""
    CRITICAL = 0  # 最高优先级
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True)
class ScheduledJob:
    """调度的作业"""
    # 优先级用于排序（越小越优先）
    priority: int = field(compare=True, default=JobPriority.NORMAL.value)
    # 提交时间用于 FIFO（同等优先级时）
    submit_time: float = field(compare=True, default_factory=time.time)

    # 作业数据（不参与比较）
    job_id: str = field(compare=False, default="")
    job_type: str = field(compare=False, default="")
    status: JobStatus = field(compare=False, default=JobStatus.PENDING)
    dependencies: List[str] = field(compare=False, default_factory=list)
    dependents: List[str] = field(compare=False, default_factory=list)

    # 任务数据
    task_func: Optional[Callable] = field(compare=False, default=None)
    task_args: tuple = field(compare=False, default_factory=tuple)
    task_kwargs: Dict[str, Any] = field(compare=False, default_factory=dict)

    # 结果
    result: Any = field(compare=False, default=None)
    error: Optional[Exception] = field(compare=False, default=None)

    # 元数据
    created_at: float = field(compare=False, default_factory=time.time)
    started_at: float = field(compare=False, default=0)
    completed_at: float = field(compare=False, default=0)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)

    @property
    def duration(self) -> float:
        """执行时长"""
        if self.started_at > 0:
            end = self.completed_at if self.completed_at > 0 else time.time()
            return end - self.started_at
        return 0.0

    @property
    def is_finished(self) -> bool:
        """是否已完成（成功或失败）"""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]

    @property
    def can_run(self) -> bool:
        """是否可以运行"""
        return (
            self.status == JobStatus.PENDING and
            not self.dependencies
        )

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status.value,
            "priority": self.priority,
            "duration": self.duration,
            "retry_count": self.retry_count,
            "has_result": self.result is not None,
            "has_error": self.error is not None,
        }


@dataclass
class SchedulerState:
    """调度器状态"""
    is_running: bool = False
    is_paused: bool = False
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    running_jobs: int = 0
    queued_jobs: int = 0

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.completed_jobs == 0:
            return 0.0
        return (self.completed_jobs - self.failed_jobs) / max(self.completed_jobs, 1)


class WorkerThread(threading.Thread):
    """工作线程"""

    def __init__(
        self,
        worker_id: int,
        job_queue: Queue,
        result_callback: Callable[[ScheduledJob], None],
    ):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.job_queue = job_queue
        self.result_callback = result_callback
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """停止工作线程"""
        self._stop_event.set()

    def run(self) -> None:
        """运行工作线程"""
        while not self._stop_event.is_set():
            try:
                job = self.job_queue.get(timeout=0.1)
                if job is None:
                    break

                job.status = JobStatus.RUNNING
                job.started_at = time.time()

                try:
                    if job.task_func:
                        result = job.task_func(*job.task_args, **job.task_kwargs)
                        job.result = result
                        job.status = JobStatus.COMPLETED
                    else:
                        job.status = JobStatus.COMPLETED

                except Exception as e:
                    job.error = e
                    job.status = JobStatus.FAILED

                job.completed_at = time.time()
                self.result_callback(job)

            except Empty:
                continue
            except Exception as e:
                # 记录错误但继续运行
                print(f"Worker {self.worker_id} error: {e}")


class JobScheduler:
    """作业调度器"""

    def __init__(
        self,
        max_workers: int = 4,
        enable_dependencies: bool = True,
        enable_auto_retry: bool = True,
    ):
        self.max_workers = max_workers
        self.enable_dependencies = enable_dependencies
        self.enable_auto_retry = enable_auto_retry

        # 作业存储
        self._jobs: Dict[str, ScheduledJob] = {}
        self._pending_queue: List[ScheduledJob] = []
        self._running_jobs: Dict[str, ScheduledJob] = {}

        # 依赖图
        self._dependency_graph: Dict[str, Set[str]] = {}  # job_id -> dependencies
        self._dependents_graph: Dict[str, Set[str]] = {}  # job_id -> dependents

        # 线程池
        self._job_queue: Queue = Queue()
        self._workers: List[WorkerThread] = []
        self._lock = threading.Lock()

        # 状态
        self._state = SchedulerState()
        self._job_counter = 0

    @property
    def state(self) -> SchedulerState:
        """获取调度器状态"""
        with self._lock:
            self._update_state()
            return self._state

    def _update_state(self) -> None:
        """更新状态"""
        self._state.total_jobs = len(self._jobs)
        self._state.completed_jobs = sum(
            1 for j in self._jobs.values()
            if j.status == JobStatus.COMPLETED
        )
        self._state.failed_jobs = sum(
            1 for j in self._jobs.values()
            if j.status == JobStatus.FAILED
        )
        self._state.running_jobs = len(self._running_jobs)
        self._state.queued_jobs = len(self._pending_queue)

    def submit_job(
        self,
        task_func: Callable,
        job_type: str = "",
        priority: JobPriority = JobPriority.NORMAL,
        dependencies: Optional[List[str]] = None,
        job_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """提交作业"""
        with self._lock:
            if job_id is None:
                job_id = f"JOB-{time.time():.0f}-{self._job_counter}"
                self._job_counter += 1

            job = ScheduledJob(
                job_id=job_id,
                job_type=job_type,
                priority=priority.value,
                submit_time=time.time(),
                task_func=task_func,
                task_kwargs=kwargs,
                dependencies=dependencies or [],
            )

            self._jobs[job_id] = job

            # 构建依赖图
            if self.enable_dependencies:
                for dep_id in job.dependencies:
                    if dep_id not in self._dependency_graph:
                        self._dependency_graph[dep_id] = set()
                    self._dependency_graph[dep_id].add(job_id)

                    if job_id not in self._dependents_graph:
                        self._dependents_graph[job_id] = set()
                    self._dependents_graph[job_id].add(dep_id)

            # 如果没有依赖或依赖已满足，加入队列
            if self._check_dependencies(job):
                heapq.heappush(self._pending_queue, job)
                job.status = JobStatus.QUEUED
            else:
                job.status = JobStatus.BLOCKED

        # 启动调度器
        if not self._state.is_running:
            self.start()

        return job_id

    def _check_dependencies(self, job: ScheduledJob) -> bool:
        """检查依赖是否满足"""
        if not self.enable_dependencies:
            return True

        for dep_id in job.dependencies:
            dep_job = self._jobs.get(dep_id)
            if not dep_job or dep_job.status != JobStatus.COMPLETED:
                return False

        return True

    def _on_job_complete(self, job: ScheduledJob) -> None:
        """作业完成回调"""
        with self._lock:
            # 从运行中移除
            if job.job_id in self._running_jobs:
                del self._running_jobs[job.job_id]

            # 处理失败重试
            if job.status == JobStatus.FAILED and self.enable_auto_retry:
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = JobStatus.PENDING
                    job.error = None
                    heapq.heappush(self._pending_queue, job)
                    return

            # 检查并解除被阻塞的作业
            if job.job_id in self._dependency_graph:
                for dependent_id in self._dependency_graph[job.job_id]:
                    dependent_job = self._jobs.get(dependent_id)
                    if dependent_job and dependent_job.status == JobStatus.BLOCKED:
                        if self._check_dependencies(dependent_job):
                            dependent_job.status = JobStatus.QUEUED
                            heapq.heappush(self._pending_queue, dependent_job)

    def _next_job(self) -> Optional[ScheduledJob]:
        """获取下一个作业"""
        with self._lock:
            while self._pending_queue:
                job = heapq.heappop(self._pending_queue)

                # 检查作业状态
                if job.status in [JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED]:
                    continue

                # 检查依赖
                if not self._check_dependencies(job):
                    job.status = JobStatus.BLOCKED
                    continue

                # 检查并发限制
                if len(self._running_jobs) >= self.max_workers:
                    # 放回队列
                    heapq.heappush(self._pending_queue, job)
                    break

                self._running_jobs[job.job_id] = job
                return job

        return None

    def start(self) -> None:
        """启动调度器"""
        with self._lock:
            if self._state.is_running:
                return

            self._state.is_running = True

            # 启动工作线程
            for i in range(self.max_workers):
                worker = WorkerThread(
                    worker_id=i,
                    job_queue=self._job_queue,
                    result_callback=self._on_job_complete,
                )
                worker.start()
                self._workers.append(worker)

            # 启动调度线程
            def schedule_loop():
                while self._state.is_running:
                    if not self._state.is_paused:
                        job = self._next_job()
                        if job:
                            self._job_queue.put(job)
                    time.sleep(0.01)

            threading.Thread(target=schedule_loop, daemon=True).start()

    def stop(self, wait: bool = True) -> None:
        """停止调度器"""
        with self._lock:
            self._state.is_running = False

            # 停止工作线程
            for worker in self._workers:
                worker.stop()

            # 发送停止信号
            for _ in self._workers:
                self._job_queue.put(None)

            self._workers.clear()

    def pause(self) -> None:
        """暂停调度"""
        with self._lock:
            self._state.is_paused = True

    def resume(self) -> None:
        """恢复调度"""
        with self._lock:
            self._state.is_paused = False

    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.is_finished:
                return False

            job.status = JobStatus.CANCELLED

            # 如果在运行队列中，移除
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]

            return True

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """获取作业"""
        return self._jobs.get(job_id)

    def get_jobs_by_status(self, status: JobStatus) -> List[ScheduledJob]:
        """按状态获取作业列表"""
        return [j for j in self._jobs.values() if j.status == status]

    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """获取作业状态"""
        job = self._jobs.get(job_id)
        return job.status if job else None

    def wait_for_job(
        self,
        job_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[ScheduledJob]:
        """等待作业完成"""
        start_time = time.time()

        while True:
            job = self._jobs.get(job_id)
            if not job:
                return None

            if job.is_finished:
                return job

            if timeout and (time.time() - start_time) > timeout:
                return job

            time.sleep(0.1)

    def wait_for_all(self, timeout: Optional[float] = None) -> bool:
        """等待所有作业完成"""
        start_time = time.time()

        while True:
            state = self.state

            if state.total_jobs == 0:
                return True

            if state.queued_jobs + state.running_jobs == 0:
                return True

            if timeout and (time.time() - start_time) > timeout:
                return False

            time.sleep(0.1)

    def clear(self) -> None:
        """清除所有作业"""
        with self._lock:
            self._jobs.clear()
            self._pending_queue.clear()
            self._running_jobs.clear()
            self._dependency_graph.clear()
            self._dependents_graph.clear()
            self._job_counter = 0

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        state = self.state

        # 计算平均执行时间
        completed = [j for j in self._jobs.values() if j.is_finished and j.duration > 0]
        avg_duration = sum(j.duration for j in completed) / len(completed) if completed else 0

        return {
            "total_jobs": state.total_jobs,
            "completed": state.completed_jobs,
            "failed": state.failed_jobs,
            "running": state.running_jobs,
            "queued": state.queued_jobs,
            "success_rate": state.success_rate,
            "avg_duration": avg_duration,
            "is_running": state.is_running,
            "is_paused": state.is_paused,
        }


# 便捷函数
def create_scheduler(max_workers: int = 4) -> JobScheduler:
    """创建调度器"""
    return JobScheduler(max_workers=max_workers)


def submit_task(
    scheduler: JobScheduler,
    task_func: Callable,
    priority: JobPriority = JobPriority.NORMAL,
    **kwargs,
) -> str:
    """提交任务"""
    return scheduler.submit_job(
        task_func=task_func,
        priority=priority,
        **kwargs,
    )
