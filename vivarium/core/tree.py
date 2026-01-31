"""Behavior tree container and execution.

The BehaviorTree class provides a container for behavior tree execution,
wrapping the root node and providing tick counting and state management.
"""

from .node import Node, NodeStatus


class BehaviorTree:
    """Container for behavior tree execution.

    BehaviorTree wraps a root node and provides a high-level interface
    for executing the tree. It tracks the number of ticks and delegates
    execution to the root node.

    Attributes:
        root: The root node of the behavior tree.
        tick_count: Number of times the tree has been ticked.
    """

    def __init__(self, root: Node):
        """Initialize the BehaviorTree with a root node.

        Args:
            root: The root node of the behavior tree.
        """
        self.root = root
        self.tick_count: int = 0

    def tick(self, state) -> NodeStatus:
        """Execute one tick of the behavior tree.

        Increments the tick count and delegates to the root node's tick method.

        Args:
            state: The current state to pass through the tree.

        Returns:
            The status returned by the root node.
        """
        self.tick_count += 1
        return self.root.tick(state)

    def reset(self) -> None:
        """Reset the behavior tree.

        Resets the tick count and calls reset on the root node,
        which propagates to all children.
        """
        self.tick_count = 0
        self.root.reset()
