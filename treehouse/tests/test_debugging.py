"""Tests for debugging functionality."""

import asyncio

import pytest
from vivarium import (
    Action,
    BehaviorTree,
    Condition,
    NodeStatus,
    Parallel,
    Selector,
    Sequence,
    State,
)
from vivarium.decorators import Inverter

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


class SimpleCondition(Condition):
    """Simple condition for testing."""

    def __init__(self, name: str, result: bool = True):
        super().__init__(name)
        self._result = result

    def evaluate(self, state: State) -> bool:
        return self._result


# --- Synchronous / unit tests (no async tick) ---


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

    debugger.set_breakpoint("test_action")
    assert "test_action" in debugger.breakpoints
    assert isinstance(debugger.breakpoints["test_action"], BreakpointConfig)


def test_set_conditional_breakpoint():
    """Test setting a conditional breakpoint."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    # Breakpoint that only triggers when state has "test" key
    def condition(state):
        return "test" in state

    debugger.set_breakpoint("test_action", condition=condition)
    bp = debugger.breakpoints["test_action"]
    assert bp.condition is not None
    assert bp.condition({"test": 123})
    assert not bp.condition({})


def test_clear_breakpoint():
    """Test clearing a specific breakpoint."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("path_a")
    debugger.set_breakpoint("path_b")
    assert len(debugger.breakpoints) == 2

    result = debugger.clear_breakpoint("path_a")
    assert result
    assert len(debugger.breakpoints) == 1
    assert "path_b" in debugger.breakpoints

    # Clearing non-existent breakpoint
    result = debugger.clear_breakpoint("nonexistent")
    assert not result


def test_clear_all_breakpoints():
    """Test clearing all breakpoints."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("path_a")
    debugger.set_breakpoint("path_b")
    debugger.set_breakpoint("path_c")
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
        DebuggerCommand.SET_BREAKPOINT, {"node_path": "test_action"}
    )
    assert "test_action" in debugger.breakpoints


def test_handle_command_clear_breakpoint():
    """Test handling clear breakpoint command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("test_action")
    debugger.handle_command(
        DebuggerCommand.CLEAR_BREAKPOINT, {"node_path": "test_action"}
    )
    assert "test_action" not in debugger.breakpoints


def test_handle_command_clear_all_breakpoints():
    """Test handling clear all breakpoints command."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("path_a")
    debugger.set_breakpoint("path_b")

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

    debugger.set_breakpoint("test_action")
    state = State()

    # Sync tick should execute normally, ignoring breakpoints
    result = debugger.tick(state)
    assert result == NodeStatus.SUCCESS
    assert action.executed


# --- Async tests ---


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

    # Give it a moment to start
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
    debugger.set_breakpoint("test_action")

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


@pytest.mark.asyncio
async def test_async_tick_with_breakpoint():
    """Test async tick hitting a breakpoint.

    The root is SimpleAction("test_action"), so the Vivarium path for
    the root node is "test_action".
    """
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)
    debugger.set_breakpoint("test_action")

    state = State()

    # Start execution in background (will pause at breakpoint)
    task = asyncio.create_task(debugger.tick_async(state))

    # Give it time to hit breakpoint
    await asyncio.sleep(0.05)

    # Should be paused
    assert debugger.paused
    # trace_start comes from tick_async, then the tick thread emits node_executing
    # and paused via the DebugEmitter
    paused_events = [c for c in commands_received if c[0] == "paused"]
    assert len(paused_events) >= 1
    bp_event = paused_events[0]
    assert bp_event[1]["reason"] == "breakpoint"
    assert bp_event[1]["node_path"] == "test_action"
    assert bp_event[1]["hit_count"] == 1

    # Resume to complete
    debugger.resume()
    result = await task

    assert result == NodeStatus.SUCCESS
    assert action.executed


@pytest.mark.asyncio
async def test_async_tick_with_conditional_breakpoint_hit():
    """Test conditional breakpoint that triggers."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    # Breakpoint that triggers when state has "trigger" key
    def condition(state):
        return "trigger" in state

    debugger.set_breakpoint("test_action", condition=condition)

    state = State()
    state["trigger"] = True

    # Start execution
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    # Should be paused
    assert debugger.paused
    paused_events = [c for c in commands_received if c[0] == "paused"]
    assert len(paused_events) >= 1
    assert paused_events[0][1]["reason"] == "breakpoint"

    debugger.resume()
    await task


@pytest.mark.asyncio
async def test_async_tick_with_conditional_breakpoint_no_hit():
    """Test conditional breakpoint that doesn't trigger."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    # Breakpoint that won't trigger
    def condition(state):
        return "trigger" in state

    debugger.set_breakpoint("test_action", condition=condition)

    state = State()
    # Don't set "trigger" key

    # Execute without pausing
    result = await debugger.tick_async(state)

    assert result == NodeStatus.SUCCESS
    assert not debugger.paused
    # Should receive trace_start, node_executing, and tick_complete events
    assert any(c[0] == "trace_start" for c in commands_received)
    assert any(c[0] == "node_executing" for c in commands_received)
    assert any(c[0] == "tick_complete" for c in commands_received)


@pytest.mark.asyncio
async def test_async_tick_with_failing_condition():
    """Test breakpoint with condition that raises exception."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    # Condition that raises exception
    def bad_condition(state):
        raise ValueError("boom")

    debugger.set_breakpoint("test_action", condition=bad_condition)

    state = State()

    # Should not pause when condition fails
    result = await debugger.tick_async(state)

    assert result == NodeStatus.SUCCESS
    assert not debugger.paused


@pytest.mark.asyncio
async def test_async_tick_step_mode():
    """Test step mode in async execution."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    # Enable step mode
    debugger.pause()
    debugger.step()

    state = State()

    # Start execution
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    # Should have paused at step
    assert debugger.paused
    paused_events = [c for c in commands_received if c[0] == "paused"]
    # manual_pause + step pause
    assert len(paused_events) >= 2
    step_events = [p for p in paused_events if p[1].get("reason") == "step"]
    assert len(step_events) >= 1

    # Resume
    debugger.resume()
    await task


@pytest.mark.asyncio
async def test_async_multiple_breakpoints():
    """Test hitting same breakpoint across multiple ticks."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree)

    debugger.set_breakpoint("test_action")

    state = State()

    # First execution - hit breakpoint
    task1 = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)
    assert debugger.paused
    debugger.resume()
    await task1

    # Reset tree for second execution
    debugger.reset()

    # Second execution - hit same breakpoint again
    task2 = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)
    assert debugger.paused

    # Check hit count incremented
    bp = debugger.breakpoints["test_action"]
    assert bp.hit_count == 2

    debugger.resume()
    await task2


@pytest.mark.asyncio
async def test_pause_before_start():
    """Test pausing before the first tick."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree, pause_before_start=True)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    state = State()

    # Should be paused initially
    assert debugger.paused

    # Start execution - should pause before first tick
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    # Should have sent trace_start and paused event
    assert any(c[0] == "trace_start" for c in commands_received)
    paused_events = [c for c in commands_received if c[0] == "paused"]
    assert len(paused_events) >= 1
    assert paused_events[0][1]["reason"] == "before_start"

    # Resume execution
    debugger.resume()
    result = await task

    # Should have completed successfully
    assert result == NodeStatus.SUCCESS
    assert not debugger.paused

    # Should have tick_complete event
    assert any(c[0] == "tick_complete" for c in commands_received)


@pytest.mark.asyncio
async def test_pause_before_start_then_step():
    """Test pausing before start, then using step mode."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree, pause_before_start=True)

    state = State()

    # Start execution - paused before first tick
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    assert debugger.paused

    # Use step - this will resume from the before_start pause but then
    # pause again when the first node_entered event fires
    debugger.step()
    await asyncio.sleep(0.05)

    # Should still be paused (step pauses on node_entered)
    assert debugger.paused

    # Resume to complete the tick
    debugger.resume()
    result = await task

    assert result == NodeStatus.SUCCESS
    assert not debugger.paused


@pytest.mark.asyncio
async def test_pause_before_start_with_breakpoint():
    """Test pause_before_start allows setting breakpoints before execution."""
    action = SimpleAction("test_action")
    tree = BehaviorTree(action)
    debugger = DebuggerTree(tree, pause_before_start=True)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    state = State()

    # Start execution - paused before first tick
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    assert debugger.paused
    assert any(c[0] == "trace_start" for c in commands_received)
    before_start_events = [
        c
        for c in commands_received
        if c[0] == "paused" and c[1].get("reason") == "before_start"
    ]
    assert len(before_start_events) == 1

    # Set a breakpoint while paused
    debugger.set_breakpoint("test_action")

    # Resume - should hit the breakpoint
    debugger.resume()
    await asyncio.sleep(0.05)

    # Should still be paused due to breakpoint
    assert debugger.paused

    # Should have paused event with breakpoint reason
    breakpoint_pause_events = [
        cmd
        for cmd in commands_received
        if cmd[0] == "paused" and cmd[1].get("reason") == "breakpoint"
    ]
    assert len(breakpoint_pause_events) == 1

    # Resume again to complete
    debugger.resume()
    await task


# --- Tests for correct delegation to Vivarium ---


@pytest.mark.asyncio
async def test_async_tick_emits_vivarium_events():
    """Test that async tick emits proper Vivarium events via the emitter."""
    action = SimpleAction("test_action")
    collector = TraceCollector()
    tree = BehaviorTree(action, emitter=collector)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    assert result == NodeStatus.SUCCESS

    # TraceCollector should have received events and built a trace
    traces = collector.get_traces()
    assert len(traces) == 1
    assert len(traces[0].executions) == 1
    assert traces[0].executions[0].node_name == "test_action"


@pytest.mark.asyncio
async def test_async_tick_sequence_emits_all_events():
    """Test that async tick of a sequence emits events for all nodes."""
    actions = [
        SimpleAction("action1"),
        SimpleAction("action2"),
        SimpleAction("action3"),
    ]
    sequence = Sequence("seq", actions)
    collector = TraceCollector()
    tree = BehaviorTree(sequence, emitter=collector)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    assert result == NodeStatus.SUCCESS
    assert all(a.executed for a in actions)

    traces = collector.get_traces()
    assert len(traces) == 1
    # Should have executions for seq + 3 actions = 4
    assert len(traces[0].executions) == 4


@pytest.mark.asyncio
async def test_async_tick_with_selector():
    """Test async tick with a Selector node."""
    # First child fails, second succeeds
    actions = [
        SimpleAction("fail_action", result=NodeStatus.FAILURE),
        SimpleAction("success_action", result=NodeStatus.SUCCESS),
        SimpleAction("skip_action", result=NodeStatus.SUCCESS),
    ]
    selector = Selector("sel", actions)
    tree = BehaviorTree(selector)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    assert result == NodeStatus.SUCCESS
    assert actions[0].executed  # tried and failed
    assert actions[1].executed  # tried and succeeded
    assert not actions[2].executed  # skipped


@pytest.mark.asyncio
async def test_async_tick_with_parallel_thresholds():
    """Test that Parallel node thresholds work correctly via Vivarium delegation."""
    actions = [
        SimpleAction("action1", result=NodeStatus.SUCCESS),
        SimpleAction("action2", result=NodeStatus.FAILURE),
        SimpleAction("action3", result=NodeStatus.SUCCESS),
    ]
    # success_threshold=2: need 2 successes to succeed
    parallel = Parallel("par", actions, success_threshold=2)
    tree = BehaviorTree(parallel)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    # 2 successes >= threshold of 2 -> SUCCESS
    assert result == NodeStatus.SUCCESS
    assert all(a.executed for a in actions)


@pytest.mark.asyncio
async def test_async_tick_with_parallel_failure_threshold():
    """Test Parallel failure threshold via Vivarium delegation."""
    actions = [
        SimpleAction("action1", result=NodeStatus.FAILURE),
        SimpleAction("action2", result=NodeStatus.FAILURE),
        SimpleAction("action3", result=NodeStatus.SUCCESS),
    ]
    # failure_threshold=2: 2 failures -> FAILURE
    parallel = Parallel("par", actions, failure_threshold=2)
    tree = BehaviorTree(parallel)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    assert result == NodeStatus.FAILURE


@pytest.mark.asyncio
async def test_async_tick_with_decorator():
    """Test that decorators work correctly via Vivarium delegation."""
    action = SimpleAction("inner_action", result=NodeStatus.SUCCESS)
    inverter = Inverter("inv", action)
    tree = BehaviorTree(inverter)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    # Inverter flips SUCCESS -> FAILURE
    assert result == NodeStatus.FAILURE
    assert action.executed


@pytest.mark.asyncio
async def test_async_tick_with_decorator_events():
    """Test that decorator emits events via Vivarium delegation."""
    action = SimpleAction("inner_action", result=NodeStatus.SUCCESS)
    inverter = Inverter("inv", action)
    collector = TraceCollector()
    tree = BehaviorTree(inverter, emitter=collector)
    debugger = DebuggerTree(tree)

    state = State()
    result = await debugger.tick_async(state)

    assert result == NodeStatus.FAILURE

    traces = collector.get_traces()
    assert len(traces) == 1
    # Should have executions for inverter + inner_action = 2
    assert len(traces[0].executions) == 2


@pytest.mark.asyncio
async def test_breakpoint_on_child_in_sequence():
    """Test setting a breakpoint on a child node inside a sequence."""
    actions = [
        SimpleAction("action1"),
        SimpleAction("action2"),
        SimpleAction("action3"),
    ]
    sequence = Sequence("seq", actions)
    tree = BehaviorTree(sequence)
    debugger = DebuggerTree(tree)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    # Breakpoint on the second child (path: seq/action2@1)
    debugger.set_breakpoint("seq/action2@1")

    state = State()
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    # Should be paused at action2
    assert debugger.paused
    bp_events = [
        c
        for c in commands_received
        if c[0] == "paused" and c[1].get("reason") == "breakpoint"
    ]
    assert len(bp_events) == 1
    assert bp_events[0][1]["node_path"] == "seq/action2@1"

    # action1 should have executed, action2 should not yet
    assert actions[0].executed
    assert not actions[1].executed

    # Resume to complete
    debugger.resume()
    result = await task
    assert result == NodeStatus.SUCCESS
    assert all(a.executed for a in actions)


@pytest.mark.asyncio
async def test_extract_tree_structure_with_decorator():
    """Test _extract_tree_structure handles decorators."""
    action = SimpleAction("inner")
    inverter = Inverter("inv", action)
    tree = BehaviorTree(inverter)
    debugger = DebuggerTree(tree)

    structure = debugger._extract_tree_structure(inverter, "root")
    assert structure["node_name"] == "inv"
    assert structure["node_type"] == "Inverter"
    assert len(structure["children"]) == 1
    assert structure["children"][0]["node_name"] == "inner"


@pytest.mark.asyncio
async def test_extract_tree_structure_with_sequence():
    """Test _extract_tree_structure handles composites."""
    actions = [SimpleAction("a"), SimpleAction("b")]
    seq = Sequence("seq", actions)
    tree = BehaviorTree(seq)
    debugger = DebuggerTree(tree)

    structure = debugger._extract_tree_structure(seq, "root")
    assert structure["node_name"] == "seq"
    assert len(structure["children"]) == 2
    assert structure["children"][0]["node_name"] == "a"
    assert structure["children"][1]["node_name"] == "b"


@pytest.mark.asyncio
async def test_step_through_sequence():
    """Test stepping through a sequence node-by-node."""
    actions = [
        SimpleAction("action1"),
        SimpleAction("action2"),
    ]
    sequence = Sequence("seq", actions)
    tree = BehaviorTree(sequence)
    debugger = DebuggerTree(tree)

    commands_received = []

    def handler(command, data):
        commands_received.append((command, data))

    debugger.set_command_handler(handler)

    # Start in step mode
    debugger.pause()
    debugger.step()

    state = State()
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    # Should be paused at first node_entered event (the sequence itself)
    assert debugger.paused

    # Step again to move to next node
    debugger.step()
    await asyncio.sleep(0.05)

    # Should be paused at next node_entered
    assert debugger.paused

    # Resume to complete
    debugger.resume()
    result = await task
    assert result == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_step_with_breakpoint_sends_correct_events():
    """Regression test: step() must send 'resumed' event immediately.

    When a user clicks step, the visualizer should:
    1. IMMEDIATELY receive 'resumed' event (with reason='step')
    2. Then execution proceeds and pauses at next node
    3. Receive 'paused' event

    This ensures button states update correctly: clicking Step should
    disable Resume/Step buttons immediately, then re-enable them when paused.

    Bug: Before fix, step() didn't send 'resumed' event, so buttons stayed
    in wrong state.
    """
    actions = [
        SimpleAction("step1"),
        SimpleAction("step2"),
        SimpleAction("step3"),
    ]
    sequence = Sequence("workflow", actions)
    tree = BehaviorTree(sequence)
    debugger = DebuggerTree(tree, pause_before_start=True)

    events_received = []

    def handler(event_type, data):
        events_received.append((event_type, data))

    debugger.set_command_handler(handler)

    # Set a breakpoint on step2 (though we won't reach it in this test)
    root_name = getattr(tree.root, "name", type(tree.root).__name__)
    step2_path = f"{root_name}/step2@1"
    debugger.set_breakpoint(step2_path)

    state = State()
    task = asyncio.create_task(debugger.tick_async(state))
    await asyncio.sleep(0.05)

    # Should be paused before start
    assert debugger.paused
    events_received.clear()

    # User clicks Step button - this is the critical moment
    debugger.step()

    # Don't wait for async execution - check events sent synchronously by
    # step(). The 'resumed' event should be sent IMMEDIATELY by step()
    event_types = [e[0] for e in events_received]
    assert (
        "resumed" in event_types
    ), f"step() must send 'resumed' event immediately, got: {event_types}"

    # Verify the resumed event has reason='step'
    resumed_events = [e for e in events_received if e[0] == "resumed"]
    assert (
        resumed_events[0][1].get("reason") == "step"
    ), f"Resumed event should have reason='step', got: {resumed_events[0][1]}"

    # Now wait for async execution to proceed
    await asyncio.sleep(0.1)

    # Should be paused at first node after stepping
    assert debugger.paused
    paused_events = [e for e in events_received if e[0] == "paused"]
    assert len(paused_events) > 0, "Should have paused event after step executes"
    assert (
        paused_events[0][1].get("reason") == "step"
    ), "Should pause due to step mode at first node"

    # Clean up - resume to completion
    debugger.resume()
    await asyncio.sleep(0.05)
    debugger.resume()  # Resume again from breakpoint at step2
    await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_multi_tick_step_with_breakpoints():
    """Regression test: multiple ticks with stepping and breakpoints.

    Simulates the breakpoint_stepping.py scenario:
    - Set a breakpoint
    - Use step to advance through execution
    - Verify paused/resumed events are sent correctly for each step

    This tests the real-world workflow where users set breakpoints
    and step through multiple ticks.
    """
    actions = [
        SimpleAction("step1"),
        SimpleAction("step2"),
        SimpleAction("step3"),
    ]
    sequence = Sequence("workflow", actions)
    tree = BehaviorTree(sequence)
    debugger = DebuggerTree(tree, pause_before_start=True)

    events_received = []

    def handler(event_type, data):
        events_received.append((event_type, data))

    debugger.set_command_handler(handler)

    # Set breakpoint on step2
    root_name = getattr(tree.root, "name", type(tree.root).__name__)
    step2_path = f"{root_name}/step2@1"
    debugger.set_breakpoint(step2_path)

    # Run first tick
    state1 = State()
    task1 = asyncio.create_task(debugger.tick_async(state1))
    await asyncio.sleep(0.05)

    assert debugger.paused  # Paused before start
    events_received.clear()

    # Step through first tick
    debugger.step()  # Should send 'resumed' immediately
    assert any(
        e[0] == "resumed" and e[1].get("reason") == "step" for e in events_received
    ), "step() should send resumed event"

    await asyncio.sleep(0.05)
    assert debugger.paused  # Paused at first node (workflow)

    debugger.step()  # Step to step1
    await asyncio.sleep(0.05)
    assert debugger.paused

    debugger.step()  # Step to step2 (has breakpoint)
    await asyncio.sleep(0.05)
    assert debugger.paused

    # Should have hit the breakpoint
    breakpoint_events = [
        e
        for e in events_received
        if e[0] == "paused" and e[1].get("reason") == "breakpoint"
    ]
    assert len(breakpoint_events) > 0, "Should have paused at breakpoint"

    # Resume to complete first tick
    debugger.resume()
    result1 = await asyncio.wait_for(task1, timeout=1.0)
    assert result1 == NodeStatus.SUCCESS

    # Verify we got tick_complete event
    assert any(e[0] == "tick_complete" for e in events_received)

    # Second tick - should work the same way
    events_received.clear()
    state2 = State()
    task2 = asyncio.create_task(debugger.tick_async(state2))
    await asyncio.sleep(0.05)

    # Should NOT be paused (pause_before_start only applies to first tick)
    # But should hit breakpoint immediately
    await asyncio.sleep(0.1)

    # Should be paused at step2 breakpoint
    assert debugger.paused
    breakpoint_events = [
        e
        for e in events_received
        if e[0] == "paused" and e[1].get("reason") == "breakpoint"
    ]
    assert len(breakpoint_events) > 0, "Should pause at breakpoint on second tick"

    # Resume to complete
    debugger.resume()
    result2 = await asyncio.wait_for(task2, timeout=1.0)
    assert result2 == NodeStatus.SUCCESS
