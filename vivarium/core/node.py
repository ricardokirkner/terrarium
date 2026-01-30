from abc import ABC, abstractmethod
from enum import Enum


class NodeStatus(Enum):
    """Status values returned by behavior tree nodes after a tick.

    Attributes:
        SUCCESS: The node completed its task successfully.
        FAILURE: The node failed to complete its task.
        RUNNING: The node is still executing and needs more ticks to complete.
        IDLE: The node has not been ticked yet or has been reset.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"
    IDLE = "idle"


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
        pass

    @abstractmethod
    def tick(self, state) -> NodeStatus:
        """Execute one tick of this node's behavior.

        Args:
            state: The current state of the behavior tree, passed down from the root.

        Returns:
            NodeStatus indicating the result of this tick (SUCCESS, FAILURE, RUNNING,
            or IDLE).
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset this node to its initial state.

        Called when the node needs to be restarted, typically when a parent
        node restarts its children or when the tree is reset.
        """
        pass
