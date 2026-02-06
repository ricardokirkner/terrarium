"""Debugging support for behavior trees.

This module provides debugging capabilities like breakpoints, stepping,
and pause/resume for behavior tree execution.

The DebuggerTree delegates all execution to Vivarium's node.tick() and
uses a DebugEmitter to intercept node_entered events for breakpoint and
step-mode pauses. The tree tick runs in a worker thread so that blocking
on a threading.Event does not stall the async event loop.
"""

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from vivarium import BehaviorTree, NodeStatus
from vivarium.core.context import ExecutionContext
from vivarium.core.events import Event, EventEmitter, NodeEntered
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


def _evaluate_bp_condition(bp: BreakpointConfig, state: Any) -> bool:
    """Evaluate a breakpoint's condition against the current state.

    Returns True if the breakpoint should trigger.
    """
    if bp.condition is None:
        return True
    try:
        return bp.condition(state)
    except Exception as e:
        logger.warning(f"Breakpoint condition failed: {e}")
        return False


class _DebugEmitter:
    """Event emitter that intercepts node_entered events for debugging.

    When a node_entered event matches a breakpoint or step-mode is active,
    the emitter blocks the calling thread until the debugger resumes.
    This allows pausing mid-tick without reimplementing tree semantics.

    The emitter also forwards all events to an optional inner emitter
    (e.g., a TraceCollector) and notifies the command handler of debug
    state changes.
    """

    def __init__(
        self,
        debugger: "DebuggerTree",
        inner: EventEmitter | None = None,
        state: Any = None,
    ):
        self._debugger = debugger
        self._inner = inner
        self._state = state

    def emit(self, event: Event) -> None:
        """Emit an event, pausing on node_entered if needed."""
        # Forward to inner emitter first
        if self._inner is not None:
            self._inner.emit(event)

        if not isinstance(event, NodeEntered):
            return

        node_path = event.path_in_tree
        debugger = self._debugger

        # Update current node path
        debugger._current_node_path = node_path

        # Notify command handler of node execution
        if debugger._command_handler:
            debugger._command_handler(
                "node_executing",
                {
                    "node_path": node_path,
                    "node_name": event.node_id,
                    "node_type": event.node_type,
                },
            )

        self._check_breakpoint(node_path)
        self._check_step_mode(node_path)

    def _check_breakpoint(self, node_path: str) -> None:
        """Block the tick thread if a breakpoint matches this path."""
        debugger = self._debugger
        bp = debugger.breakpoints.get(node_path)
        if not bp:
            return

        should_trigger = _evaluate_bp_condition(bp, self._state)
        if not should_trigger:
            return

        bp.hit_count += 1
        debugger._paused = True
        debugger._thread_resume.clear()

        if debugger._command_handler:
            debugger._command_handler(
                "paused",
                {
                    "reason": "breakpoint",
                    "node_path": node_path,
                    "hit_count": bp.hit_count,
                    "note": f"Paused at breakpoint on {node_path}",
                },
            )

        debugger._thread_resume.wait()

    def _check_step_mode(self, node_path: str) -> None:
        """Block the tick thread if step mode is active."""
        debugger = self._debugger
        if not debugger._step_mode:
            return

        debugger._paused = True
        debugger._thread_resume.clear()
        debugger._step_mode = False

        if debugger._command_handler:
            debugger._command_handler(
                "paused",
                {
                    "reason": "step",
                    "node_path": node_path,
                },
            )

        debugger._thread_resume.wait()


class DebuggerTree:
    """Behavior tree wrapper with debugging support.

    This class wraps a Vivarium BehaviorTree and adds debugging capabilities
    such as breakpoints, stepping through execution, and pause/resume.

    Execution is fully delegated to Vivarium's node.tick(). A DebugEmitter
    intercepts node_entered events to check breakpoints and step-mode,
    blocking the tick thread when a pause is needed.

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
        # Threading event used by the tick thread to block on pause
        self._thread_resume = threading.Event()
        if pause_before_start:
            self._resume_event.clear()  # Start paused if requested
            self._thread_resume.clear()
        else:
            self._resume_event.set()  # Start in resumed state
            self._thread_resume.set()
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
            node_path: The path to the node (e.g., "root/action@0").
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
            self._thread_resume.clear()
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
        self._thread_resume.set()
        if self._command_handler:
            self._command_handler("resumed", {})

    def step(self) -> None:
        """Execute one step (one node) then pause again."""
        self._step_mode = True
        self._resume_event.set()
        self._thread_resume.set()

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
                child_name = getattr(child, "name", child.__class__.__name__)
                child_path = f"{path}/{child_name}@{i}"
                child_info = self._extract_tree_structure(child, child_path)
                node_info["children"].append(child_info)

        # Check if this is a decorator node with a single child
        if hasattr(node, "child") and not hasattr(node, "children"):
            child = node.child
            child_name = getattr(child, "name", child.__class__.__name__)
            child_path = f"{path}/{child_name}"
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

    def _run_tick_in_thread(self, state: Any, emitter: _DebugEmitter) -> NodeStatus:
        """Run a tree tick in the current thread with the debug emitter.

        This is called via asyncio.to_thread so the blocking pause in
        _DebugEmitter.emit() does not stall the event loop.

        Args:
            state: The current state to pass through the tree.
            emitter: The debug emitter that intercepts events.

        Returns:
            The status returned by the tree.
        """
        self.tree.tick_count += 1
        tick_id = self.tree.tick_count

        from vivarium.core.events import TickCompleted, TickStarted

        emitter.emit(TickStarted(tick_id=tick_id))

        root_name = getattr(self.tree.root, "name", type(self.tree.root).__name__)
        root_type = type(self.tree.root).__name__
        ctx = ExecutionContext(tick_id=tick_id, path="")
        root_ctx = ctx.child(root_name, root_type)

        result = self.tree.root.tick(state, emitter, root_ctx)

        emitter.emit(TickCompleted(tick_id=tick_id, result=result))
        return result

    async def tick_async(self, state: Any) -> NodeStatus:
        """Execute one tick of the behavior tree asynchronously.

        Execution is delegated entirely to Vivarium's node.tick(), running
        in a worker thread. A DebugEmitter intercepts node_entered events
        to check breakpoints and step-mode, blocking the tick thread when
        a pause is needed.

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
            logger.info("Paused before first tick (pause_before_start=True)")

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
            logger.info("Waiting for resume (manual pause)")
            await self._resume_event.wait()

        # Build the debug emitter wrapping the tree's existing emitter
        inner_emitter = getattr(self.tree, "_emitter", None)
        debug_emitter = _DebugEmitter(self, inner=inner_emitter, state=state)

        # Run the tick in a thread so blocking pauses don't stall the loop
        result = await asyncio.to_thread(self._run_tick_in_thread, state, debug_emitter)

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
        logger.info(f"DebuggerTree.handle_command: {command} with data: {data}")

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
        self._thread_resume.set()
        self._current_node_path = None
        self._first_tick = True
        # Note: We don't clear breakpoints on reset
