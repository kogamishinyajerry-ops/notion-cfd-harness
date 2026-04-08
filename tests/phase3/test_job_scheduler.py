#!/usr/bin/env python3
"""
Tests for Phase 3 Job Scheduler

Coverage:
1. SchedulerState dataclass
2. ScheduledJob creation and defaults
3. JobScheduler: submit, schedule, state transitions, priority, dependencies, cancel
4. BatchJobScheduler: batch submit, progress, run_all, deadlock detection
5. Convenience functions: create_scheduled_job, schedule_from_solver_jobs
"""

import time
import pytest

from knowledge_compiler.phase3.schema import (
    JobPriority,
    ScheduledJob,
    SchedulerState,
    SolverJob,
    SolverStatus,
)
from knowledge_compiler.phase3.job_scheduler.scheduler import (
    JobScheduler,
    BatchJobScheduler,
    create_scheduled_job,
    schedule_from_solver_jobs,
)


# ============================================================================
# SchedulerState Tests
# ============================================================================

class TestSchedulerState:
    def test_default_state(self):
        state = SchedulerState()
        assert state.running_jobs == []
        assert state.pending_jobs == []
        assert state.completed_jobs == []
        assert state.failed_jobs == []
        assert state.max_concurrent == 2

    def test_can_schedule_below_limit(self):
        state = SchedulerState(max_concurrent=3)
        assert state.can_schedule() is True
        state.running_jobs = ["j1", "j2"]
        assert state.can_schedule() is True

    def test_cannot_schedule_at_limit(self):
        state = SchedulerState(max_concurrent=2)
        state.running_jobs = ["j1", "j2"]
        assert state.can_schedule() is False


# ============================================================================
# ScheduledJob Tests
# ============================================================================

class TestScheduledJob:
    def test_creation(self):
        job = ScheduledJob(
            job_id="JOB-001",
            priority=JobPriority.HIGH,
            estimated_duration=3600.0,
            dependencies=["JOB-000"],
        )
        assert job.job_id == "JOB-001"
        assert job.priority == JobPriority.HIGH
        assert job.estimated_duration == 3600.0
        assert job.dependencies == ["JOB-000"]
        assert job.status == SolverStatus.PENDING

    def test_default_values(self):
        job = ScheduledJob(job_id="JOB-001", priority=JobPriority.MEDIUM)
        assert job.dependencies == []
        assert job.resource_requirements == {}
        assert job.scheduled_at == 0.0
        assert job.started_at == 0.0


# ============================================================================
# JobScheduler Tests
# ============================================================================

class TestJobScheduler:
    def test_init(self):
        scheduler = JobScheduler(max_concurrent=4)
        assert scheduler.state.max_concurrent == 4

    def test_submit(self):
        scheduler = JobScheduler()
        job = ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM)
        scheduler.submit(job)
        assert scheduler.get_pending_count() == 1
        assert "J1" in scheduler.state.pending_jobs

    def test_submit_duplicate_raises(self):
        scheduler = JobScheduler()
        job = ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM)
        scheduler.submit(job)
        with pytest.raises(ValueError, match="重复"):
            scheduler.submit(job)

    def test_schedule_next_no_deps(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.LOW))
        scheduler.submit(ScheduledJob(job_id="J2", priority=JobPriority.HIGH))

        next_job = scheduler.schedule_next()
        assert next_job.job_id == "J2"  # HIGH before LOW

    def test_schedule_next_priority_order(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.LOW))
        scheduler.submit(ScheduledJob(job_id="J2", priority=JobPriority.MEDIUM))
        scheduler.submit(ScheduledJob(job_id="J3", priority=JobPriority.CRITICAL))
        scheduler.submit(ScheduledJob(job_id="J4", priority=JobPriority.HIGH))

        order = []
        while True:
            job = scheduler.schedule_next()
            if job is None:
                break
            order.append(job.job_id)
            scheduler.mark_started(job.job_id)
            scheduler.mark_completed(job.job_id)

        assert order == ["J3", "J4", "J2", "J1"]

    def test_schedule_next_concurrent_limit(self):
        scheduler = JobScheduler(max_concurrent=1)
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.HIGH))
        scheduler.submit(ScheduledJob(job_id="J2", priority=JobPriority.LOW))

        # Schedule first
        job1 = scheduler.schedule_next()
        assert job1.job_id == "J1"
        scheduler.mark_started(job1.job_id)

        # Can't schedule second (concurrent limit)
        assert scheduler.schedule_next() is None

    def test_schedule_next_empty(self):
        scheduler = JobScheduler()
        assert scheduler.schedule_next() is None

    def test_dependency_blocking(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.HIGH))
        scheduler.submit(
            ScheduledJob(
                job_id="J2",
                priority=JobPriority.CRITICAL,
                dependencies=["J1"],
            )
        )

        # J2 has higher priority but depends on J1
        next_job = scheduler.schedule_next()
        assert next_job.job_id == "J1"

    def test_dependency_resolved_after_completion(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.LOW))
        scheduler.submit(
            ScheduledJob(
                job_id="J2",
                priority=JobPriority.HIGH,
                dependencies=["J1"],
            )
        )

        # Complete J1
        job1 = scheduler.schedule_next()
        scheduler.mark_started(job1.job_id)
        scheduler.mark_completed(job1.job_id)

        # Now J2 should be schedulable
        job2 = scheduler.schedule_next()
        assert job2.job_id == "J2"

    def test_mark_started(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        scheduler.mark_started("J1")
        assert "J1" in scheduler.state.running_jobs
        assert "J1" not in scheduler.state.pending_jobs

    def test_mark_completed_success(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        scheduler.mark_started("J1")
        scheduler.mark_completed("J1", success=True)
        assert "J1" in scheduler.state.completed_jobs
        assert scheduler.get_job("J1").status == SolverStatus.COMPLETED

    def test_mark_completed_failure(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        scheduler.mark_started("J1")
        scheduler.mark_completed("J1", success=False)
        assert "J1" in scheduler.state.failed_jobs
        assert scheduler.get_job("J1").status == SolverStatus.FAILED

    def test_mark_unknown_raises(self):
        scheduler = JobScheduler()
        with pytest.raises(KeyError):
            scheduler.mark_started("UNKNOWN")

    def test_cancel_pending(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        assert scheduler.cancel("J1") is True
        assert scheduler.get_pending_count() == 0

    def test_cancel_running_fails(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        scheduler.mark_started("J1")
        assert scheduler.cancel("J1") is False

    def test_cancel_unknown(self):
        scheduler = JobScheduler()
        assert scheduler.cancel("UNKNOWN") is False

    def test_is_done(self):
        scheduler = JobScheduler()
        assert scheduler.is_done() is True  # No jobs

        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        assert scheduler.is_done() is False

        scheduler.mark_started("J1")
        scheduler.mark_completed("J1")
        assert scheduler.is_done() is True

    def test_get_job(self):
        scheduler = JobScheduler()
        assert scheduler.get_job("X") is None
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        assert scheduler.get_job("J1") is not None

    def test_fifo_same_priority(self):
        scheduler = JobScheduler()
        scheduler.submit(ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM))
        scheduler.submit(ScheduledJob(job_id="J2", priority=JobPriority.MEDIUM))
        scheduler.submit(ScheduledJob(job_id="J3", priority=JobPriority.MEDIUM))

        order = []
        while not scheduler.is_done():
            job = scheduler.schedule_next()
            if job is None:
                break
            scheduler.mark_started(job.job_id)
            scheduler.mark_completed(job.job_id)
            order.append(job.job_id)

        assert order == ["J1", "J2", "J3"]


# ============================================================================
# BatchJobScheduler Tests
# ============================================================================

class TestBatchJobScheduler:
    def test_submit_batch(self):
        batch = BatchJobScheduler(max_concurrent=3)
        jobs = [
            ScheduledJob(job_id=f"J{i}", priority=JobPriority.MEDIUM)
            for i in range(5)
        ]
        count = batch.submit_batch(jobs)
        assert count == 5

    def test_submit_batch_skip_duplicates(self):
        batch = BatchJobScheduler()
        jobs = [
            ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM),
            ScheduledJob(job_id="J1", priority=JobPriority.HIGH),
        ]
        count = batch.submit_batch(jobs)
        assert count == 1

    def test_get_progress(self):
        batch = BatchJobScheduler()
        batch.submit_batch([
            ScheduledJob(job_id=f"J{i}", priority=JobPriority.MEDIUM)
            for i in range(4)
        ])
        progress = batch.get_progress()
        assert progress["pending"] == 4
        assert progress["total"] == 4

    def test_run_all_success(self):
        batch = BatchJobScheduler(max_concurrent=2)

        def mock_executor(job):
            return True

        batch.submit_batch([
            ScheduledJob(job_id=f"J{i}", priority=JobPriority.MEDIUM)
            for i in range(4)
        ])
        results = batch.run_all(mock_executor)

        assert len(results["completed"]) == 4
        assert len(results["failed"]) == 0
        assert results["success_rate"] == 1.0

    def test_run_all_with_failures(self):
        batch = BatchJobScheduler()

        def flaky_executor(job):
            return not job.job_id.endswith("1")  # J1, J11, etc. fail

        batch.submit_batch([
            ScheduledJob(job_id=f"J{i}", priority=JobPriority.MEDIUM)
            for i in range(3)
        ])
        results = batch.run_all(flaky_executor)

        assert "J1" in results["failed"]
        assert "J0" in results["completed"]
        assert "J2" in results["completed"]

    def test_run_all_with_dependencies(self):
        batch = BatchJobScheduler()
        batch.submit_batch([
            ScheduledJob(job_id="J1", priority=JobPriority.LOW),
            ScheduledJob(
                job_id="J2",
                priority=JobPriority.HIGH,
                dependencies=["J1"],
            ),
        ])

        results = batch.run_all(lambda job: True)
        assert len(results["completed"]) == 2

    def test_run_all_deadlock_detection(self):
        """Circular dependency should be detected"""
        batch = BatchJobScheduler()
        batch.submit_batch([
            ScheduledJob(job_id="J1", priority=JobPriority.MEDIUM, dependencies=["J2"]),
            ScheduledJob(job_id="J2", priority=JobPriority.MEDIUM, dependencies=["J1"]),
        ])

        results = batch.run_all(lambda job: True)
        assert len(results["cancelled"]) == 2

    def test_schedule_ready(self):
        batch = BatchJobScheduler(max_concurrent=2)
        batch.submit_batch([
            ScheduledJob(job_id=f"J{i}", priority=JobPriority.MEDIUM)
            for i in range(4)
        ])

        ready = batch.schedule_ready()
        assert len(ready) == 2  # max_concurrent limit


# ============================================================================
# Convenience Functions
# ============================================================================

class TestConvenienceFunctions:
    def test_create_scheduled_job(self):
        job = create_scheduled_job(
            job_id="TEST-001",
            priority=JobPriority.HIGH,
            estimated_duration=1800.0,
            dependencies=["PREV-001"],
        )
        assert job.job_id == "TEST-001"
        assert job.priority == JobPriority.HIGH
        assert job.estimated_duration == 1800.0
        assert job.dependencies == ["PREV-001"]

    def test_create_scheduled_job_defaults(self):
        job = create_scheduled_job(job_id="TEST-001")
        assert job.priority == JobPriority.MEDIUM
        assert job.dependencies == []

    def test_schedule_from_solver_jobs(self):
        solver_jobs = [
            SolverJob(job_id="SJ1"),
            SolverJob(job_id="SJ2"),
        ]
        scheduled = schedule_from_solver_jobs(solver_jobs)
        assert len(scheduled) == 2
        assert scheduled[0].job_id == "SJ1"
        assert scheduled[1].job_id == "SJ2"
        # No dependencies by default
        for job in scheduled:
            assert job.dependencies == []
