from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .status import NodeStatus

if TYPE_CHECKING:
    from .context import ExecutionContext
    from .events import EventEmitter


class Node(ABC):
    """Abstract base class for behavior tree nodes.

    All nodes in a behavior tree must inherit from this class and implement
    the required abstract methods: __init__, tick, and reset.
    """

    @abstractmethod
    def __init__(self, name: str):
        """Initialize the node with a name.

        Args:
            name: A unique identifier for this node.
        """
        pass  # pragma: no cover

    @abstractmethod
    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Execute one tick of this node's behavior.

        Args:
            state: The current state of the behavior tree, passed down from the root.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            NodeStatus indicating the result of this tick (SUCCESS, FAILURE, RUNNING,
            or IDLE).
        """
        pass  # pragma: no cover

    @abstractmethod
    def reset(self):
        """Reset this node to its initial state.

        Called when the node needs to be restarted, typically when a parent
        node restarts its children or when the tree is reset.
        """
        pass  # pragma: no cover
