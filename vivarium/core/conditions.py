"""Condition nodes for behavior trees.

Conditions are leaf nodes that check state without modifying it.
They represent the "checking" part of a behavior tree, as opposed to Actions
which perform work and may have side effects.

Key differences between Conditions and Actions:
- Conditions: Read-only checks, no side effects, should not modify state
  Examples: IsTargetInRange, HasEnoughHealth, IsPlayerVisible
- Actions: Perform work, may have side effects, can modify state
  Examples: MoveToTarget, Attack, PlayAnimation, SendMessage

Conditions never return RUNNING - they always complete immediately with
either SUCCESS (condition is true) or FAILURE (condition is false).
"""

from abc import abstractmethod

from core.node import Node, NodeStatus


class Condition(Node):
    """Abstract base class for condition nodes in a behavior tree.

    Conditions are leaf nodes that check state without modifying it.
    They always complete immediately, returning SUCCESS if the condition
    is true or FAILURE if false. Conditions never return RUNNING.

    Subclasses must implement the evaluate() method which contains the
    condition logic. The tick() method is already implemented to call
    evaluate() and convert the boolean result to SUCCESS/FAILURE.

    Attributes:
        name: A unique identifier for this condition.
    """

    def __init__(self, name: str):
        """Initialize the Condition with a name.

        Args:
            name: A unique identifier for this condition.
        """
        self.name = name

    @abstractmethod
    def evaluate(self, state) -> bool:
        """Evaluate the condition.

        This method should check state without modifying it.
        It should be a pure read-only operation with no side effects.

        Args:
            state: The current state of the behavior tree.

        Returns:
            True if the condition is satisfied, False otherwise.
        """
        pass  # pragma: no cover

    def tick(self, state) -> NodeStatus:
        """Execute one tick of this condition.

        Calls evaluate() and converts the boolean result to a NodeStatus.

        Args:
            state: The current state of the behavior tree.

        Returns:
            SUCCESS if evaluate() returns True.
            FAILURE if evaluate() returns False.
        """
        return NodeStatus.SUCCESS if self.evaluate(state) else NodeStatus.FAILURE

    def reset(self):
        """Reset this condition to its initial state.

        Default implementation does nothing. Conditions typically don't
        maintain internal state, but subclasses can override if needed.
        """
        pass  # pragma: no cover
