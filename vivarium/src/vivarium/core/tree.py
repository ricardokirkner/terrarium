"""Behavior tree container and execution.

The BehaviorTree class provides a container for behavior tree execution,
wrapping the root node and providing tick counting and state management.
"""

from .context import ExecutionContext
from .events import Event, EventEmitter, TickCompleted, TickStarted
from .node import Node, NodeStatus


class BehaviorTree:
    """Container for behavior tree execution.

    BehaviorTree wraps a root node and provides a high-level interface
    for executing the tree. It tracks the number of ticks and delegates
    execution to the root node.

    Attributes:
        root: The root node of the behavior tree.
        tick_count: Number of times the tree has been ticked.
        emitter: Optional event emitter for observation.
    """

    def __init__(self, root: Node, emitter: EventEmitter | None = None):
        """Initialize the BehaviorTree with a root node.

        Args:
            root: The root node of the behavior tree.
            emitter: Optional event emitter for observation.
        """
        self.root = root
        self.tick_count: int = 0
        self._emitter = emitter

    def _emit(self, event: Event) -> None:
        """Emit an event if an emitter is configured."""
        if self._emitter is not None:
            self._emitter.emit(event)

    def tick(self, state) -> NodeStatus:
        """Execute one tick of the behavior tree.

        Increments the tick count and delegates to the root node's tick method.
        Emits tick_started and tick_completed events if an emitter is configured.

        Args:
            state: The current state to pass through the tree.

        Returns:
            The status returned by the root node.
        """
        self.tick_count += 1
        self._emit(TickStarted(tick_id=self.tick_count))

        if self._emitter is not None:
            ctx = ExecutionContext(tick_id=self.tick_count, path="")
            result = self.root.tick(state, self._emitter, ctx)
        else:
            result = self.root.tick(state)

        self._emit(TickCompleted(tick_id=self.tick_count, result=result))
        return result

    def reset(self) -> None:
        """Reset the behavior tree traversal state.

        Calls reset on the root node, which propagates to all children.
        This resets internal state like current_index in Sequence/Selector
        nodes, but preserves the tick_count.
        """
        self.root.reset()
