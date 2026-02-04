#!/usr/bin/env python3
"""Example agent that streams execution to the visualizer.

This example demonstrates:
1. Connecting to the Treehouse Visualizer server
2. Streaming behavior tree execution events in real-time
3. Viewing execution in a web browser

Prerequisites:
1. Start the visualizer server:
   uvicorn treehouse.visualizer.server:app --reload

2. Open http://localhost:8000 in a browser

3. Run this agent:
   python examples/streaming_agent.py

Usage:
    python examples/streaming_agent.py
    python examples/streaming_agent.py --mock  # Use mock LLM provider
"""

import argparse
import asyncio
import sys
import time

from vivarium.core import (
    Action,
    BehaviorTree,
    Condition,
    NodeStatus,
    Selector,
    Sequence,
)

from treehouse import DebuggerClient, TraceCollector, print_trace
from treehouse.llm import (
    LLMAction,
    LLMCondition,
    MockConfig,
    MockLLMProvider,
    OllamaProvider,
)


class SimulatedAction(Action):
    """An action that simulates work with a delay."""

    def __init__(self, name: str, duration: float = 0.5, succeed: bool = True):
        super().__init__(name)
        self.duration = duration
        self.succeed = succeed

    def execute(self, state) -> NodeStatus:
        time.sleep(self.duration)
        return NodeStatus.SUCCESS if self.succeed else NodeStatus.FAILURE


class SimpleCondition(Condition):
    """A condition that checks a state value."""

    def __init__(self, name: str, key: str, expected: bool = True):
        super().__init__(name)
        self.key = key
        self.expected = expected

    def evaluate(self, state) -> bool:
        return state.get(self.key, False) == self.expected


def create_demo_tree(provider):
    """Create a demo behavior tree with mixed node types."""
    # Simple conditions and actions
    check_ready = SimpleCondition("check_ready", "is_ready", True)
    prepare = SimulatedAction("prepare", duration=0.3)
    execute_task = SimulatedAction("execute_task", duration=0.5)

    # LLM nodes
    analyze = LLMCondition(
        name="analyze_input",
        provider=provider,
        question="Is the input '{user_input}' a valid request?",
    )

    respond = LLMAction(
        name="generate_response",
        provider=provider,
        task="Generate a helpful response for: {user_input}",
        output_key="response",
        temperature=0.7,
        max_tokens=100,
    )

    fallback = SimulatedAction("fallback_action", duration=0.2)

    # Build tree structure
    tree = Selector(
        name="main_selector",
        children=[
            Sequence(
                name="main_sequence",
                children=[
                    check_ready,
                    prepare,
                    analyze,
                    respond,
                    execute_task,
                ],
            ),
            fallback,
        ],
    )

    return tree


async def run_agent(provider, server_url: str):
    """Run the agent with streaming to the visualizer."""
    print(f"Connecting to visualizer at {server_url}...")

    async with DebuggerClient(url=server_url) as debugger:
        if not debugger.connected:
            print("Warning: Could not connect to visualizer server.")
            print("Start the server with: uvicorn treehouse.visualizer.server:app")
            print("Continuing without streaming...\n")

        # Create tree and collector
        root = create_demo_tree(provider)
        collector = TraceCollector(debugger=debugger)
        tree = BehaviorTree(root=root, emitter=collector)

        # Set up state
        state = {
            "is_ready": True,
            "user_input": "Tell me a joke about programming",
        }
        collector.set_state(state)

        print("\nExecuting behavior tree...")
        print("-" * 40)

        # Execute the tree
        result = tree.tick(state)

        # Give time for events to stream
        await asyncio.sleep(0.5)

        print(f"\nResult: {result.value}")
        if "response" in state:
            print(f"Response: {state['response']}")

        # Get and display trace
        trace = collector.get_trace()
        if trace:
            print("\n" + "=" * 40)
            print("Execution Trace:")
            print("=" * 40)
            print_trace(trace, show_llm=True)

        return trace


async def main():
    parser = argparse.ArgumentParser(description="Streaming Agent Example")
    parser.add_argument(
        "--server",
        default="ws://localhost:8000/ws/agent",
        help="Visualizer server WebSocket URL",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM provider instead of Ollama",
    )
    parser.add_argument(
        "--model",
        default="llama3.2",
        help="Ollama model name (default: llama3.2)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to run the agent",
    )
    args = parser.parse_args()

    # Create provider
    if args.mock:
        print("Using MockLLMProvider")
        provider = MockLLMProvider(
            MockConfig(
                canned_responses={
                    "valid request": "Yes",
                    "joke": "Why do programmers prefer dark mode? "
                    "Because light attracts bugs!",
                },
                default_response="Yes",
                simulate_delay_ms=100,
            ),
            model="mock-model",
        )
    else:
        print(f"Using OllamaProvider with model: {args.model}")
        provider = OllamaProvider(model=args.model)

    # Run agent
    for i in range(args.repeat):
        if args.repeat > 1:
            print(f"\n{'='*40}")
            print(f"Run {i + 1} of {args.repeat}")
            print("=" * 40)

        await run_agent(provider, args.server)

        if i < args.repeat - 1:
            print("\nWaiting 2 seconds before next run...")
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)
