"""Telemetry data structures for behavior tree observation.

This module provides:
- NodeExecution: Represents a single node execution with timing data
- ExecutionTrace: A complete trace of a behavior tree tick
- TraceCollector: Implements Vivarium's EventEmitter to build traces from events
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from vivarium.core import Event


@dataclass
class NodeExecution:
    """Represents a single node execution event in a behavior tree.

    This dataclass captures telemetry data for node execution, enabling
    observation and analysis of behavior tree performance and decisions.

    Attributes:
        node_id: Unique identifier for the node instance.
        node_name: Human-readable name of the node.
        node_type: Type of node (e.g., "Action", "Condition", "Sequence").
        path_in_tree: Full path to the node (e.g., "root/selector[0]/action[1]").
        timestamp: When the execution completed.
        status: Execution result ("success", "failure", "running").
        duration_ms: Execution duration in milliseconds.
        llm_prompt: Optional LLM prompt (for LLMAction/LLMCondition nodes).
        llm_response: Optional LLM response content.
        llm_reasoning: Optional LLM reasoning/chain-of-thought.
        llm_tokens: Optional token usage dict with prompt/completion/total.
        llm_cost: Optional cost in USD for the LLM call.
        llm_model: Optional model name used for the LLM call.
    """

    node_id: str
    node_name: str
    node_type: str
    path_in_tree: str
    timestamp: datetime
    status: str
    duration_ms: float
    # Optional LLM fields
    llm_prompt: str | None = None
    llm_response: str | None = None
    llm_reasoning: str | None = None
    llm_tokens: dict[str, int] | None = None
    llm_cost: float | None = None
    llm_model: str | None = None

    def __repr__(self) -> str:
        """Return a debug-friendly representation of the node execution."""
        base = (
            f"NodeExecution("
            f"id={self.node_id!r}, "
            f"name={self.node_name!r}, "
            f"type={self.node_type!r}, "
            f"path={self.path_in_tree!r}, "
            f"status={self.status!r}, "
            f"duration={self.duration_ms:.2f}ms"
        )
        if self.llm_prompt:
            base += f", llm=True, tokens={self.llm_tokens}"
        return base + ")"

    @property
    def has_llm_data(self) -> bool:
        """Return True if this execution has LLM data."""
        return self.llm_prompt is not None

    def to_dict(self) -> dict:
        """Convert to a dictionary for serialization."""
        data = {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type,
            "path_in_tree": self.path_in_tree,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "duration_ms": self.duration_ms,
        }
        # Include LLM fields only if present
        if self.llm_prompt is not None:
            data["llm_prompt"] = self.llm_prompt
        if self.llm_response is not None:
            data["llm_response"] = self.llm_response
        if self.llm_reasoning is not None:
            data["llm_reasoning"] = self.llm_reasoning
        if self.llm_tokens is not None:
            data["llm_tokens"] = self.llm_tokens
        if self.llm_cost is not None:
            data["llm_cost"] = self.llm_cost
        if self.llm_model is not None:
            data["llm_model"] = self.llm_model
        return data

    @classmethod
    def from_dict(cls, data: dict) -> NodeExecution:
        """Create from a dictionary."""
        return cls(
            node_id=data["node_id"],
            node_name=data["node_name"],
            node_type=data["node_type"],
            path_in_tree=data["path_in_tree"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=data["status"],
            duration_ms=data["duration_ms"],
            llm_prompt=data.get("llm_prompt"),
            llm_response=data.get("llm_response"),
            llm_reasoning=data.get("llm_reasoning"),
            llm_tokens=data.get("llm_tokens"),
            llm_cost=data.get("llm_cost"),
            llm_model=data.get("llm_model"),
        )


@dataclass
class ExecutionTrace:
    """A complete execution trace from a single behavior tree tick.

    Captures all node executions during a tick, with timing information
    for analysis and visualization.

    Attributes:
        trace_id: Unique identifier for this trace (UUID).
        tick_id: The tick number from the BehaviorTree.
        start_time: When the tick started.
        end_time: When the tick completed.
        status: Final result of the tick ("success", "failure", "running").
        executions: List of node executions in chronological order.
        metadata: Optional metadata for custom data.
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tick_id: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: str = ""
    executions: list[NodeExecution] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert trace to a dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "tick_id": self.tick_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "executions": [e.to_dict() for e in self.executions],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert trace to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionTrace:
        """Create trace from dictionary."""
        return cls(
            trace_id=data["trace_id"],
            tick_id=data["tick_id"],
            start_time=(
                datetime.fromisoformat(data["start_time"])
                if data["start_time"]
                else None
            ),
            end_time=(
                datetime.fromisoformat(data["end_time"]) if data["end_time"] else None
            ),
            status=data["status"],
            executions=[NodeExecution.from_dict(e) for e in data["executions"]],
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> ExecutionTrace:
        """Create trace from JSON string."""
        return cls.from_dict(json.loads(json_str))


class TraceCollector:
    """Collects Vivarium events and builds ExecutionTrace objects.

    Implements the EventEmitter protocol from Vivarium, allowing it to be
    passed to BehaviorTree for event collection.

    Usage:
        collector = TraceCollector()
        tree = BehaviorTree(root=my_tree, emitter=collector)
        tree.tick(state)
        trace = collector.get_trace()

    The collector matches start events (action_invoked, node_entered) with
    end events (action_completed, node_exited, condition_evaluated) using
    path_in_tree to compute execution duration.

    For LLM nodes, the collector can extract LLM execution data from the
    state if provided via set_state().
    """

    def __init__(self):
        self._pending: dict[str, Event] = {}  # path_in_tree -> start event
        self._current_trace: ExecutionTrace | None = None
        self._traces: list[ExecutionTrace] = []
        self._state: dict | None = None  # Reference to state for LLM data extraction

    def set_state(self, state: dict) -> None:
        """Set the state reference for LLM data extraction.

        Call this before tree.tick() to enable LLM data capture.

        Args:
            state: The behavior tree state dict.
        """
        self._state = state

    def emit(self, event: Event) -> None:
        """Receive events from Vivarium and build NodeExecution objects.

        This method implements the EventEmitter protocol.
        """
        match event.event_type:
            case "tick_started":
                self._start_trace(event)
            case "tick_completed":
                self._complete_trace(event)
            case "action_invoked" | "node_entered":
                self._pending[event.path_in_tree] = event
            case "action_completed" | "node_exited":
                self._complete_node(event)
            case "condition_evaluated":
                # Conditions don't have a start event, duration is 0
                self._record_condition(event)

    def _start_trace(self, event: Event) -> None:
        """Start a new trace for this tick."""
        self._current_trace = ExecutionTrace(
            tick_id=event.tick_id,
            start_time=event.timestamp,
        )
        self._pending.clear()

    def _complete_trace(self, event: Event) -> None:
        """Complete the current trace."""
        if self._current_trace is not None:
            self._current_trace.end_time = event.timestamp
            self._current_trace.status = event.payload.get("result", "unknown")
            self._traces.append(self._current_trace)
            self._current_trace = None

    def _complete_node(self, end_event: Event) -> None:
        """Match end event with start event to compute duration."""
        start_event = self._pending.pop(end_event.path_in_tree, None)
        if start_event:
            duration_ms = (
                end_event.timestamp - start_event.timestamp
            ).total_seconds() * 1000
        else:
            duration_ms = 0.0

        # Extract LLM data from state if available
        llm_data = self._extract_llm_data(end_event.node_id)

        execution = NodeExecution(
            node_id=end_event.node_id,
            node_name=end_event.node_id,
            node_type=end_event.node_type,
            path_in_tree=end_event.path_in_tree,
            timestamp=end_event.timestamp,
            status=end_event.payload.get("result", "unknown"),
            duration_ms=duration_ms,
            **llm_data,
        )

        if self._current_trace is not None:
            self._current_trace.executions.append(execution)

    def _record_condition(self, event: Event) -> None:
        """Record a condition evaluation (no start event, instant)."""
        # Convert bool result to status string
        result = event.payload.get("result", False)
        status = "success" if result else "failure"

        # Extract LLM data from state if available
        llm_data = self._extract_llm_data(event.node_id)

        execution = NodeExecution(
            node_id=event.node_id,
            node_name=event.node_id,
            node_type=event.node_type,
            path_in_tree=event.path_in_tree,
            timestamp=event.timestamp,
            status=status,
            duration_ms=0.0,
            **llm_data,
        )

        if self._current_trace is not None:
            self._current_trace.executions.append(execution)

    def _extract_llm_data(self, node_id: str) -> dict:
        """Extract LLM execution data from state for a node.

        LLM nodes store their execution data in state under "_llm_{node_name}".

        Args:
            node_id: The node identifier.

        Returns:
            Dict with LLM fields if found, empty dict otherwise.
        """
        if self._state is None:
            return {}

        llm_key = f"_llm_{node_id}"
        llm_data = self._state.get(llm_key)

        if llm_data is None:
            return {}

        # Handle both LLMExecutionData objects and dicts
        if hasattr(llm_data, "to_dict"):
            data = llm_data.to_dict()
        elif isinstance(llm_data, dict):
            data = llm_data
        else:
            return {}

        return {
            "llm_prompt": data.get("prompt"),
            "llm_response": data.get("response"),
            "llm_reasoning": data.get("reasoning"),
            "llm_tokens": data.get("tokens_used"),
            "llm_cost": data.get("cost"),
            "llm_model": data.get("model"),
        }

    def get_executions(self) -> list[NodeExecution]:
        """Return all executions from completed traces."""
        executions = []
        for trace in self._traces:
            executions.extend(trace.executions)
        return executions

    def get_trace(self) -> ExecutionTrace | None:
        """Return the most recent completed trace, or None."""
        return self._traces[-1] if self._traces else None

    def get_traces(self) -> list[ExecutionTrace]:
        """Return all completed traces."""
        return self._traces.copy()

    def clear(self) -> None:
        """Clear all collected traces and pending events."""
        self._pending.clear()
        self._current_trace = None
        self._traces.clear()
