"""Decorator nodes for behavior trees.

Decorators are nodes with a single child that modify the child's behavior
or result. They are a standard behavior tree pattern for adding control
flow logic without modifying the child node itself.

Common uses:
- Inverter: Negates the child's result (SUCCESS <-> FAILURE)
- Repeater: Repeats the child a fixed number of times or indefinitely
- RetryUntilSuccess: Retries a failing child with optional attempt limits
"""

from .context import ExecutionContext
from .events import EventEmitter, NodeEntered, NodeExited
from .node import Node
from .status import NodeStatus


class Decorator(Node):
    """Abstract base class for decorator nodes.

    A decorator wraps a single child node and modifies its behavior or
    result. Subclasses override tick() to implement the decoration logic.

    Attributes:
        name: A unique identifier for this node.
        child: The single child node being decorated.
    """

    def __init__(self, name: str, child: Node):
        """Initialize the decorator with a name and child node.

        Args:
            name: A unique identifier for this node.
            child: The child node to decorate.
        """
        self.name = name
        self.child = child

    def _emit_entered(
        self,
        node_type: str,
        emitter: "EventEmitter | None",
        ctx: "ExecutionContext | None",
    ) -> None:
        """Emit NodeEntered event.

        Args:
            node_type: Type name for this decorator (e.g., "Inverter").
            emitter: Optional event emitter.
            ctx: Optional execution context (already contains this node's path).
        """
        if emitter is not None and ctx is not None:
            emitter.emit(
                NodeEntered(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type=node_type,
                    path_in_tree=ctx.path,
                )
            )

    def _emit_exited(
        self,
        node_type: str,
        result: NodeStatus,
        emitter: "EventEmitter | None",
        ctx: "ExecutionContext | None",
    ) -> None:
        """Emit NodeExited event.

        Args:
            node_type: Type name for this decorator.
            result: The final status of this node.
            emitter: Optional event emitter.
            ctx: Optional execution context (already contains this node's path).
        """
        if emitter is not None and ctx is not None:
            emitter.emit(
                NodeExited(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type=node_type,
                    path_in_tree=ctx.path,
                    result=result,
                )
            )

    def _child_ctx(
        self,
        emitter: "EventEmitter | None",
        ctx: "ExecutionContext | None",
    ) -> "ExecutionContext | None":
        """Create context for the child node.

        Args:
            emitter: Optional event emitter.
            ctx: This decorator's execution context.

        Returns:
            A child context with the child's name in the path, or None.
        """
        if emitter is not None and ctx is not None:
            child_name = getattr(self.child, "name", type(self.child).__name__)
            child_type = type(self.child).__name__
            return ctx.child(child_name, child_type)
        return None

    def reset(self):
        """Reset this node and the child to initial state."""
        self.child.reset()


class Inverter(Decorator):
    """Inverts the child's result.

    SUCCESS becomes FAILURE, FAILURE becomes SUCCESS.
    RUNNING passes through unchanged.

    This is useful for negating conditions or flipping the logic of
    an action's success/failure semantics.
    """

    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Tick the child and invert its result.

        Args:
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            FAILURE if child returns SUCCESS.
            SUCCESS if child returns FAILURE.
            RUNNING if child returns RUNNING.
        """
        self._emit_entered("Inverter", emitter, ctx)

        child_status = self.child.tick(state, emitter, self._child_ctx(emitter, ctx))

        if child_status == NodeStatus.SUCCESS:
            result = NodeStatus.FAILURE
        elif child_status == NodeStatus.FAILURE:
            result = NodeStatus.SUCCESS
        else:
            result = child_status

        self._emit_exited("Inverter", result, emitter, ctx)
        return result


class Repeater(Decorator):
    """Repeats the child a fixed number of times or indefinitely.

    If max_repeats is None, repeats indefinitely (returns RUNNING after
    each successful child tick). If max_repeats is set, repeats up to
    that many times and returns SUCCESS when all repetitions complete.

    If the child returns FAILURE at any point, the Repeater immediately
    returns FAILURE. If the child returns RUNNING, the Repeater returns
    RUNNING and will resume on the next tick.

    Attributes:
        name: A unique identifier for this node.
        child: The child node to repeat.
        max_repeats: Maximum number of repetitions, or None for infinite.
        current_count: Number of completed repetitions so far.
    """

    def __init__(self, name: str, child: Node, max_repeats: int | None = None):
        """Initialize the Repeater.

        Args:
            name: A unique identifier for this node.
            child: The child node to repeat.
            max_repeats: Maximum repetitions. None means infinite.
        """
        super().__init__(name, child)
        self.max_repeats = max_repeats
        self.current_count: int = 0

    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Tick the child repeatedly.

        Within a single tick, the child is executed once. If it succeeds,
        the repeat counter increments. The Repeater returns RUNNING until
        all repetitions are done (finite) or indefinitely (infinite).

        Args:
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            FAILURE if the child fails.
            RUNNING if the child is running or more repetitions remain.
            SUCCESS if max_repeats is reached.
        """
        self._emit_entered("Repeater", emitter, ctx)

        child_status = self.child.tick(state, emitter, self._child_ctx(emitter, ctx))

        if child_status == NodeStatus.FAILURE:
            result = NodeStatus.FAILURE
            self.current_count = 0
            self._emit_exited("Repeater", result, emitter, ctx)
            return result

        if child_status == NodeStatus.RUNNING:
            result = NodeStatus.RUNNING
            self._emit_exited("Repeater", result, emitter, ctx)
            return result

        # Child succeeded
        self.current_count += 1
        self.child.reset()

        if self.max_repeats is not None and self.current_count >= self.max_repeats:
            result = NodeStatus.SUCCESS
            self.current_count = 0
            self._emit_exited("Repeater", result, emitter, ctx)
            return result

        # More repetitions needed
        result = NodeStatus.RUNNING
        self._emit_exited("Repeater", result, emitter, ctx)
        return result

    def reset(self):
        """Reset this node and child to initial state."""
        self.current_count = 0
        super().reset()


class RetryUntilSuccess(Decorator):
    """Retries the child until it succeeds, with optional max attempts.

    Each tick executes the child once. If it fails, the retry counter
    increments and the child is reset for the next attempt. If max_attempts
    is set and exhausted, returns FAILURE.

    If the child returns RUNNING, the RetryUntilSuccess returns RUNNING
    without incrementing the attempt counter.

    Attributes:
        name: A unique identifier for this node.
        child: The child node to retry.
        max_attempts: Maximum number of attempts, or None for unlimited.
        current_attempts: Number of attempts so far.
    """

    def __init__(self, name: str, child: Node, max_attempts: int | None = None):
        """Initialize RetryUntilSuccess.

        Args:
            name: A unique identifier for this node.
            child: The child node to retry.
            max_attempts: Maximum attempts. None means unlimited.
        """
        super().__init__(name, child)
        self.max_attempts = max_attempts
        self.current_attempts: int = 0

    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Tick the child, retrying on failure.

        Args:
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            SUCCESS if the child succeeds.
            RUNNING if the child failed but more attempts remain, or
                if the child returned RUNNING.
            FAILURE if max_attempts is exhausted.
        """
        self._emit_entered("RetryUntilSuccess", emitter, ctx)

        child_status = self.child.tick(state, emitter, self._child_ctx(emitter, ctx))

        if child_status == NodeStatus.SUCCESS:
            result = NodeStatus.SUCCESS
            self.current_attempts = 0
            self._emit_exited("RetryUntilSuccess", result, emitter, ctx)
            return result

        if child_status == NodeStatus.RUNNING:
            result = NodeStatus.RUNNING
            self._emit_exited("RetryUntilSuccess", result, emitter, ctx)
            return result

        # Child failed
        self.current_attempts += 1
        self.child.reset()

        if self.max_attempts is not None and self.current_attempts >= self.max_attempts:
            result = NodeStatus.FAILURE
            self.current_attempts = 0
            self._emit_exited("RetryUntilSuccess", result, emitter, ctx)
            return result

        # More attempts available
        result = NodeStatus.RUNNING
        self._emit_exited("RetryUntilSuccess", result, emitter, ctx)
        return result

    def reset(self):
        """Reset this node and child to initial state."""
        self.current_attempts = 0
        super().reset()
