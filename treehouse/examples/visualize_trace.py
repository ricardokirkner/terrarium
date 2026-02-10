#!/usr/bin/env python3
"""Example demonstrating trace visualization.

This script creates a simple behavior tree, runs it, and displays
the execution trace in both tree view and timeline formats.

Usage:
    cd treehouse
    uv run python examples/visualize_trace.py
"""

import time

from vivarium import (
    Action,
    BehaviorTree,
    Condition,
    NodeStatus,
    Selector,
    Sequence,
    State,
)

from treehouse import TraceCollector
from treehouse.visualization import print_timeline, print_trace

# Define some actions and conditions for our example tree


class CheckHealth(Condition):
    """Check if health is above threshold."""

    def __init__(self, threshold: int = 30):
        super().__init__("check_health")
        self.threshold = threshold

    def evaluate(self, state) -> bool:
        return state.get("health", 100) > self.threshold


class Heal(Action):
    """Heal the player."""

    def __init__(self):
        super().__init__("heal")

    def execute(self, state) -> NodeStatus:
        # Simulate some work
        time.sleep(0.01)
        state["health"] = min(100, state.get("health", 0) + 30)
        return NodeStatus.SUCCESS


class Attack(Action):
    """Attack the enemy."""

    def __init__(self):
        super().__init__("attack")

    def execute(self, state) -> NodeStatus:
        # Simulate some work
        time.sleep(0.005)
        state["enemy_health"] = max(0, state.get("enemy_health", 100) - 25)
        return NodeStatus.SUCCESS


class CheckEnemyAlive(Condition):
    """Check if enemy is still alive."""

    def __init__(self):
        super().__init__("enemy_alive")

    def evaluate(self, state) -> bool:
        return state.get("enemy_health", 100) > 0


class Flee(Action):
    """Flee from combat."""

    def __init__(self):
        super().__init__("flee")

    def execute(self, state) -> NodeStatus:
        time.sleep(0.002)
        return NodeStatus.SUCCESS


def main():
    """Run the example."""
    # Create a combat AI behavior tree:
    # - If health is low, try to heal
    # - If enemy is alive, attack
    # - Otherwise flee
    tree = BehaviorTree(
        root=Selector(
            "combat_ai",
            [
                # Low health branch: heal if needed
                Sequence(
                    "heal_if_needed",
                    [
                        CheckHealth(threshold=50),  # Will fail if health <= 50
                        # This branch won't execute if CheckHealth passes
                    ],
                ),
                # Attack branch
                Sequence(
                    "attack_sequence",
                    [
                        CheckEnemyAlive(),
                        Attack(),
                    ],
                ),
                # Fallback: flee
                Flee(),
            ],
        ),
    )

    # Set up the trace collector
    collector = TraceCollector()
    tree_with_collector = BehaviorTree(root=tree.root, emitter=collector)

    # Initial state: player has low health, enemy is alive
    state = State({"health": 40, "enemy_health": 100})

    print("=" * 60)
    print("Combat AI Example - Trace Visualization")
    print("=" * 60)
    print()
    print(
        f"Initial state: health={state['health']}, enemy_health={state['enemy_health']}"
    )
    print()

    # Run a few ticks
    for i in range(3):
        print(f"--- Tick {i + 1} ---")
        result = tree_with_collector.tick(state)
        print(f"Result: {result.value}")
        health = state["health"]
        enemy_health = state["enemy_health"]
        print(f"State after: health={health}, enemy_health={enemy_health}")
        print()

    # Display the traces
    print("=" * 60)
    print("Tree View (most recent trace)")
    print("=" * 60)
    print()

    trace = collector.get_trace()
    if trace:
        print_trace(trace)
        print()

    print("=" * 60)
    print("Timeline View (most recent trace)")
    print("=" * 60)
    print()

    if trace:
        print_timeline(trace, bar_width=30)
        print()

    # Show all traces summary
    print("=" * 60)
    print("All Traces Summary")
    print("=" * 60)
    print()

    for trace in collector.get_traces():
        print(f"Trace #{trace.tick_id}: {trace.status} ({len(trace.executions)} nodes)")


if __name__ == "__main__":
    main()
