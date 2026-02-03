"""Execution context for tracking tree traversal.

The ExecutionContext tracks the current position in the behavior tree
during execution. It is immutable - creating a child context returns a new instance.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context for tracking execution position.

    Attributes:
        tick_id: Current tick number.
        path: Path to current node (e.g., "root/selector[0]/action[1]").
    """

    tick_id: int
    path: str = ""

    def child(
        self, node_id: str, node_type: str, child_index: int | None = None
    ) -> "ExecutionContext":
        """Create a child context for a nested node.

        Args:
            node_id: The ID of the child node.
            node_type: The type of the node (e.g., "Action", "Sequence").
            child_index: Index of this node in parent's children list (if applicable).

        Returns:
            A new ExecutionContext with the child's path.
        """
        if child_index is not None:
            segment = f"{node_id}[{child_index}]"
        else:
            segment = node_id

        if self.path:
            new_path = f"{self.path}/{segment}"
        else:
            new_path = segment

        return ExecutionContext(tick_id=self.tick_id, path=new_path)
