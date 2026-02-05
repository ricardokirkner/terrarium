"""Demonstration of breakpoint debugging with Treehouse.

This example shows how to use the DebuggerTree with breakpoints
to pause and step through behavior tree execution.

IMPORTANT LIMITATION:
The current implementation checks breakpoints at the TICK level (before
each tree.tick() call), not at individual node level. This means:
- Breakpoints pause BEFORE the tick that contains that node
- You can step through ticks, not individual nodes
- To pause at specific nodes, you need to structure your tree with
  multiple ticks or use manual pause/resume

For per-node breakpoints, the tree would need to be async-aware at
the Vivarium level (future enhancement).

Usage:
    # Terminal 1: Start the visualizer
    make visualizer

    # Terminal 2: Run this example
    python examples/breakpoint_demo.py

    # In browser: http://localhost:8000
    # - Click the circles (○) before nodes to set breakpoints
    # - Click Pause/Resume/Step buttons to control execution
    # - Breakpoints currently work at tick boundaries
"""

import asyncio
import time

from vivarium import Action, BehaviorTree, NodeStatus, Selector, Sequence, State

from treehouse import DebuggerClient, DebuggerTree, TraceCollector


class SlowAction(Action):
    """Action that takes some time to execute."""

    def __init__(self, name: str, duration: float = 0.5, result=NodeStatus.SUCCESS):
        super().__init__(name)
        self.duration = duration
        self.result = result

    def execute(self, state: State) -> NodeStatus:
        print(f"  Executing {self.name}...")
        time.sleep(self.duration)
        return self.result


async def main():
    print("🌳 Treehouse Breakpoint Demo")
    print("=" * 50)
    print()
    print("Instructions:")
    print("1. Open http://localhost:8000 in your browser")
    print("2. Right-click on nodes to set breakpoints (red dot)")
    print("3. Use Pause/Resume/Step buttons to control execution")
    print("4. Watch the tree pause at breakpoints!")
    print()
    print("=" * 50)
    print()

    # Build a simple behavior tree
    sequence = Sequence(
        "main_sequence",
        [
            SlowAction("initialize", duration=0.3),
            Selector(
                "check_options",
                [
                    SlowAction("try_option_a", duration=0.3, result=NodeStatus.FAILURE),
                    SlowAction("try_option_b", duration=0.3, result=NodeStatus.SUCCESS),
                ],
            ),
            SlowAction("finalize", duration=0.3),
        ],
    )

    # Create trace collector and debugger client
    debugger_client = DebuggerClient(url="ws://localhost:8000/ws/agent")
    collector = TraceCollector()
    collector.set_debugger(debugger_client)

    # Create behavior tree with collector
    tree = BehaviorTree(sequence, emitter=collector)

    # Wrap with DebuggerTree for breakpoint support
    debugger_tree = DebuggerTree(tree)

    # Set the debugger tree as the command handler for the client
    debugger_client.command_handler = debugger_tree

    # Connect to visualizer
    await debugger_client.connect()

    if not debugger_client.connected:
        print("❌ Failed to connect to visualizer at ws://localhost:8000/ws/agent")
        print("   Make sure the visualizer is running: make visualizer")
        return

    print("✅ Connected to visualizer")
    print()
    print("Starting execution in 2 seconds...")
    print("(Set breakpoints in the browser now!)")
    await asyncio.sleep(2)

    # Run multiple ticks to demonstrate pause/resume/step
    print("\nNOTE: Breakpoints work at TICK boundaries (not individual nodes)")
    print("Set breakpoint on 'initialize' to pause before Tick 1")
    print("Use Step button to execute one tick at a time")
    print()

    for tick in range(5):
        print(f"\n--- Tick {tick + 1} ---")

        state = State()
        state["tick"] = tick + 1

        # Check if we should break at "root" (start of tick)
        # This demonstrates tick-level breakpoints
        if "root" in debugger_tree.breakpoints:
            print("  Breakpoint at root - execution will pause before this tick")

        # Execute with async tick to support pause/resume
        result = await debugger_tree.tick_async(state)

        print(f"  Result: {result}")

        # Get trace
        traces = collector.get_traces()
        if traces:
            trace = traces[-1]
            print(f"  Trace ID: {trace.trace_id[:8]}...")
            print(f"  Executions: {len(trace.executions)} nodes")

        # Reset tree for next tick
        tree.reset()

        # Small delay between ticks
        if tick < 4:
            await asyncio.sleep(0.5)

    print("\n✅ Demo complete!")
    print("Check the visualizer for the execution traces.")

    # Disconnect
    await debugger_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
