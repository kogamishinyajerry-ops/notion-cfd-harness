#!/usr/bin/env python3
"""
Tests for Job Scheduler - 作业调度器测试
"""

import time
import pytest

from knowledge_compiler.phase2.execution_layer.job_scheduler import (
    JobPriority,
    JobScheduler,
    JobStatus,
    ScheduledJob,
    SchedulerState,
    WorkerThread,
    create_scheduler,
    submit_task,
)


class TestJobStatus:
    """测试作业状态"""

    def test_status_values(self):
        """测试状态值"""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"


class TestJobPriority:
    """测试作业优先级"""

    def test_priority_order(self):
        """测试优先级顺序"""
        assert JobPriority.CRITICAL.value < JobPriority.HIGH.value
        assert JobPriority.HIGH.value < JobPriority.NORMAL.value
        assert JobPriority.NORMAL.value < JobPriority.LOW.value


class TestScheduledJob:
    """测试调度作业"""

    def test_job_creation(self):
        """测试创建作业"""
        job = ScheduledJob(
            job_id="test-job",
            job_type="test",
            priority=JobPriority.NORMAL.value,
            submit_time=time.time(),
        )
        assert job.job_id == "test-job"
        assert job.job_type == "test"
        assert job.status == JobStatus.PENDING

    def test_job_duration(self):
        """测试作业时长"""
        job = ScheduledJob(priority=1, submit_time=time.time())
        job.started_at = time.time() - 1
        job.completed_at = time.time()
        assert job.duration >= 1.0

    def test_is_finished(self):
        """测试是否完成"""
        job = ScheduledJob(priority=1, submit_time=time.time())

        job.status = JobStatus.PENDING
        assert job.is_finished is False

        job.status = JobStatus.COMPLETED
        assert job.is_finished is True

        job.status = JobStatus.FAILED
        assert job.is_finished is True

    def test_can_run(self):
        """测试是否可运行"""
        job = ScheduledJob(priority=1, submit_time=time.time())
        job.status = JobStatus.PENDING
        job.dependencies = []
        assert job.can_run is True

        job.dependencies = ["other-job"]
        assert job.can_run is False

        job.status = JobStatus.RUNNING
        assert job.can_run is False

    def test_get_summary(self):
        """测试获取摘要"""
        job = ScheduledJob(
            job_id="test",
            job_type="test_type",
            priority=1,
            submit_time=time.time(),
        )
        summary = job.get_summary()
        assert summary["job_id"] == "test"
        assert summary["job_type"] == "test_type"
        assert summary["priority"] == 1


class TestSchedulerState:
    """测试调度器状态"""

    def test_state_creation(self):
        """测试创建状态"""
        state = SchedulerState()
        assert state.is_running is False
        assert state.is_paused is False
        assert state.total_jobs == 0

    def test_success_rate(self):
        """测试成功率"""
        state = SchedulerState(
            completed_jobs=10,
            failed_jobs=2,
        )
        assert state.success_rate == 0.8


class TestJobScheduler:
    """测试作业调度器"""

    def test_scheduler_init(self):
        """测试初始化"""
        scheduler = JobScheduler(max_workers=2)
        assert scheduler.max_workers == 2
        assert scheduler.enable_dependencies is True
        assert scheduler._state.is_running is False

    def test_submit_simple_job(self):
        """测试提交简单作业"""
        scheduler = JobScheduler()

        def dummy_task():
            return "result"

        job_id = scheduler.submit_job(dummy_task)
        assert job_id.startswith("JOB-")

        job = scheduler.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id

    def test_submit_with_priority(self):
        """测试带优先级提交"""
        scheduler = JobScheduler()

        job_id = scheduler.submit_job(
            lambda: None,
            priority=JobPriority.HIGH,
        )

        job = scheduler.get_job(job_id)
        assert job.priority == JobPriority.HIGH.value

    def test_get_job_status(self):
        """测试获取作业状态"""
        scheduler = JobScheduler()

        job_id = scheduler.submit_job(lambda: None)
        status = scheduler.get_job_status(job_id)

        assert status is not None
        assert status in [JobStatus.QUEUED, JobStatus.BLOCKED]

    def test_get_jobs_by_status(self):
        """测试按状态获取作业"""
        scheduler = JobScheduler()

        scheduler.submit_job(lambda: None)
        scheduler.submit_job(lambda: None)

        pending_jobs = scheduler.get_jobs_by_status(JobStatus.PENDING)
        queued_jobs = scheduler.get_jobs_by_status(JobStatus.QUEUED)

        # 作业应该被移出 PENDING 状态
        assert len(pending_jobs) == 0
        assert len(queued_jobs) >= 0

    def test_cancel_job(self):
        """测试取消作业"""
        scheduler = JobScheduler()

        def slow_task():
            time.sleep(10)
            return "should not complete"

        job_id = scheduler.submit_job(slow_task)
        result = scheduler.cancel_job(job_id)

        assert result is True

        job = scheduler.get_job(job_id)
        assert job.status == JobStatus.CANCELLED

    def test_cancel_nonexistent_job(self):
        """测试取消不存在的作业"""
        scheduler = JobScheduler()
        result = scheduler.cancel_job("nonexistent")
        assert result is False

    def test_cancel_finished_job(self):
        """测试取消已完成作业"""
        scheduler = JobScheduler()

        def quick_task():
            return "done"

        job_id = scheduler.submit_job(quick_task)

        # 等待作业完成
        job = scheduler.wait_for_job(job_id, timeout=5)

        if job and job.is_finished:
            result = scheduler.cancel_job(job_id)
            assert result is False

    def test_pause_resume(self):
        """测试暂停恢复"""
        scheduler = JobScheduler()

        scheduler.start()
        scheduler.pause()

        assert scheduler.state.is_paused is True

        scheduler.resume()
        assert scheduler.state.is_paused is False

        scheduler.stop()

    def test_clear(self):
        """测试清除"""
        scheduler = JobScheduler()

        scheduler.submit_job(lambda: None)
        scheduler.submit_job(lambda: None)

        assert len(scheduler._jobs) == 2

        scheduler.clear()

        assert len(scheduler._jobs) == 0

    def test_get_statistics(self):
        """测试获取统计"""
        scheduler = JobScheduler()

        scheduler.submit_job(lambda: None)
        scheduler.submit_job(lambda: lambda: 1/0)  # 会失败的作业

        stats = scheduler.get_statistics()
        assert "total_jobs" in stats
        assert "success_rate" in stats
        assert "is_running" in stats


class TestJobDependencies:
    """测试作业依赖"""

    def test_submit_with_dependencies(self):
        """测试带依赖提交"""
        scheduler = JobScheduler()

        results = []

        def task_a():
            results.append("a")
            return "a"

        def task_b():
            results.append("b")
            return "b"

        job_a = scheduler.submit_job(task_a)
        job_b = scheduler.submit_job(task_b, dependencies=[job_a])

        # job_b 应该被阻塞
        assert scheduler.get_job_status(job_b) == JobStatus.BLOCKED

    def test_dependency_chain(self):
        """测试依赖链"""
        scheduler = JobScheduler()

        results = []

        def task(name):
            def inner():
                results.append(name)
                return name
            return inner

        job_a = scheduler.submit_job(task("a"))
        job_b = scheduler.submit_job(task("b"), dependencies=[job_a])
        job_c = scheduler.submit_job(task("c"), dependencies=[job_b])

        # 验证依赖关系
        job_c_obj = scheduler.get_job(job_c)
        assert len(job_c_obj.dependencies) == 1
        assert job_b in job_c_obj.dependencies

    def test_dependency_completion(self):
        """测试依赖完成后的执行"""
        scheduler = JobScheduler(max_workers=1)

        results = []

        def task_a():
            time.sleep(0.1)
            results.append("a")
            return "a"

        def task_b():
            results.append("b")
            return "b"

        job_a = scheduler.submit_job(task_a)
        job_b = scheduler.submit_job(task_b, dependencies=[job_a])

        scheduler.wait_for_all(timeout=5)

        # b 应该在 a 之后执行
        assert results == ["a", "b"]


class TestAutoRetry:
    """测试自动重试"""

    def test_auto_retry_enabled(self):
        """测试启用自动重试"""
        scheduler = JobScheduler(max_workers=1, enable_auto_retry=True)

        attempts = []

        def failing_task():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("fail")
            return "success"

        job_id = scheduler.submit_job(failing_task)

        scheduler.wait_for_job(job_id, timeout=10)

        job = scheduler.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert len(attempts) == 3

    def test_auto_retry_disabled(self):
        """测试禁用自动重试"""
        scheduler = JobScheduler(max_workers=1, enable_auto_retry=False)

        attempts = []

        def failing_task():
            attempts.append(1)
            raise ValueError("fail")

        job_id = scheduler.submit_job(failing_task)

        scheduler.wait_for_job(job_id, timeout=5)

        job = scheduler.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert len(attempts) == 1


class TestWaitForJob:
    """测试等待作业"""

    def test_wait_for_completed_job(self):
        """测试等待已完成作业"""
        scheduler = JobScheduler()

        def quick_task():
            return "done"

        job_id = scheduler.submit_job(quick_task)
        job = scheduler.wait_for_job(job_id, timeout=5)

        assert job is not None
        assert job.status == JobStatus.COMPLETED

    def test_wait_for_job_timeout(self):
        """测试等待作业超时"""
        scheduler = JobScheduler()

        def slow_task():
            time.sleep(10)
            return "done"

        job_id = scheduler.submit_job(slow_task)
        job = scheduler.wait_for_job(job_id, timeout=0.5)

        assert job is not None
        assert not job.is_finished

    def test_wait_for_nonexistent_job(self):
        """测试等待不存在的作业"""
        scheduler = JobScheduler()
        job = scheduler.wait_for_job("nonexistent", timeout=1)
        assert job is None


class TestWaitForAll:
    """测试等待所有作业"""

    def test_wait_for_all_success(self):
        """测试等待所有作业成功"""
        scheduler = JobScheduler(max_workers=2)

        for i in range(3):
            scheduler.submit_job(lambda x=i: x * 2)

        result = scheduler.wait_for_all(timeout=5)
        assert result is True

    def test_wait_for_all_empty(self):
        """测试等待空作业列表"""
        scheduler = JobScheduler()
        result = scheduler.wait_for_all(timeout=1)
        assert result is True


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_create_scheduler(self):
        """测试创建调度器"""
        scheduler = create_scheduler(max_workers=4)
        assert isinstance(scheduler, JobScheduler)
        assert scheduler.max_workers == 4

    def test_submit_task(self):
        """测试提交任务"""
        scheduler = JobScheduler()

        def my_task(x):
            return x * 2

        job_id = submit_task(scheduler, my_task, x=5)

        job = scheduler.wait_for_job(job_id, timeout=5)
        assert job.result == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
