"""Demonstration of breakpoint debugging with Treehouse.

This example shows how to use the DebuggerTree with breakpoints
to pause and step through behavior tree execution.

Usage:
    # Terminal 1: Start the visualizer
    make visualizer

    # Terminal 2: Run this example
    python examples/breakpoint_demo.py

    # In browser: http://localhost:8000
    # - Right-click on nodes to set breakpoints (red dot will appear)
    # - Click Pause/Resume/Step buttons to control execution
    # - Watch execution pause at breakpoints
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

    # Run multiple ticks to show breakpoint behavior
    for tick in range(3):
        print(f"\n--- Tick {tick + 1} ---")

        state = State()
        state["tick"] = tick + 1

        # Execute with async tick to support breakpoints
        result = await debugger_tree.tick_async(state)

        print(f"Result: {result}")

        # Get trace
        traces = collector.get_traces()
        if traces:
            trace = traces[-1]
            print(f"Trace ID: {trace.trace_id}")
            print(f"Executions: {len(trace.executions)}")

        # Reset tree for next tick
        tree.reset()

        # Wait a bit between ticks
        if tick < 2:
            await asyncio.sleep(1)

    print("\n✅ Demo complete!")
    print("Check the visualizer for the execution traces.")

    # Disconnect
    await debugger_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
