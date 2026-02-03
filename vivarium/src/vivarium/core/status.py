"""Node status values for behavior tree execution."""

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
