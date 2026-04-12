"""
Tests for pipeline_websocket.py — TDD for PipelineEventBus (Plan 30-03).

Covers:
1.  publish() assigns monotonic global sequence numbers
2.  After 105 events, buffer holds exactly 100 (oldest 5 dropped)
3.  get_buffer() returns events in ascending sequence order
4.  replay_from(last_seq=N) returns only events with sequence > N
5.  replay_from(last_seq=0) returns all buffered events
6.  Two pipelines have independent buffers
7.  subscribe() returns an asyncio.Queue; published events appear in queue
8.  broadcast_pipeline_event() calls bus.publish() on the singleton
"""

import asyncio
import threading
import time

import pytest

from api_server.services.pipeline_websocket import (
    PipelineEvent,
    PipelineEventBus,
    broadcast_pipeline_event,
    get_event_bus,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def fresh_bus():
    """Create a fresh PipelineEventBus for each test (isolated state)."""
    bus = PipelineEventBus()
    yield bus
    # No cleanup needed — each test gets its own bus instance


@pytest.fixture
def fresh_singleton():
    """Reset the module-level singleton to ensure isolation."""
    import api_server.services.pipeline_websocket as pw
    pw._event_bus = None
    yield
    pw._event_bus = None


# --------------------------------------------------------------------------
# Test 1: publish() assigns monotonic sequence numbers
# --------------------------------------------------------------------------

def test_publish_assigns_monotonic_sequence_numbers(fresh_bus):
    """First event gets seq=1, second gets seq=2, etc. (global counter)."""
    bus = fresh_bus
    e1 = PipelineEvent(event_type="pipeline_started", pipeline_id="P1")
    e2 = PipelineEvent(event_type="step_started", pipeline_id="P1")
    e3 = PipelineEvent(event_type="step_completed", pipeline_id="P1")

    r1 = bus.publish(e1)
    r2 = bus.publish(e2)
    r3 = bus.publish(e3)

    assert r1.sequence == 1
    assert r2.sequence == 2
    assert r3.sequence == 3


# --------------------------------------------------------------------------
# Test 2: After 105 events, buffer holds exactly 100 (ring buffer)
# --------------------------------------------------------------------------

def test_buffer_holds_100_events_max(fresh_bus):
    """Publishing 105 events for the same pipeline keeps only the last 100."""
    bus = fresh_bus
    for i in range(105):
        e = PipelineEvent(event_type="step_completed", pipeline_id="P1")
        bus.publish(e)

    buf = bus.get_buffer("P1")
    assert len(buf) == 100


# --------------------------------------------------------------------------
# Test 3: get_buffer() returns events in ascending sequence order
# --------------------------------------------------------------------------

def test_get_buffer_returns_ascending_order(fresh_bus):
    """get_buffer() returns the oldest event first, newest last."""
    bus = fresh_bus
    for i in range(10):
        e = PipelineEvent(event_type="step_started", pipeline_id="P1")
        bus.publish(e)

    buf = bus.get_buffer("P1")
    sequences = [e.sequence for e in buf]
    assert sequences == list(range(1, 11))


# --------------------------------------------------------------------------
# Test 4: replay_from(last_seq=N) returns only events with sequence > N
# --------------------------------------------------------------------------

def test_replay_from_excludes_events_at_or_below_last_seq(fresh_bus):
    """replay_from with last_seq=50 returns only events seq > 50."""
    bus = fresh_bus
    for i in range(60):
        e = PipelineEvent(event_type="step_started", pipeline_id="P1")
        bus.publish(e)

    missed = bus.replay_from("P1", last_seq=50)
    seqs = [e.sequence for e in missed]
    assert all(s > 50 for s in seqs)
    assert seqs == list(range(51, 61))


# --------------------------------------------------------------------------
# Test 5: replay_from(last_seq=0) returns all buffered events
# --------------------------------------------------------------------------

def test_replay_from_with_zero_returns_all(fresh_bus):
    """replay_from with last_seq=0 is equivalent to get_buffer (all events)."""
    bus = fresh_bus
    for i in range(5):
        e = PipelineEvent(event_type="pipeline_started", pipeline_id="P1")
        bus.publish(e)

    missed = bus.replay_from("P1", last_seq=0)
    buf = bus.get_buffer("P1")
    assert [e.sequence for e in missed] == [e.sequence for e in buf]


# --------------------------------------------------------------------------
# Test 6: Two pipelines have independent buffers
# --------------------------------------------------------------------------

def test_buffers_are_independent_per_pipeline(fresh_bus):
    """P1 and P2 have separate buffers; events for P1 do not appear in P2."""
    bus = fresh_bus

    for i in range(3):
        bus.publish(PipelineEvent(event_type="step_started", pipeline_id="P1"))

    for i in range(5):
        bus.publish(PipelineEvent(event_type="step_started", pipeline_id="P2"))

    buf1 = bus.get_buffer("P1")
    buf2 = bus.get_buffer("P2")

    assert len(buf1) == 3
    assert len(buf2) == 5

    p1_seqs = {e.sequence for e in buf1}
    p2_seqs = {e.sequence for e in buf2}
    assert p1_seqs.isdisjoint(p2_seqs)  # no overlap in sequences


# --------------------------------------------------------------------------
# Test 7: subscribe() returns asyncio.Queue; published events appear in queue
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribe_queue_receives_published_events(fresh_bus):
    """Subscribing to a pipeline and publishing events puts them in the queue."""
    bus = fresh_bus
    q = bus.subscribe("P1")

    # Publish two events
    e1 = PipelineEvent(event_type="step_started", pipeline_id="P1")
    e2 = PipelineEvent(event_type="step_completed", pipeline_id="P1")
    bus.publish(e1)
    bus.publish(e2)

    # Events should be in the queue (non-blocking get)
    received = []
    received.append(await asyncio.wait_for(q.get(), timeout=1.0))
    received.append(await asyncio.wait_for(q.get(), timeout=1.0))

    assert received[0].event_type == "step_started"
    assert received[1].event_type == "step_completed"


# --------------------------------------------------------------------------
# Test 8: broadcast_pipeline_event() calls bus.publish() on singleton
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_pipeline_event_calls_singleton_publish(fresh_singleton):
    """broadcast_pipeline_event() publishes to the global singleton bus."""
    event = PipelineEvent(event_type="pipeline_started", pipeline_id="P1")
    await broadcast_pipeline_event(event)

    bus = get_event_bus()
    assert bus is not None
    buf = bus.get_buffer("P1")
    assert len(buf) == 1
    assert buf[0].event_type == "pipeline_started"
    assert buf[0].sequence == 1


# --------------------------------------------------------------------------
# Additional verification tests
# --------------------------------------------------------------------------

def test_publish_returns_event_with_sequence(fresh_bus):
    """publish() returns the event with the sequence number set."""
    bus = fresh_bus
    e = PipelineEvent(event_type="pipeline_started", pipeline_id="P1")
    result = bus.publish(e)
    assert result.sequence == 1
    assert e.sequence == 1  # same object, mutated in place


def test_subscriber_count(fresh_bus):
    """subscriber_count() returns the number of active subscribers for a pipeline."""
    bus = fresh_bus
    q1 = bus.subscribe("P1")
    q2 = bus.subscribe("P1")
    assert bus.subscriber_count("P1") == 2
    bus.unsubscribe("P1", q1)
    assert bus.subscriber_count("P1") == 1
    bus.unsubscribe("P1", q2)
    assert bus.subscriber_count("P1") == 0


def test_unsubscribe_removes_queue(fresh_bus):
    """unsubscribe() removes the queue from the subscriber set."""
    bus = fresh_bus
    q = bus.subscribe("P1")
    bus.unsubscribe("P1", q)
    assert bus.subscriber_count("P1") == 0


def test_unsubscribe_nonexistent_is_safe(fresh_bus):
    """Calling unsubscribe for a non-existent subscriber does not raise."""
    bus = fresh_bus
    q = asyncio.Queue()
    bus.unsubscribe("P1", q)  # should not raise


def test_get_buffer_unknown_pipeline_returns_empty(fresh_bus):
    """get_buffer() on a pipeline with no events returns an empty list."""
    bus = fresh_bus
    assert bus.get_buffer("UNKNOWN") == []


def test_replay_from_unknown_pipeline_returns_empty(fresh_bus):
    """replay_from() on a pipeline with no events returns an empty list."""
    bus = fresh_bus
    assert bus.replay_from("UNKNOWN", last_seq=0) == []
