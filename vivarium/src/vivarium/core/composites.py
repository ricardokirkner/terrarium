from .context import ExecutionContext
from .events import EventEmitter, NodeEntered, NodeExited
from .node import Node
from .status import NodeStatus


def _raise_idle_error(child: Node) -> None:
    """Raise ValueError for a child that returned IDLE."""
    child_name = getattr(child, "name", type(child).__name__)
    raise ValueError(
        f"Node '{child_name}' returned unexpected status {NodeStatus.IDLE}. "
        f"Nodes must return SUCCESS, FAILURE, or RUNNING from tick()."
    )


class Sequence(Node):
    """A composite node that executes children in order until one fails.

    The Sequence node ticks its children from left to right. If a child returns
    SUCCESS, it moves to the next child. If a child returns FAILURE, the sequence
    immediately fails. If a child returns RUNNING, the sequence returns RUNNING
    and will resume from that child on the next tick.

    Note on empty Sequence: Returns SUCCESS (vacuously true - all zero children
    succeeded).

    Attributes:
        name: A unique identifier for this node.
        children: List of child nodes to execute in order.
        current_index: Index of the child currently being executed.
    """

    def __init__(self, name: str, children: list[Node] | None = None):
        """Initialize the Sequence node.

        Args:
            name: A unique identifier for this node.
            children: Optional list of child nodes to execute in order.
        """
        self.name = name
        self.children: list[Node] = children if children is not None else []
        self.current_index: int = 0

    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Execute children in order until one fails or returns RUNNING.

        Args:
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            FAILURE if any child fails.
            RUNNING if a child is still running.
            SUCCESS if all children succeed.

        Raises:
            ValueError: If a child returns IDLE (invalid during execution).
        """
        # Set up context for this node if emitting
        node_ctx = ctx
        if emitter is not None and ctx is not None:
            emitter.emit(
                NodeEntered(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Sequence",
                    path_in_tree=ctx.path,
                )
            )

        def emit_exit(result: NodeStatus) -> NodeStatus:
            if emitter is not None and ctx is not None:
                emitter.emit(
                    NodeExited(
                        tick_id=ctx.tick_id,
                        node_id=self.name,
                        node_type="Sequence",
                        path_in_tree=ctx.path,
                        result=result,
                    )
                )
            return result

        while self.current_index < len(self.children):
            child = self.children[self.current_index]

            # Create child context with position index
            child_ctx = None
            if emitter is not None and node_ctx is not None:
                child_name = getattr(child, "name", type(child).__name__)
                child_type = type(child).__name__
                child_ctx = node_ctx.child(child_name, child_type, self.current_index)

            status = child.tick(state, emitter, child_ctx)

            if status == NodeStatus.FAILURE:
                self.current_index = 0
                return emit_exit(NodeStatus.FAILURE)
            elif status == NodeStatus.RUNNING:
                return emit_exit(NodeStatus.RUNNING)
            elif status == NodeStatus.SUCCESS:
                self.current_index += 1
            else:
                _raise_idle_error(child)

        self.current_index = 0
        return emit_exit(NodeStatus.SUCCESS)

    def reset(self):
        """Reset this node and all children to their initial state."""
        self.current_index = 0
        for child in self.children:
            child.reset()


class Selector(Node):
    """A composite node that tries children until one succeeds.

    The Selector node ticks its children from left to right. If a child returns
    FAILURE, it moves to the next child. If a child returns SUCCESS, the selector
    immediately succeeds. If a child returns RUNNING, the selector returns RUNNING
    and will resume from that child on the next tick.

    Note on empty Selector: Returns FAILURE (no child succeeded).

    Attributes:
        name: A unique identifier for this node.
        children: List of child nodes to try in order.
        current_index: Index of the child currently being executed.
    """

    def __init__(self, name: str, children: list[Node] | None = None):
        """Initialize the Selector node.

        Args:
            name: A unique identifier for this node.
            children: Optional list of child nodes to try in order.
        """
        self.name = name
        self.children: list[Node] = children if children is not None else []
        self.current_index: int = 0

    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Try children in order until one succeeds or returns RUNNING.

        Args:
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            SUCCESS if any child succeeds.
            RUNNING if a child is still running.
            FAILURE if all children fail.

        Raises:
            ValueError: If a child returns IDLE (invalid during execution).
        """
        # Set up context for this node if emitting
        node_ctx = ctx
        if emitter is not None and ctx is not None:
            emitter.emit(
                NodeEntered(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Selector",
                    path_in_tree=ctx.path,
                )
            )

        def emit_exit(result: NodeStatus) -> NodeStatus:
            if emitter is not None and ctx is not None:
                emitter.emit(
                    NodeExited(
                        tick_id=ctx.tick_id,
                        node_id=self.name,
                        node_type="Selector",
                        path_in_tree=ctx.path,
                        result=result,
                    )
                )
            return result

        while self.current_index < len(self.children):
            child = self.children[self.current_index]

            # Create child context with position index
            child_ctx = None
            if emitter is not None and node_ctx is not None:
                child_name = getattr(child, "name", type(child).__name__)
                child_type = type(child).__name__
                child_ctx = node_ctx.child(child_name, child_type, self.current_index)

            status = child.tick(state, emitter, child_ctx)

            if status == NodeStatus.SUCCESS:
                self.current_index = 0
                return emit_exit(NodeStatus.SUCCESS)
            elif status == NodeStatus.RUNNING:
                return emit_exit(NodeStatus.RUNNING)
            elif status == NodeStatus.FAILURE:
                self.current_index += 1
            else:
                _raise_idle_error(child)

        self.current_index = 0
        return emit_exit(NodeStatus.FAILURE)

    def reset(self):
        """Reset this node and all children to their initial state."""
        self.current_index = 0
        for child in self.children:
            child.reset()


class Parallel(Node):
    """A composite node that executes all children simultaneously.

    The Parallel node ticks all its children on every tick until they complete.
    Once a child returns SUCCESS or FAILURE, it is not ticked again until the
    Parallel node is reset. This prevents side effects from being executed
    multiple times.

    It uses thresholds to determine success or failure based on how many
    children succeed or fail.

    Note on empty Parallel: Returns SUCCESS (vacuously true - all zero children
    succeeded).

    Attributes:
        name: A unique identifier for this node.
        children: List of child nodes to execute in parallel.
        success_threshold: Number of children that must succeed for this node
            to succeed. If None, all children must succeed.
        failure_threshold: Number of children that must fail for this node
            to fail. If None, all children must fail.
    """

    def __init__(
        self,
        name: str,
        children: list[Node] | None = None,
        success_threshold: int | None = None,
        failure_threshold: int | None = None,
    ):
        """Initialize the Parallel node.

        Args:
            name: A unique identifier for this node.
            children: Optional list of child nodes to execute in parallel.
            success_threshold: Number of children that must succeed for SUCCESS.
                Defaults to all children (None).
            failure_threshold: Number of children that must fail for FAILURE.
                Defaults to all children (None).
        """
        self.name = name
        self.children: list[Node] = children if children is not None else []
        self.success_threshold = success_threshold
        self.failure_threshold = failure_threshold
        self._child_statuses: list[NodeStatus | None] = [None] * len(self.children)

    def _ensure_status_list_size(self):
        """Ensure _child_statuses matches children length for dynamic children."""
        while len(self._child_statuses) < len(self.children):
            self._child_statuses.append(None)

    def _tick_child(
        self,
        index: int,
        child: Node,
        state,
        emitter: "EventEmitter | None" = None,
        node_ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Tick a child if not already completed, updating cached status.

        Args:
            index: Index of the child in the children list.
            child: The child node to tick.
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            node_ctx: Optional execution context for this Parallel node.

        Returns:
            The child's status (cached if already completed).

        Raises:
            ValueError: If the child returns IDLE.
        """
        cached = self._child_statuses[index]
        if cached in (NodeStatus.SUCCESS, NodeStatus.FAILURE):
            return cached  # type: ignore[return-value]

        status = child.tick(state, emitter, node_ctx)
        self._child_statuses[index] = status

        if status == NodeStatus.IDLE:
            _raise_idle_error(child)
        return status

    def _evaluate_thresholds(
        self, success_count: int, failure_count: int, running_count: int
    ) -> NodeStatus:
        """Evaluate counts against thresholds to determine result.

        Args:
            success_count: Number of children that succeeded.
            failure_count: Number of children that failed.
            running_count: Number of children still running.

        Returns:
            The resulting status based on threshold evaluation.
        """
        effective_success = self.success_threshold or len(self.children)
        effective_failure = self.failure_threshold or len(self.children)

        if success_count >= effective_success:
            return NodeStatus.SUCCESS
        if failure_count >= effective_failure:
            return NodeStatus.FAILURE
        if running_count > 0:
            return NodeStatus.RUNNING
        return NodeStatus.FAILURE

    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Execute all children and evaluate based on thresholds.

        Children that have already completed (returned SUCCESS or FAILURE) are
        not ticked again. This prevents actions with side effects from being
        executed multiple times.

        Args:
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            SUCCESS if success_threshold children succeed.
            FAILURE if failure_threshold children fail.
            RUNNING if thresholds are not yet met and children are still running.

        Raises:
            ValueError: If a child returns IDLE (invalid during execution).
        """
        # Set up context for this node if emitting
        node_ctx = ctx
        if emitter is not None and ctx is not None:
            emitter.emit(
                NodeEntered(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Parallel",
                    path_in_tree=ctx.path,
                )
            )

        def emit_exit(result: NodeStatus) -> NodeStatus:
            if emitter is not None and ctx is not None:
                emitter.emit(
                    NodeExited(
                        tick_id=ctx.tick_id,
                        node_id=self.name,
                        node_type="Parallel",
                        path_in_tree=ctx.path,
                        result=result,
                    )
                )
            return result

        if not self.children:
            return emit_exit(NodeStatus.SUCCESS)

        self._ensure_status_list_size()

        success_count = 0
        failure_count = 0
        running_count = 0

        for i, child in enumerate(self.children):
            child_ctx = None
            if emitter is not None and node_ctx is not None:
                child_name = getattr(child, "name", type(child).__name__)
                child_type = type(child).__name__
                child_ctx = node_ctx.child(child_name, child_type, i)
            status = self._tick_child(i, child, state, emitter, child_ctx)
            if status == NodeStatus.SUCCESS:
                success_count += 1
            elif status == NodeStatus.FAILURE:
                failure_count += 1
            else:
                running_count += 1

        result = self._evaluate_thresholds(success_count, failure_count, running_count)
        return emit_exit(result)

    def reset(self):
        """Reset this node and all children to their initial state."""
        self._child_statuses = [None] * len(self.children)
        for child in self.children:
            child.reset()
