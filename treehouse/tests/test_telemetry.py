"""Tests for treehouse telemetry module."""

from datetime import datetime, timezone

import pytest
from vivarium.core import (
    ActionCompleted,
    ActionInvoked,
    BehaviorTree,
    ConditionEvaluated,
    NodeEntered,
    NodeExited,
    NodeStatus,
    State,
    TickCompleted,
    TickStarted,
)

from treehouse import ExecutionTrace, NodeExecution, TraceCollector

# --- NodeExecution Tests ---


def test_node_execution_has_required_fields():
    """NodeExecution should have all required fields."""
    now = datetime.now(timezone.utc)
    execution = NodeExecution(
        node_id="test_node",
        node_name="Test Node",
        node_type="Action",
        path_in_tree="root/test_node",
        timestamp=now,
        status="success",
        duration_ms=10.5,
    )
    assert execution.node_id == "test_node"
    assert execution.node_name == "Test Node"
    assert execution.node_type == "Action"
    assert execution.path_in_tree == "root/test_node"
    assert execution.timestamp == now
    assert execution.status == "success"
    assert execution.duration_ms == 10.5


def test_node_execution_repr():
    """NodeExecution repr should include path."""
    now = datetime.now(timezone.utc)
    execution = NodeExecution(
        node_id="heal",
        node_name="Heal",
        node_type="Action",
        path_in_tree="root/sequence/heal[0]",
        timestamp=now,
        status="success",
        duration_ms=5.0,
    )
    repr_str = repr(execution)
    assert "heal" in repr_str
    assert "root/sequence/heal[0]" in repr_str
    assert "5.00ms" in repr_str


def test_node_execution_to_dict():
    """NodeExecution.to_dict should serialize correctly."""
    now = datetime.now(timezone.utc)
    execution = NodeExecution(
        node_id="test",
        node_name="Test",
        node_type="Action",
        path_in_tree="root/test",
        timestamp=now,
        status="success",
        duration_ms=1.0,
    )
    data = execution.to_dict()
    assert data["node_id"] == "test"
    assert data["path_in_tree"] == "root/test"
    assert data["timestamp"] == now.isoformat()


def test_node_execution_from_dict_roundtrip():
    """NodeExecution should roundtrip through dict."""
    now = datetime.now(timezone.utc)
    original = NodeExecution(
        node_id="test",
        node_name="Test",
        node_type="Action",
        path_in_tree="root/test",
        timestamp=now,
        status="failure",
        duration_ms=2.5,
    )
    restored = NodeExecution.from_dict(original.to_dict())
    assert restored.node_id == original.node_id
    assert restored.path_in_tree == original.path_in_tree
    assert restored.status == original.status
    assert restored.duration_ms == original.duration_ms


# --- ExecutionTrace Tests ---


def test_execution_trace_has_required_fields():
    """ExecutionTrace should have all required fields."""
    trace = ExecutionTrace(tick_id=1)
    assert trace.trace_id  # UUID generated
    assert trace.tick_id == 1
    assert trace.executions == []
    assert trace.metadata == {}


def test_execution_trace_to_json_roundtrip():
    """ExecutionTrace should roundtrip through JSON."""
    now = datetime.now(timezone.utc)
    execution = NodeExecution(
        node_id="test",
        node_name="Test",
        node_type="Action",
        path_in_tree="root/test",
        timestamp=now,
        status="success",
        duration_ms=1.0,
    )
    original = ExecutionTrace(
        trace_id="test-trace-id",
        tick_id=5,
        start_time=now,
        end_time=now,
        status="success",
        executions=[execution],
        metadata={"key": "value"},
    )

    json_str = original.to_json()
    restored = ExecutionTrace.from_json(json_str)

    assert restored.trace_id == original.trace_id
    assert restored.tick_id == original.tick_id
    assert restored.status == original.status
    assert len(restored.executions) == 1
    assert restored.executions[0].node_id == "test"
    assert restored.metadata == {"key": "value"}


# --- TraceCollector Tests ---


def test_trace_collector_implements_event_emitter():
    """TraceCollector should have emit method."""
    collector = TraceCollector()
    assert hasattr(collector, "emit")
    assert callable(collector.emit)


def test_trace_collector_creates_trace_on_tick_events():
    """TraceCollector should create a trace from tick_started/tick_completed."""
    collector = TraceCollector()

    collector.emit(TickStarted(tick_id=1))
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.SUCCESS))

    trace = collector.get_trace()
    assert trace is not None
    assert trace.tick_id == 1
    assert trace.status == "success"
    assert trace.start_time is not None
    assert trace.end_time is not None


def test_trace_collector_computes_duration_from_paired_events():
    """TraceCollector should compute duration from action_invoked/completed."""
    collector = TraceCollector()

    collector.emit(TickStarted(tick_id=1))
    collector.emit(
        ActionInvoked(
            tick_id=1,
            node_id="heal",
            node_type="Action",
            path_in_tree="root/heal",
        )
    )
    # Small delay simulated via timestamp difference in actual usage
    collector.emit(
        ActionCompleted(
            tick_id=1,
            node_id="heal",
            node_type="Action",
            path_in_tree="root/heal",
            result=NodeStatus.SUCCESS,
        )
    )
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.SUCCESS))

    trace = collector.get_trace()
    assert len(trace.executions) == 1
    assert trace.executions[0].node_id == "heal"
    assert trace.executions[0].status == "success"
    # Duration should be >= 0 (timestamps are very close in tests)
    assert trace.executions[0].duration_ms >= 0


def test_trace_collector_handles_node_entered_exited():
    """TraceCollector should handle composite node events."""
    collector = TraceCollector()

    collector.emit(TickStarted(tick_id=1))
    collector.emit(
        NodeEntered(
            tick_id=1,
            node_id="main_seq",
            node_type="Sequence",
            path_in_tree="main_seq",
        )
    )
    collector.emit(
        NodeExited(
            tick_id=1,
            node_id="main_seq",
            node_type="Sequence",
            path_in_tree="main_seq",
            result=NodeStatus.SUCCESS,
        )
    )
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.SUCCESS))

    trace = collector.get_trace()
    assert len(trace.executions) == 1
    assert trace.executions[0].node_type == "Sequence"


def test_trace_collector_handles_condition_evaluated():
    """TraceCollector should handle condition events (no start event)."""
    collector = TraceCollector()

    collector.emit(TickStarted(tick_id=1))
    collector.emit(
        ConditionEvaluated(
            tick_id=1,
            node_id="is_healthy",
            node_type="Condition",
            path_in_tree="root/is_healthy",
            result=True,
        )
    )
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.SUCCESS))

    trace = collector.get_trace()
    assert len(trace.executions) == 1
    assert trace.executions[0].node_id == "is_healthy"
    assert trace.executions[0].status == "success"
    assert trace.executions[0].duration_ms == 0.0  # Conditions are instant


def test_trace_collector_handles_false_condition():
    """TraceCollector should convert False condition to 'failure' status."""
    collector = TraceCollector()

    collector.emit(TickStarted(tick_id=1))
    collector.emit(
        ConditionEvaluated(
            tick_id=1,
            node_id="is_dead",
            node_type="Condition",
            path_in_tree="root/is_dead",
            result=False,
        )
    )
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.FAILURE))

    trace = collector.get_trace()
    assert trace.executions[0].status == "failure"


def test_trace_collector_multiple_ticks():
    """TraceCollector should collect multiple traces."""
    collector = TraceCollector()

    # Tick 1
    collector.emit(TickStarted(tick_id=1))
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.SUCCESS))

    # Tick 2
    collector.emit(TickStarted(tick_id=2))
    collector.emit(TickCompleted(tick_id=2, result=NodeStatus.FAILURE))

    traces = collector.get_traces()
    assert len(traces) == 2
    assert traces[0].tick_id == 1
    assert traces[0].status == "success"
    assert traces[1].tick_id == 2
    assert traces[1].status == "failure"


def test_trace_collector_get_executions():
    """TraceCollector.get_executions should return all executions."""
    collector = TraceCollector()

    collector.emit(TickStarted(tick_id=1))
    collector.emit(
        ConditionEvaluated(
            tick_id=1,
            node_id="cond1",
            node_type="Condition",
            path_in_tree="root/cond1",
            result=True,
        )
    )
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.SUCCESS))

    collector.emit(TickStarted(tick_id=2))
    collector.emit(
        ConditionEvaluated(
            tick_id=2,
            node_id="cond2",
            node_type="Condition",
            path_in_tree="root/cond2",
            result=False,
        )
    )
    collector.emit(TickCompleted(tick_id=2, result=NodeStatus.FAILURE))

    executions = collector.get_executions()
    assert len(executions) == 2
    assert executions[0].node_id == "cond1"
    assert executions[1].node_id == "cond2"


def test_trace_collector_clear():
    """TraceCollector.clear should remove all data."""
    collector = TraceCollector()

    collector.emit(TickStarted(tick_id=1))
    collector.emit(TickCompleted(tick_id=1, result=NodeStatus.SUCCESS))

    assert collector.get_trace() is not None

    collector.clear()

    assert collector.get_trace() is None
    assert collector.get_traces() == []
    assert collector.get_executions() == []


# --- Integration Tests ---


class SuccessAction:
    """A simple action that always succeeds."""

    def __init__(self, name: str):
        self.name = name

    def tick(self, state, emitter=None, ctx=None):
        if emitter and ctx:
            from vivarium.core import ActionCompleted, ActionInvoked

            node_ctx = ctx.child(self.name, "Action")
            emitter.emit(
                ActionInvoked(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Action",
                    path_in_tree=node_ctx.path,
                )
            )
            emitter.emit(
                ActionCompleted(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Action",
                    path_in_tree=node_ctx.path,
                    result=NodeStatus.SUCCESS,
                )
            )
        return NodeStatus.SUCCESS

    def reset(self):
        pass


@pytest.mark.integration
def test_trace_collector_with_vivarium_tree():
    """TraceCollector should work with a real Vivarium BehaviorTree."""
    from vivarium.core import Action

    class SimpleAction(Action):
        def __init__(self, name: str):
            super().__init__(name)

        def execute(self, state) -> NodeStatus:
            return NodeStatus.SUCCESS

    collector = TraceCollector()
    tree = BehaviorTree(root=SimpleAction("do_thing"), emitter=collector)

    result = tree.tick(State())

    assert result == NodeStatus.SUCCESS
    trace = collector.get_trace()
    assert trace is not None
    assert trace.tick_id == 1
    assert trace.status == "success"
    # Should have action execution
    assert len(trace.executions) == 1
    assert trace.executions[0].node_id == "do_thing"
