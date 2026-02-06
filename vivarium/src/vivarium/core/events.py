"""Event types for behavior tree observation.

Events describe behavior tree meaning, not implementation details.
They are emitted by Vivarium and consumed by external tools like Treehouse.

This module implements Event Boundary v0 as defined in docs/event-boundary.md.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .status import NodeStatus


class EventEmitter(Protocol):
    """Protocol for objects that can receive events.

    This is a structural protocol - any object with an emit(Event) method
    satisfies it. This allows observers to be implemented in any way
    (logging, streaming, buffering, etc.) without Vivarium knowing the details.
    """

    def emit(self, event: "Event") -> None:
        """Emit an event. Must not raise exceptions."""
        ...


def _status_to_str(status: NodeStatus) -> str:
    """Convert NodeStatus to lowercase string for payload."""
    return status.value


def _now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Event:
    """Base event with required fields per Event Boundary v0.

    All events must include these fields to allow observers to:
    - Reconstruct structure
    - Preserve causality
    - Correlate events across time

    Subclasses may override the payload property to compute a dict from
    their typed fields (e.g., result status). The base implementation
    returns an empty dict.
    """

    event_type: str
    tick_id: int
    node_id: str
    node_type: str
    path_in_tree: str
    timestamp: datetime = field(default_factory=_now)

    @property
    def payload(self) -> dict[str, Any]:
        """Event-specific data as a dict for serialization."""
        return {}


@dataclass(frozen=True)
class TickStarted(Event):
    """Emitted when a tick begins."""

    tick_id: int = field(default=0)
    event_type: str = field(default="tick_started", init=False)
    node_id: str = field(default="", init=False)
    node_type: str = field(default="", init=False)
    path_in_tree: str = field(default="", init=False)

    def __init__(self, tick_id: int):
        object.__setattr__(self, "tick_id", tick_id)
        object.__setattr__(self, "event_type", "tick_started")
        object.__setattr__(self, "node_id", "")
        object.__setattr__(self, "node_type", "")
        object.__setattr__(self, "path_in_tree", "")
        object.__setattr__(self, "timestamp", _now())


@dataclass(frozen=True)
class TickCompleted(Event):
    """Emitted when a tick ends."""

    tick_id: int = field(default=0)
    result: NodeStatus = field(default=NodeStatus.SUCCESS)
    event_type: str = field(default="tick_completed", init=False)
    node_id: str = field(default="", init=False)
    node_type: str = field(default="", init=False)
    path_in_tree: str = field(default="", init=False)

    def __init__(self, tick_id: int, result: NodeStatus):
        object.__setattr__(self, "tick_id", tick_id)
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "event_type", "tick_completed")
        object.__setattr__(self, "node_id", "")
        object.__setattr__(self, "node_type", "")
        object.__setattr__(self, "path_in_tree", "")
        object.__setattr__(self, "timestamp", _now())

    @property
    def payload(self) -> dict[str, Any]:
        return {"result": _status_to_str(self.result)}


@dataclass(frozen=True)
class NodeEntered(Event):
    """Emitted when execution enters a node."""

    tick_id: int = field(default=0)
    node_id: str = field(default="")
    node_type: str = field(default="")
    path_in_tree: str = field(default="")
    event_type: str = field(default="node_entered", init=False)

    def __init__(self, tick_id: int, node_id: str, node_type: str, path_in_tree: str):
        object.__setattr__(self, "tick_id", tick_id)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "node_type", node_type)
        object.__setattr__(self, "path_in_tree", path_in_tree)
        object.__setattr__(self, "event_type", "node_entered")
        object.__setattr__(self, "timestamp", _now())


@dataclass(frozen=True)
class NodeExited(Event):
    """Emitted when execution exits a node with a result."""

    tick_id: int = field(default=0)
    node_id: str = field(default="")
    node_type: str = field(default="")
    path_in_tree: str = field(default="")
    result: NodeStatus = field(default=NodeStatus.SUCCESS)
    event_type: str = field(default="node_exited", init=False)

    def __init__(
        self,
        tick_id: int,
        node_id: str,
        node_type: str,
        path_in_tree: str,
        result: NodeStatus,
    ):
        object.__setattr__(self, "tick_id", tick_id)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "node_type", node_type)
        object.__setattr__(self, "path_in_tree", path_in_tree)
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "event_type", "node_exited")
        object.__setattr__(self, "timestamp", _now())

    @property
    def payload(self) -> dict[str, Any]:
        return {"result": _status_to_str(self.result)}


@dataclass(frozen=True)
class ConditionEvaluated(Event):
    """Emitted when a condition is evaluated."""

    tick_id: int = field(default=0)
    node_id: str = field(default="")
    node_type: str = field(default="")
    path_in_tree: str = field(default="")
    result: bool = field(default=False)
    event_type: str = field(default="condition_evaluated", init=False)

    def __init__(
        self,
        tick_id: int,
        node_id: str,
        node_type: str,
        path_in_tree: str,
        result: bool,
    ):
        object.__setattr__(self, "tick_id", tick_id)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "node_type", node_type)
        object.__setattr__(self, "path_in_tree", path_in_tree)
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "event_type", "condition_evaluated")
        object.__setattr__(self, "timestamp", _now())

    @property
    def payload(self) -> dict[str, Any]:
        return {"result": self.result}


@dataclass(frozen=True)
class ActionInvoked(Event):
    """Emitted when an action begins execution."""

    tick_id: int = field(default=0)
    node_id: str = field(default="")
    node_type: str = field(default="")
    path_in_tree: str = field(default="")
    event_type: str = field(default="action_invoked", init=False)

    def __init__(self, tick_id: int, node_id: str, node_type: str, path_in_tree: str):
        object.__setattr__(self, "tick_id", tick_id)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "node_type", node_type)
        object.__setattr__(self, "path_in_tree", path_in_tree)
        object.__setattr__(self, "event_type", "action_invoked")
        object.__setattr__(self, "timestamp", _now())


@dataclass(frozen=True)
class ActionCompleted(Event):
    """Emitted when an action completes."""

    tick_id: int = field(default=0)
    node_id: str = field(default="")
    node_type: str = field(default="")
    path_in_tree: str = field(default="")
    result: NodeStatus = field(default=NodeStatus.SUCCESS)
    event_type: str = field(default="action_completed", init=False)

    def __init__(
        self,
        tick_id: int,
        node_id: str,
        node_type: str,
        path_in_tree: str,
        result: NodeStatus,
    ):
        object.__setattr__(self, "tick_id", tick_id)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "node_type", node_type)
        object.__setattr__(self, "path_in_tree", path_in_tree)
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "event_type", "action_completed")
        object.__setattr__(self, "timestamp", _now())

    @property
    def payload(self) -> dict[str, Any]:
        return {"result": _status_to_str(self.result)}


class ListEventEmitter:
    """A simple event emitter that collects events in a list.

    Useful for testing and debugging. Not thread-safe.
    """

    def __init__(self):
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        """Append event to the list."""
        self.events.append(event)

    def clear(self) -> None:
        """Remove all collected events."""
        self.events.clear()
