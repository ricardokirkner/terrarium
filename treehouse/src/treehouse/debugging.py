"""Debugging support for behavior trees.

This module provides debugging capabilities like breakpoints, stepping,
and pause/resume for behavior tree execution.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from vivarium import BehaviorTree, NodeStatus


class DebuggerCommand(str, Enum):
    """Commands that can be sent to the debugger."""

    PAUSE = "pause"
    RESUME = "resume"
    STEP = "step"
    SET_BREAKPOINT = "set_breakpoint"
    CLEAR_BREAKPOINT = "clear_breakpoint"
    CLEAR_ALL_BREAKPOINTS = "clear_all_breakpoints"


@dataclass
class BreakpointConfig:
    """Configuration for a breakpoint."""

    node_path: str
    """The path to the node where the breakpoint is set."""

    condition: Callable[[Any], bool] | None = None
    """Optional condition function. Breakpoint only triggers if this returns True."""

    hit_count: int = 0
    """Number of times this breakpoint has been hit."""


class DebuggerTree:
    """Behavior tree wrapper with debugging support.

    This class wraps a Vivarium BehaviorTree and adds debugging capabilities
    such as breakpoints, stepping through execution, and pause/resume.

    Attributes:
        tree: The wrapped BehaviorTree instance.
        breakpoints: Dictionary mapping node paths to breakpoint configurations.
        paused: Whether execution is currently paused.
        step_mode: Whether to pause after each node execution.
    """

    def __init__(self, tree: BehaviorTree):
        """Initialize the DebuggerTree.

        Args:
            tree: The BehaviorTree to wrap with debugging capabilities.
        """
        self.tree = tree
        self.breakpoints: dict[str, BreakpointConfig] = {}
        self._paused = False
        self._step_mode = False
        self._resume_event = asyncio.Event()
        self._resume_event.set()  # Start in resumed state
        self._current_node_path: str | None = None
        self._command_handler: Callable[[str, dict], None] | None = None

    @property
    def paused(self) -> bool:
        """Check if execution is currently paused."""
        return self._paused

    @property
    def step_mode(self) -> bool:
        """Check if step mode is enabled."""
        return self._step_mode

    def set_command_handler(self, handler: Callable[[str, dict], None] | None) -> None:
        """Set the command handler for responding to debugger commands.

        Args:
            handler: Callable that takes (command, data) and handles debugger commands.
        """
        self._command_handler = handler

    def set_breakpoint(
        self,
        node_path: str,
        condition: Callable[[Any], bool] | None = None,
    ) -> None:
        """Set a breakpoint at a specific node path.

        Args:
            node_path: The path to the node (e.g., "root/sequence[0]/action[1]").
            condition: Optional condition function that must return True for the
                      breakpoint to trigger.
        """
        self.breakpoints[node_path] = BreakpointConfig(
            node_path=node_path, condition=condition
        )

    def clear_breakpoint(self, node_path: str) -> bool:
        """Clear a breakpoint at a specific node path.

        Args:
            node_path: The path to the node.

        Returns:
            True if a breakpoint was removed, False if none existed.
        """
        if node_path in self.breakpoints:
            del self.breakpoints[node_path]
            return True
        return False

    def clear_all_breakpoints(self) -> int:
        """Clear all breakpoints.

        Returns:
            The number of breakpoints that were cleared.
        """
        count = len(self.breakpoints)
        self.breakpoints.clear()
        return count

    def pause(self) -> None:
        """Pause execution at the next node."""
        self._paused = True
        self._resume_event.clear()
        if self._command_handler:
            self._command_handler(
                "paused",
                {
                    "reason": "manual_pause",
                    "current_node": self._current_node_path,
                },
            )

    def resume(self) -> None:
        """Resume execution from a paused state."""
        self._paused = False
        self._step_mode = False
        self._resume_event.set()
        if self._command_handler:
            self._command_handler("resumed", {})

    def step(self) -> None:
        """Execute one step (one node) then pause again."""
        self._step_mode = True
        self._resume_event.set()

    async def _check_breakpoint(self, node_path: str, state: Any) -> None:
        """Check if we should pause at this node.

        Args:
            node_path: The path of the node about to execute.
            state: The current state.
        """
        self._current_node_path = node_path

        # Check for breakpoint
        if node_path in self.breakpoints:
            bp = self.breakpoints[node_path]
            should_break = True

            if bp.condition is not None:
                try:
                    should_break = bp.condition(state)
                except Exception:
                    # If condition evaluation fails, don't break
                    should_break = False

            if should_break:
                bp.hit_count += 1
                self._paused = True
                self._resume_event.clear()

                if self._command_handler:
                    self._command_handler(
                        "paused",
                        {
                            "reason": "breakpoint",
                            "node_path": node_path,
                            "hit_count": bp.hit_count,
                        },
                    )

        # Check for step mode
        if self._step_mode:
            self._paused = True
            self._resume_event.clear()
            self._step_mode = False

            if self._command_handler:
                self._command_handler(
                    "paused",
                    {
                        "reason": "step",
                        "node_path": node_path,
                    },
                )

        # Wait if paused
        if self._paused:
            await self._resume_event.wait()

    async def tick_async(self, state: Any) -> NodeStatus:
        """Execute one tick of the behavior tree asynchronously.

        This method checks for breakpoints before executing each tick.

        Note: Breakpoints are checked BEFORE each tick. If you set a breakpoint
        on a specific node path, execution will pause before the tick that
        contains that node. This is because Vivarium executes trees synchronously
        and we cannot interrupt mid-tick.

        Args:
            state: The current state to pass through the tree.

        Returns:
            The status returned by the tree.
        """
        # Check if any breakpoints match this execution
        # Since we can't pause mid-tick, we check all breakpoints before the tick
        should_pause = False
        breakpoint_info = None

        for node_path, bp in self.breakpoints.items():
            # Check if this breakpoint's condition is met
            if bp.condition is None:
                should_pause = True
                breakpoint_info = (node_path, bp)
                break
            else:
                try:
                    if bp.condition(state):
                        should_pause = True
                        breakpoint_info = (node_path, bp)
                        break
                except Exception:
                    pass

        if should_pause and breakpoint_info:
            node_path, bp = breakpoint_info
            bp.hit_count += 1
            self._paused = True
            self._resume_event.clear()

            if self._command_handler:
                self._command_handler(
                    "paused",
                    {
                        "reason": "breakpoint",
                        "node_path": node_path,
                        "hit_count": bp.hit_count,
                        "note": "Paused before tick containing this node",
                    },
                )

            # Wait for resume
            await self._resume_event.wait()

        # Check for step mode
        if self._step_mode:
            self._paused = True
            self._resume_event.clear()
            self._step_mode = False

            if self._command_handler:
                self._command_handler(
                    "paused",
                    {
                        "reason": "step",
                        "node_path": "tick",
                    },
                )

            await self._resume_event.wait()

        # Execute the tree
        return self.tree.tick(state)

    def tick(self, state: Any) -> NodeStatus:
        """Execute one tick of the behavior tree synchronously.

        Note: Synchronous ticking does not support breakpoints or stepping.
        Use tick_async() for debugging features.

        Args:
            state: The current state to pass through the tree.

        Returns:
            The status returned by the tree.
        """
        return self.tree.tick(state)

    def handle_command(self, command: str, data: dict | None = None) -> None:
        """Handle a debugger command.

        Args:
            command: The command to execute.
            data: Optional data for the command.
        """
        data = data or {}

        if command == DebuggerCommand.PAUSE:
            self.pause()
        elif command == DebuggerCommand.RESUME:
            self.resume()
        elif command == DebuggerCommand.STEP:
            self.step()
        elif command == DebuggerCommand.SET_BREAKPOINT:
            node_path = data.get("node_path")
            if node_path:
                self.set_breakpoint(node_path)
        elif command == DebuggerCommand.CLEAR_BREAKPOINT:
            node_path = data.get("node_path")
            if node_path:
                self.clear_breakpoint(node_path)
        elif command == DebuggerCommand.CLEAR_ALL_BREAKPOINTS:
            self.clear_all_breakpoints()

    def reset(self) -> None:
        """Reset the tree and debugger state."""
        self.tree.reset()
        self._paused = False
        self._step_mode = False
        self._resume_event.set()
        self._current_node_path = None
        # Note: We don't clear breakpoints on reset
