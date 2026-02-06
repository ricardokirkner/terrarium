"""Debugging support for behavior trees.

This module provides debugging capabilities like breakpoints, stepping,
and pause/resume for behavior tree execution.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from vivarium import BehaviorTree, NodeStatus
from vivarium.core.node import Node

logger = logging.getLogger(__name__)


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

    def __init__(self, tree: BehaviorTree, pause_before_start: bool = False):
        """Initialize the DebuggerTree.

        Args:
            tree: The BehaviorTree to wrap with debugging capabilities.
            pause_before_start: If True, pause before the first tick to allow
                setting breakpoints.
        """
        self.tree = tree
        self.breakpoints: dict[str, BreakpointConfig] = {}
        self._paused = pause_before_start
        self._pause_before_start = pause_before_start  # Track initial pause request
        self._step_mode = False
        self._resume_event = asyncio.Event()
        if pause_before_start:
            self._resume_event.clear()  # Start paused if requested
        else:
            self._resume_event.set()  # Start in resumed state
        self._current_node_path: str | None = None
        self._command_handler: Callable[[str, dict], None] | None = None
        self._first_tick = True  # Track if this is the first tick

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
        if not self._paused:
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

    def _extract_tree_structure(self, node: Node, path: str = "root") -> dict:
        """Extract the full tree structure for visualization.

        Args:
            node: The node to extract structure from.
            path: The current path in the tree.

        Returns:
            A dictionary representing the tree structure.
        """
        node_info = {
            "node_name": getattr(node, "name", node.__class__.__name__),
            "node_type": node.__class__.__name__,
            "path_in_tree": path,
            "children": [],
        }

        # Check if this is a composite node with children
        if hasattr(node, "children") and node.children:
            for i, child in enumerate(node.children):
                # Use index-based path to match execution paths
                child_path = f"{path}/{i}"
                child_info = self._extract_tree_structure(child, child_path)
                node_info["children"].append(child_info)

        return node_info

    def send_tree_structure(self) -> None:
        """Send the complete tree structure to the visualizer.

        This should be called before execution starts to allow users to see
        the tree and set breakpoints.
        """
        if not self._command_handler:
            return

        tree_structure = self._extract_tree_structure(self.tree.root, "root")
        self._command_handler("tree_structure", tree_structure)

    async def _execute_node_async(
        self, node: Node, state: Any, path: str = "root"
    ) -> NodeStatus:
        """Execute a single node asynchronously with debugging support.

        This method recursively walks the tree and pauses at breakpoints
        or in step mode.

        Args:
            node: The node to execute
            state: The current state
            path: The path to this node in the tree

        Returns:
            The status returned by the node
        """
        # Check if we should pause before executing this node
        await self._check_node_breakpoint(path, state)

        # Check for step mode - pause before each node
        if self._step_mode:
            self._paused = True
            self._resume_event.clear()
            self._step_mode = False  # Clear after using

            if self._command_handler:
                self._command_handler(
                    "paused",
                    {
                        "reason": "step",
                        "node_path": path,
                    },
                )

            await self._resume_event.wait()

        # Store current node being executed
        self._current_node_path = path

        # Notify that we're about to execute this node
        if self._command_handler:
            self._command_handler(
                "node_executing",
                {
                    "node_path": path,
                    "node_name": node.name,
                    "node_type": type(node).__name__,
                },
            )

        # Execute the node based on its type
        if hasattr(node, "children"):
            # Composite node - execute children based on node type
            result = await self._execute_composite_node(node, state, path)
        else:
            # Leaf node - execute directly
            result = node.tick(state)

        return result

    async def _execute_composite_node(
        self, node: Node, state: Any, path: str
    ) -> NodeStatus:
        """Execute a composite node's children according to its logic.

        Args:
            node: The composite node
            state: The current state
            path: The path to this node

        Returns:
            The status based on the composite node's logic
        """
        node_type = type(node).__name__

        if node_type == "Sequence":
            # Sequence: execute children in order, stop on first non-success
            for i, child in enumerate(node.children):
                child_path = f"{path}/{i}"
                status = await self._execute_node_async(child, state, child_path)
                if status != NodeStatus.SUCCESS:
                    return status
            return NodeStatus.SUCCESS

        elif node_type == "Selector":
            # Selector: execute children in order, stop on first non-failure
            for i, child in enumerate(node.children):
                child_path = f"{path}/{i}"
                status = await self._execute_node_async(child, state, child_path)
                if status != NodeStatus.FAILURE:
                    return status
            return NodeStatus.FAILURE

        elif node_type == "Parallel":
            # Parallel: execute all children
            statuses = []
            for i, child in enumerate(node.children):
                child_path = f"{path}/{i}"
                status = await self._execute_node_async(child, state, child_path)
                statuses.append(status)

            # Return based on parallel policy (simplified: all must succeed)
            if all(s == NodeStatus.SUCCESS for s in statuses):
                return NodeStatus.SUCCESS
            return NodeStatus.FAILURE

        else:
            # Unknown composite type - fall back to normal tick
            logger.warning(
                f"Unknown composite node type: {node_type}, using normal tick"
            )
            return node.tick(state)

    async def _check_node_breakpoint(self, node_path: str, state: Any) -> None:
        """Check if we should pause at this specific node.

        Args:
            node_path: The path to the node
            state: The current state
        """
        bp = self.breakpoints.get(node_path)
        if bp:
            # Check condition if present
            should_trigger = False
            if bp.condition is None:
                should_trigger = True
            else:
                try:
                    should_trigger = bp.condition(state)
                except Exception as e:
                    logger.warning(f"Breakpoint condition failed: {e}")
                    should_trigger = False

            if should_trigger:
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
                            "note": f"Paused at breakpoint on {node_path}",
                        },
                    )

                await self._resume_event.wait()

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

        This method executes the tree node-by-node, checking for breakpoints
        and step mode at each node. This allows pausing at specific nodes
        within a tick, not just at tick boundaries.

        Args:
            state: The current state to pass through the tree.

        Returns:
            The status returned by the tree.
        """
        # Send trace_start event to initialize visualizer
        if self._command_handler:
            tick_id = getattr(self.tree, "tick_count", 0)
            self._command_handler(
                "trace_start",
                {
                    "trace_id": str(uuid.uuid4()),
                    "tick_id": tick_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        # Pause before first tick if requested via pause_before_start
        if self._first_tick and self._pause_before_start:
            self._first_tick = False
            self._pause_before_start = False  # Only pause once
            logger.info("⏸️  Paused before first tick (pause_before_start=True)")

            if self._command_handler:
                self._command_handler(
                    "paused",
                    {
                        "reason": "before_start",
                        "note": (
                            "Paused before first tick. Set breakpoints and "
                            "click Resume or Step to begin."
                        ),
                    },
                )

            await self._resume_event.wait()

        self._first_tick = False

        # Check if manually paused
        if self._paused and not self._step_mode and not self._pause_before_start:
            logger.info("⏸️  Waiting for resume (manual pause)")
            await self._resume_event.wait()

        # Execute the tree node-by-node with debugging support
        result = await self._execute_node_async(self.tree.root, state, "root")

        # Send tick_complete event after execution
        if self._command_handler:
            self._command_handler("tick_complete", {"status": str(result)})

        return result

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
        logger.info(f"🎮 DebuggerTree.handle_command: {command} with data: {data}")

        if command == DebuggerCommand.PAUSE:
            logger.info("⏸️  Executing PAUSE")
            self.pause()
        elif command == DebuggerCommand.RESUME:
            logger.info("▶️  Executing RESUME")
            self.resume()
            logger.info(
                f"▶️  After resume: _paused={self._paused}, "
                f"_resume_event.is_set()={self._resume_event.is_set()}"
            )
        elif command == DebuggerCommand.STEP:
            logger.info("⏭️  Executing STEP")
            self.step()
        elif command == DebuggerCommand.SET_BREAKPOINT:
            node_path = data.get("node_path")
            if node_path:
                logger.info(f"🔴 Setting breakpoint at {node_path}")
                self.set_breakpoint(node_path)
        elif command == DebuggerCommand.CLEAR_BREAKPOINT:
            node_path = data.get("node_path")
            if node_path:
                logger.info(f"⚪ Clearing breakpoint at {node_path}")
                self.clear_breakpoint(node_path)
        elif command == DebuggerCommand.CLEAR_ALL_BREAKPOINTS:
            logger.info("⚪ Clearing all breakpoints")
            self.clear_all_breakpoints()

    def reset(self) -> None:
        """Reset the tree and debugger state."""
        self.tree.reset()
        self._paused = False
        self._step_mode = False
        self._resume_event.set()
        self._current_node_path = None
        self._first_tick = True
        # Note: We don't clear breakpoints on reset
