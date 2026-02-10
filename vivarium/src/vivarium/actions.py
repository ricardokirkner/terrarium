"""Action nodes for behavior trees.

Actions are leaf nodes that perform work and can modify the world state.
They represent the "doing" part of a behavior tree, as opposed to Conditions
which only check state without modifying it.

Key differences between Actions and Conditions:
- Actions: Perform work, may have side effects, can modify state
  Examples: MoveToTarget, Attack, PlayAnimation, SendMessage
- Conditions: Read-only checks, no side effects, should not modify state
  Examples: IsTargetInRange, HasEnoughHealth, IsPlayerVisible

Both Actions and Conditions are leaf nodes (they have no children), but they
serve different purposes in the behavior tree structure.
"""

from abc import abstractmethod
from typing import TYPE_CHECKING

from .events import (
    ActionCompleted,
    ActionInvoked,
    EventEmitter,
    NodeEntered,
    NodeExited,
)

if TYPE_CHECKING:
    from .context import ExecutionContext
from .node import Node
from .status import NodeStatus


class Action(Node):
    """Abstract base class for action nodes in a behavior tree.

    Actions are leaf nodes that perform work. They may modify the world state
    and can return SUCCESS, FAILURE, or RUNNING depending on the outcome of
    their execution.

    Subclasses must implement the execute() method which contains the actual
    action logic. The tick() method is already implemented to call execute().

    Attributes:
        name: A unique identifier for this action.
    """

    def __init__(self, name: str):
        """Initialize the Action with a name.

        Args:
            name: A unique identifier for this action.
        """
        self.name = name

    @abstractmethod
    def execute(self, state) -> NodeStatus:
        """Execute the action's logic.

        This method should contain the actual work performed by the action.
        It may modify the state or have other side effects.

        Args:
            state: The current state of the behavior tree.

        Returns:
            SUCCESS if the action completed successfully.
            FAILURE if the action failed.
            RUNNING if the action is still in progress and needs more ticks.
        """
        pass  # pragma: no cover

    def tick(
        self,
        state,
        emitter: "EventEmitter | None" = None,
        ctx: "ExecutionContext | None" = None,
    ) -> NodeStatus:
        """Execute one tick of this action.

        Delegates to the execute() method which subclasses must implement.
        Emits action_invoked and action_completed events if an emitter is provided.

        Args:
            state: The current state of the behavior tree.
            emitter: Optional event emitter for observation.
            ctx: Optional execution context for tracking position in tree.

        Returns:
            The result of execute().
        """
        if emitter is not None and ctx is not None:
            emitter.emit(
                NodeEntered(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Action",
                    path_in_tree=ctx.path,
                )
            )
            emitter.emit(
                ActionInvoked(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Action",
                    path_in_tree=ctx.path,
                )
            )
            result = self.execute(state)
            emitter.emit(
                ActionCompleted(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Action",
                    path_in_tree=ctx.path,
                    result=result,
                )
            )
            emitter.emit(
                NodeExited(
                    tick_id=ctx.tick_id,
                    node_id=self.name,
                    node_type="Action",
                    path_in_tree=ctx.path,
                    result=result,
                )
            )
            return result

        return self.execute(state)

    def reset(self):
        """Reset this action to its initial state.

        Default implementation does nothing. Subclasses can override this
        to reset any internal state they maintain.
        """
        pass  # pragma: no cover
