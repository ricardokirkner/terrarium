"""Interactive demonstration of stepping through tree execution with breakpoints.

This example shows the ACTUAL behavior of breakpoints in Treehouse:
- Breakpoints pause BEFORE the tick that contains the breakpoint node
- You can step through ticks (not individual nodes)
- Multiple breakpoints in one tick will all trigger

Usage:
    # Terminal 1: Start the visualizer
    make visualizer

    # Terminal 2: Run this example
    python examples/breakpoint_stepping.py

    # In browser: http://localhost:8000
    1. Set a breakpoint on any node (click the circle ○)
    2. Watch execution pause BEFORE that tick starts
    3. Click Step to execute one tick at a time
    4. Click Resume to run remaining ticks without stopping

Try these experiments:
- Set breakpoint on first node -> pauses before first tick
- Set breakpoint on middle node -> pauses before that tick
- Set breakpoints on multiple nodes in same tick -> pauses once
- Use Step button to execute one tick at a time
"""

import asyncio

from vivarium import Action, BehaviorTree, NodeStatus, Sequence, State

from treehouse import DebuggerClient, DebuggerTree, TraceCollector


class CounterAction(Action):
    """Action that increments a counter."""

    def __init__(self, name: str):
        super().__init__(name)
        self.execution_count = 0

    def execute(self, state: State) -> NodeStatus:
        self.execution_count += 1
        print(f"  ✓ {self.name} (execution #{self.execution_count})")
        state[f"{self.name}_count"] = self.execution_count
        return NodeStatus.SUCCESS


async def main():
    print("🔍 Breakpoint Stepping Demo")
    print("=" * 60)
    print()
    print("This demo runs the SAME tree 10 times (10 ticks)")
    print("Each tick executes: Step1 -> Step2 -> Step3")
    print()
    print("TRY THIS:")
    print("1. Open http://localhost:8000")
    print("2. Set breakpoint on 'Step2' (click the circle)")
    print("3. Watch execution pause BEFORE each tick")
    print("4. Use Step button to execute one tick at a time")
    print("5. Or click Resume to run all remaining ticks")
    print()
    print("=" * 60)
    print()

    # Build a simple 3-step sequence
    step1 = CounterAction("Step1")
    step2 = CounterAction("Step2")
    step3 = CounterAction("Step3")

    sequence = Sequence("workflow", [step1, step2, step3])

    # Setup collector and debugger
    debugger_client = DebuggerClient(url="ws://localhost:8000/ws/agent")
    collector = TraceCollector()
    collector.set_debugger(debugger_client)

    tree = BehaviorTree(sequence, emitter=collector)
    debugger_tree = DebuggerTree(tree)

    # Set up bidirectional communication
    debugger_client.command_handler = debugger_tree

    # Set up callback to send debugger events back to visualizer
    def send_debugger_event(event_type: str, data: dict):
        """Send debugger events to visualizer."""
        # Use sync send which queues the message
        debugger_client.send_sync({"type": event_type, "data": data})

    debugger_tree.set_command_handler(send_debugger_event)

    # Connect
    await debugger_client.connect()

    if not debugger_client.connected:
        print("❌ Failed to connect to visualizer")
        print("   Run: make visualizer")
        return

    print("✅ Connected to visualizer")
    print()
    print("Starting in 3 seconds...")
    print("Set breakpoints now in the browser!")
    await asyncio.sleep(3)

    # Execute 10 ticks of the same tree
    print("\n" + "=" * 60)
    print("STARTING EXECUTION - 10 ticks")
    print("=" * 60)

    for tick_num in range(1, 11):
        print(f"\n📍 Tick {tick_num}/10")

        state = State()
        state["tick"] = tick_num

        # This will pause if any breakpoints are set
        result = await debugger_tree.tick_async(state)

        print(f"  Status: {result}")

        if tick_num < 10:
            # Small delay between ticks
            await asyncio.sleep(0.3)

    print("\n" + "=" * 60)
    print("✅ All 10 ticks complete!")
    print(f"   Step1 executed: {step1.execution_count} times")
    print(f"   Step2 executed: {step2.execution_count} times")
    print(f"   Step3 executed: {step3.execution_count} times")
    print("=" * 60)

    # Cleanup
    await debugger_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
