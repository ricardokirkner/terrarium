from core.node import Node, NodeStatus


class Sequence(Node):
    """A composite node that executes children in order until one fails.

    The Sequence node ticks its children from left to right. If a child returns
    SUCCESS, it moves to the next child. If a child returns FAILURE, the sequence
    immediately fails. If a child returns RUNNING, the sequence returns RUNNING
    and will resume from that child on the next tick.

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

    def tick(self, state) -> NodeStatus:
        """Execute children in order until one fails or returns RUNNING.

        Args:
            state: The current state of the behavior tree.

        Returns:
            FAILURE if any child fails.
            RUNNING if a child is still running.
            SUCCESS if all children succeed.
        """
        while self.current_index < len(self.children):
            child = self.children[self.current_index]
            status = child.tick(state)

            if status == NodeStatus.FAILURE:
                return NodeStatus.FAILURE
            elif status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            elif status == NodeStatus.SUCCESS:
                self.current_index += 1

        return NodeStatus.SUCCESS

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

    def tick(self, state) -> NodeStatus:
        """Try children in order until one succeeds or returns RUNNING.

        Args:
            state: The current state of the behavior tree.

        Returns:
            SUCCESS if any child succeeds.
            RUNNING if a child is still running.
            FAILURE if all children fail.
        """
        while self.current_index < len(self.children):
            child = self.children[self.current_index]
            status = child.tick(state)

            if status == NodeStatus.SUCCESS:
                return NodeStatus.SUCCESS
            elif status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            elif status == NodeStatus.FAILURE:
                self.current_index += 1

        return NodeStatus.FAILURE

    def reset(self):
        """Reset this node and all children to their initial state."""
        self.current_index = 0
        for child in self.children:
            child.reset()
