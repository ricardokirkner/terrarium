"""Tests for debugging functionality."""

import asyncio

import pytest
from vivarium import Action, BehaviorTree, NodeStatus, Sequence, State

from treehouse.debugging import BreakpointConfig, DebuggerCommand, DebuggerTree
from treehouse.telemetry import TraceCollector


class SimpleAction(Action):
    """Simple action for testing."""

    def __init__(self, name: str, result: NodeStatus = NodeStatus.SUCCESS):
        super().__init__(name)
        self.result = result
        self.executed = False

    def execute(self, state: State) -> NodeStatus:
        self.executed = True
        return self.result


def test_debugger_tree_creation():
    """Test creating a DebuggerTree."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    assert debugger.tree is tree
    assert not debugger.paused
    assert not debugger.step_mode
    assert len(debugger.breakpoints) == 0


def test_set_breakpoint():
    """Test setting a breakpoint."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("root/action[0]")
    assert "root/action[0]" in debugger.breakpoints
    assert isinstance(debugger.breakpoints["root/action[0]"], BreakpointConfig)


def test_set_conditional_breakpoint():
    """Test setting a conditional breakpoint."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    # Breakpoint that only triggers when state has "test" key
    def condition(state):
        return "test" in state

    debugger.set_breakpoint("root/action[0]", condition=condition)
    bp = debugger.breakpoints["root/action[0]"]
    assert bp.condition is not None
    assert bp.condition({"test": 123})
    assert not bp.condition({})


def test_clear_breakpoint():
    """Test clearing a specific breakpoint."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("root/action[0]")
    debugger.set_breakpoint("root/action[1]")
    assert len(debugger.breakpoints) == 2

    result = debugger.clear_breakpoint("root/action[0]")
    assert result
    assert len(debugger.breakpoints) == 1
    assert "root/action[1]" in debugger.breakpoints

    # Clearing non-existent breakpoint
    result = debugger.clear_breakpoint("nonexistent")
    assert not result


def test_clear_all_breakpoints():
    """Test clearing all breakpoints."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("root/action[0]")
    debugger.set_breakpoint("root/action[1]")
    debugger.set_breakpoint("root/action[2]")
    assert len(debugger.breakpoints) == 3

    count = debugger.clear_all_breakpoints()
    assert count == 3
    assert len(debugger.breakpoints) == 0


def test_pause_resume():
    """Test manual pause and resume."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    # Initially not paused
    assert not debugger.paused

    # Pause
    debugger.pause()
    assert debugger.paused

    # Resume
    debugger.resume()
    assert not debugger.paused
    assert not debugger.step_mode


def test_step_mode():
    """Test step mode."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    # Initially not in step mode
    assert not debugger.step_mode

    # Enable step mode via pause and step
    debugger.pause()
    assert debugger.paused

    debugger.step()

    # After step, resume event should be set and step_mode enabled
    assert debugger._resume_event.is_set()
    # Step mode will cause pause after next node execution
    assert debugger.step_mode


def test_handle_command_pause():
    """Test handling pause command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.handle_command(DebuggerCommand.PAUSE)
    assert debugger.paused


def test_handle_command_resume():
    """Test handling resume command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.pause()
    assert debugger.paused

    debugger.handle_command(DebuggerCommand.RESUME)
    assert not debugger.paused


def test_handle_command_step():
    """Test handling step command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.pause()
    debugger.handle_command(DebuggerCommand.STEP)

    # Step sets step_mode and clears pause temporarily
    assert debugger._resume_event.is_set()


def test_handle_command_set_breakpoint():
    """Test handling set breakpoint command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.handle_command(
        DebuggerCommand.SET_BREAKPOINT, {"node_path": "root/action[0]"}
    )
    assert "root/action[0]" in debugger.breakpoints


def test_handle_command_clear_breakpoint():
    """Test handling clear breakpoint command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("root/action[0]")
    debugger.handle_command(
        DebuggerCommand.CLEAR_BREAKPOINT, {"node_path": "root/action[0]"}
    )
    assert "root/action[0]" not in debugger.breakpoints


def test_handle_command_clear_all_breakpoints():
    """Test handling clear all breakpoints command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("root/action[0]")
    debugger.set_breakpoint("root/action[1]")

    debugger.handle_command(DebuggerCommand.CLEAR_ALL_BREAKPOINTS)
    assert len(debugger.breakpoints) == 0


def test_sync_tick():
    """Test synchronous tick (without breakpoint support)."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    state = State()
    result = debugger.tick(state)

    assert result == NodeStatus.SUCCESS
    assert action.executed


def test_sync_tick_with_breakpoint():
    """Test that sync tick ignores breakpoints."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("root")
    state = State()

    # Sync tick should execute normally, ignoring breakpoints
    result = debugger.tick(state)
    assert result == NodeStatus.SUCCESS
    assert action.executed


@pytest.mark.asyncio
async def test_async_tick_basic():
    """Test basic async tick."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    assert result == NodeStatus.SUCCESS
    assert action.executed


@pytest.mark.asyncio
async def test_async_tick_with_pause():
    """Test async tick with manual pause."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    state = State()

    # Start execution in background
    task = asyncio.create_task(debugger.tick_async(state))

    # Give it a moment to pause
    await asyncio.sleep(0.01)

    # Pause before it executes
    debugger.pause()

    # It should be paused now
    assert debugger.paused

    # Resume
    debugger.resume()

    # Wait for completion
    result = await task
    assert result == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_command_handler_callback():
    """Test that command handler is called."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    # Pause should trigger callback
    debugger.pause()
    assert len(commands_received) == 1
    assert commands_received[0][0] == "paused"
    assert commands_received[0][1]["reason"] == "manual_pause"

    # Resume should trigger callback
    debugger.resume()
    assert len(commands_received) == 2
    assert commands_received[1][0] == "resumed"


def test_reset():
    """Test resetting the debugger."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    # Set some state
    debugger.pause()
    debugger.set_breakpoint("root/action[0]")

    # Reset
    debugger.reset()

    # Debugger state should be reset (but not breakpoints)
    assert not debugger.paused
    assert not debugger.step_mode
    assert debugger._resume_event.is_set()
    assert debugger._current_node_path is None

    # Breakpoints should persist
    assert len(debugger.breakpoints) == 1


def test_debugger_with_trace_collector():
    """Test using debugger with trace collector."""
    action = SimpleAction("test_action")
    collector = TraceCollector()
    tree = BehaviorTree(action, emitter=collector)
    debugger = DebuggerTree(tree)

    state = State()
    result = debugger.tick(state)

    assert result == NodeStatus.SUCCESS
    assert action.executed

    # Trace should be collected
    traces = collector.get_traces()
    assert len(traces) == 1
    assert len(traces[0].executions) == 1


def test_debugger_with_sequence():
    """Test debugger with sequence of actions."""
    actions = [
        SimpleAction("action1"),
        SimpleAction("action2"),
        SimpleAction("action3"),
    ]
    sequence = Sequence("sequence", actions)
    tree = BehaviorTree(sequence)
    debugger = DebuggerTree(tree)

    state = State()
    result = debugger.tick(state)

    assert result == NodeStatus.SUCCESS
    assert all(action.executed for action in actions)
