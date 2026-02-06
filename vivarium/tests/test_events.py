"""Tests for event types."""

from vivarium.core import NodeStatus
from vivarium.core.events import (
    ActionCompleted,
    ActionInvoked,
    ConditionEvaluated,
    Event,
    EventEmitter,
    ListEventEmitter,
    NodeEntered,
    NodeExited,
    TickCompleted,
    TickStarted,
)


def test_event_has_required_fields():
    """Event should have required fields per Event Boundary v0."""
    event = Event(
        event_type="test_event",
        tick_id=1,
        node_id="test_node",
        node_type="Action",
        path_in_tree="root/test_node",
    )
    assert event.event_type == "test_event"
    assert event.tick_id == 1
    assert event.node_id == "test_node"
    assert event.node_type == "Action"
    assert event.path_in_tree == "root/test_node"
    assert event.timestamp is not None
    assert event.payload == {}


def test_tick_started_event():
    """TickStarted should have tick_id."""
    event = TickStarted(tick_id=1)
    assert event.event_type == "tick_started"
    assert event.tick_id == 1
    # Tick events don't have node context
    assert event.node_id == ""
    assert event.node_type == ""
    assert event.path_in_tree == ""


def test_tick_completed_event():
    """TickCompleted should have tick_id and result status."""
    event = TickCompleted(tick_id=1, result=NodeStatus.SUCCESS)
    assert event.event_type == "tick_completed"
    assert event.payload["result"] == "success"


def test_node_entered_event():
    """NodeEntered should have node context."""
    event = NodeEntered(
        tick_id=1,
        node_id="attack",
        node_type="Action",
        path_in_tree="root/selector[0]/attack",
    )
    assert event.event_type == "node_entered"


def test_node_exited_event():
    """NodeExited should have node context and result."""
    event = NodeExited(
        tick_id=1,
        node_id="attack",
        node_type="Action",
        path_in_tree="root/selector[0]/attack",
        result=NodeStatus.SUCCESS,
    )
    assert event.event_type == "node_exited"
    assert event.payload["result"] == "success"


def test_condition_evaluated_event():
    """ConditionEvaluated should have condition name and boolean result."""
    event = ConditionEvaluated(
        tick_id=1,
        node_id="is_low_health",
        node_type="Condition",
        path_in_tree="root/sequence[0]/is_low_health",
        result=True,
    )
    assert event.event_type == "condition_evaluated"
    assert event.payload["result"] is True


def test_action_invoked_event():
    """ActionInvoked should have action name."""
    event = ActionInvoked(
        tick_id=1,
        node_id="heal",
        node_type="Action",
        path_in_tree="root/sequence[0]/heal",
    )
    assert event.event_type == "action_invoked"


def test_action_completed_event():
    """ActionCompleted should have action name and outcome."""
    event = ActionCompleted(
        tick_id=1,
        node_id="heal",
        node_type="Action",
        path_in_tree="root/sequence[0]/heal",
        result=NodeStatus.SUCCESS,
    )
    assert event.event_type == "action_completed"
    assert event.payload["result"] == "success"


def test_event_emitter_protocol():
    """EventEmitter should be a Protocol with emit method."""

    class MockEmitter:
        def __init__(self):
            self.events = []

        def emit(self, event: Event) -> None:
            self.events.append(event)

    emitter = MockEmitter()
    event = TickStarted(tick_id=1)
    emitter.emit(event)

    assert len(emitter.events) == 1
    assert emitter.events[0] == event

    # Verify it satisfies the protocol
    def accepts_emitter(e: EventEmitter) -> None:
        pass

    accepts_emitter(emitter)  # Should not raise


def test_list_event_emitter():
    """ListEventEmitter should collect events in a list."""
    emitter = ListEventEmitter()
    event1 = TickStarted(tick_id=1)
    event2 = TickCompleted(tick_id=1, result=NodeStatus.SUCCESS)

    emitter.emit(event1)
    emitter.emit(event2)

    assert len(emitter.events) == 2
    assert emitter.events[0] == event1
    assert emitter.events[1] == event2


def test_list_event_emitter_clear():
    """ListEventEmitter.clear() should remove all events."""
    emitter = ListEventEmitter()
    emitter.emit(TickStarted(tick_id=1))
    emitter.clear()
    assert len(emitter.events) == 0


def test_events_exported_from_core():
    """Event types should be importable from vivarium.core."""
    from vivarium.core import (
        ActionCompleted,
        ActionInvoked,
        ConditionEvaluated,
        Event,
        EventEmitter,
        ListEventEmitter,
        NodeEntered,
        NodeExited,
        TickCompleted,
        TickStarted,
    )

    # Just verify imports work
    assert Event is not None
    assert EventEmitter is not None
    assert ListEventEmitter is not None
    assert TickStarted is not None
    assert TickCompleted is not None
    assert NodeEntered is not None
    assert NodeExited is not None
    assert ConditionEvaluated is not None
    assert ActionInvoked is not None
    assert ActionCompleted is not None
