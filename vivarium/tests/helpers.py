"""Shared test helpers for vivarium tests.

This module provides reusable node implementations for testing behavior trees.
These are intentionally simple implementations that make tests readable and
self-documenting.
"""

from vivarium.core import Action, Condition, Node, NodeStatus

# =============================================================================
# Generic Mock Nodes
# =============================================================================


class MockNode(Node):
    """A mock node that returns a configurable status."""

    def __init__(self, name: str, status: NodeStatus = NodeStatus.SUCCESS):
        self.name = name
        self._status = status
        self.tick_count = 0
        self._reset_called = False

    def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
        self.tick_count += 1
        return self._status

    def reset(self):
        self._reset_called = True
        self.tick_count = 0


class OrderTrackingNode(Node):
    """A node that records its execution order to a shared list."""

    def __init__(self, name: str, execution_order: list[str]):
        self.name = name
        self._execution_order = execution_order

    def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
        self._execution_order.append(self.name)
        return NodeStatus.SUCCESS

    def reset(self):
        pass


# =============================================================================
# Simple Actions
# =============================================================================


class SuccessAction(Action):
    """An action that always returns SUCCESS."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.SUCCESS


class FailureAction(Action):
    """An action that always returns FAILURE."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.FAILURE


class RunningAction(Action):
    """An action that always returns RUNNING."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.RUNNING


# =============================================================================
# State-Modifying Actions
# =============================================================================


class CountingAction(Action):
    """An action that counts how many times it was executed."""

    def __init__(self, name: str):
        super().__init__(name)
        self.execute_count = 0

    def execute(self, state) -> NodeStatus:
        self.execute_count += 1
        return NodeStatus.SUCCESS

    def reset(self):
        self.execute_count = 0


class IncrementAction(Action):
    """An action that increments a counter in state."""

    def __init__(self, name: str, key: str = "counter"):
        super().__init__(name)
        self.key = key

    def execute(self, state) -> NodeStatus:
        state[self.key] = state.get(self.key, 0) + 1
        return NodeStatus.SUCCESS


class SetValueAction(Action):
    """An action that sets a value in state."""

    def __init__(self, name: str, key: str, value):
        super().__init__(name)
        self.key = key
        self.value = value

    def execute(self, state) -> NodeStatus:
        state[self.key] = self.value
        return NodeStatus.SUCCESS


# =============================================================================
# Simple Conditions
# =============================================================================


class TrueCondition(Condition):
    """A condition that always returns True."""

    def evaluate(self, state) -> bool:
        return True


class FalseCondition(Condition):
    """A condition that always returns False."""

    def evaluate(self, state) -> bool:
        return False


# =============================================================================
# State-Checking Conditions
# =============================================================================


class ValueCheckCondition(Condition):
    """A condition that checks if a value in state exceeds a threshold."""

    def __init__(self, name: str, key: str, threshold: float):
        super().__init__(name)
        self.key = key
        self.threshold = threshold

    def evaluate(self, state) -> bool:
        return state.get(self.key, 0) > self.threshold


class HasKeyCondition(Condition):
    """A condition that checks if a key exists in state."""

    def __init__(self, name: str, key: str):
        super().__init__(name)
        self.key = key

    def evaluate(self, state) -> bool:
        return self.key in state
