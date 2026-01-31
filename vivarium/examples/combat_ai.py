#!/usr/bin/env python3
"""Example: Combat AI using behavior trees.

This example demonstrates a simple combat AI that:
- Heals when health is low (< 50)
- Attacks when health is sufficient (>= 50)

The behavior tree structure:
    Selector
    ├── Sequence (heal branch)
    │   ├── LowHealthCondition (health < 50)
    │   └── HealAction (+20 health)
    └── AttackAction (deals damage, takes damage if enemy is active)

Usage:
    python examples/combat_ai.py [options]

Options:
    --health INT          Starting health (1-100, default: random)
    --enemy-health INT    Enemy starting health (1-100, default: random)
    --damage-dealt INT    Damage dealt per attack (1-50, default: random)
    --damage-taken INT    Damage taken per attack (0-50, default: random)
    --passive-enemy       Enemy doesn't counterattack (default: active)
    --seed INT            Random seed for reproducibility
"""

import argparse
import random
import sys
from pathlib import Path

# Add parent directory to path so we can import vivarium
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vivarium.core import (
    Action,
    BehaviorTree,
    Condition,
    NodeStatus,
    Selector,
    Sequence,
    State,
)

# Conditions


class LowHealthCondition(Condition):
    """Check if health is below threshold."""

    def __init__(self, name: str, threshold: int = 50):
        super().__init__(name)
        self.threshold = threshold

    def evaluate(self, state) -> bool:
        health = state.get("health", 0)
        is_low = health < self.threshold
        print(
            f"  [{self.name}] Health={health}, threshold={self.threshold}, low={is_low}"
        )
        return is_low


# Actions


class HealAction(Action):
    """Heal the agent."""

    def __init__(self, name: str, amount: int = 20):
        super().__init__(name)
        self.amount = amount

    def execute(self, state) -> NodeStatus:
        old_health = state.get("health", 0)
        new_health = min(100, old_health + self.amount)  # Cap at 100
        state["health"] = new_health
        state["last_action"] = "heal"
        print(
            f"  [{self.name}] Healed {new_health - old_health} "
            "HP: {old_health} -> {new_health}"
        )
        return NodeStatus.SUCCESS


class AttackAction(Action):
    """Attack an enemy (and take some damage in return if enemy is active)."""

    def __init__(self, name: str, damage_dealt: int = 10, damage_taken: int = 5):
        super().__init__(name)
        self.damage_dealt = damage_dealt
        self.damage_taken = damage_taken

    def execute(self, state) -> NodeStatus:
        # Deal damage to enemy
        enemy_health = state.get("enemy_health", 100)
        enemy_health = max(0, enemy_health - self.damage_dealt)
        state["enemy_health"] = enemy_health

        # Take damage from enemy counterattack (if enemy is active)
        old_health = state.get("health", 100)
        passive_enemy = state.get("passive_enemy", False)

        if passive_enemy:
            new_health = old_health
            damage_msg = "enemy passive, no damage taken"
        else:
            new_health = max(0, old_health - self.damage_taken)
            damage_msg = (
                f"took {self.damage_taken} damage: health {old_health} -> {new_health}"
            )

        state["health"] = new_health
        state["last_action"] = "attack"

        print(
            f"  [{self.name}] Attacked for {self.damage_dealt} damage, "
            f"{damage_msg}, enemy health -> {enemy_health}"
        )
        return NodeStatus.SUCCESS


def build_combat_tree(damage_dealt: int, damage_taken: int) -> BehaviorTree:
    """Build the combat AI behavior tree.

    Args:
        damage_dealt: Damage dealt per attack.
        damage_taken: Damage taken per attack (if enemy is active).
    """
    return BehaviorTree(
        Selector(
            "combat_ai",
            [
                # Heal branch: if health < 50, heal
                Sequence(
                    "heal_branch",
                    [
                        LowHealthCondition("check_low_health", threshold=50),
                        HealAction("heal", amount=20),
                    ],
                ),
                # Attack branch: otherwise attack
                AttackAction(
                    "attack", damage_dealt=damage_dealt, damage_taken=damage_taken
                ),
            ],
        )
    )


def print_state(state: State, label: str = "State") -> None:
    """Print current state."""
    print(f"{label}:")
    print(f"  health: {state.get('health', 'N/A')}")
    print(f"  enemy_health: {state.get('enemy_health', 'N/A')}")
    print(f"  last_action: {state.get('last_action', 'N/A')}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Combat AI behavior tree example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with random values
  python examples/combat_ai.py

  # Run with specific values
  python examples/combat_ai.py --health 80 --enemy-health 60

  # Run with passive enemy (no counterattack)
  python examples/combat_ai.py --passive-enemy

  # Run with reproducible random values
  python examples/combat_ai.py --seed 42
        """,
    )
    parser.add_argument(
        "--health",
        type=int,
        default=None,
        help="Starting health (1-100, default: random 50-100)",
    )
    parser.add_argument(
        "--enemy-health",
        type=int,
        default=None,
        help="Enemy starting health (1-100, default: random 50-100)",
    )
    parser.add_argument(
        "--damage-dealt",
        type=int,
        default=None,
        help="Damage dealt per attack (1-50, default: random 5-20)",
    )
    parser.add_argument(
        "--damage-taken",
        type=int,
        default=None,
        help="Damage taken per attack (0-50, default: random 3-15)",
    )
    parser.add_argument(
        "--passive-enemy",
        action="store_true",
        help="Enemy doesn't counterattack (default: active enemy)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    return parser.parse_args()


def main():
    """Run the combat AI example."""
    args = parse_args()

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)

    # Determine values (use provided or generate random)
    health = args.health if args.health is not None else random.randint(50, 100)
    enemy_health = (
        args.enemy_health if args.enemy_health is not None else random.randint(50, 100)
    )
    damage_dealt = (
        args.damage_dealt if args.damage_dealt is not None else random.randint(5, 20)
    )
    damage_taken = (
        args.damage_taken if args.damage_taken is not None else random.randint(3, 15)
    )
    passive_enemy = args.passive_enemy

    # Clamp values to valid ranges
    health = max(1, min(100, health))
    enemy_health = max(1, min(100, enemy_health))
    damage_dealt = max(1, min(50, damage_dealt))
    damage_taken = max(0, min(50, damage_taken))

    print("=" * 60)
    print("Combat AI Behavior Tree Example")
    print("=" * 60)
    print()
    print("Tree structure:")
    print("  Selector")
    print("  ├── Sequence (heal if low health)")
    print("  │   ├── LowHealthCondition (health < 50)")
    print("  │   └── HealAction (+20 HP)")
    print(
        f"  └── AttackAction (deal {damage_dealt} damage, take {damage_taken} damage)"
    )
    print()
    print("Configuration:")
    print(f"  Starting health: {health}")
    print(f"  Enemy health: {enemy_health}")
    print(f"  Damage dealt: {damage_dealt}")
    print(f"  Damage taken: {damage_taken}")
    print(f"  Enemy type: {'passive' if passive_enemy else 'active'}")
    if args.seed is not None:
        print(f"  Random seed: {args.seed}")
    print()

    # Build tree and initialize state
    tree = build_combat_tree(damage_dealt=damage_dealt, damage_taken=damage_taken)
    state = State(
        {
            "health": health,
            "enemy_health": enemy_health,
            "passive_enemy": passive_enemy,
        }
    )

    print("=" * 60)
    print("Initial State")
    print("=" * 60)
    print_state(state)
    print()

    # Run multiple ticks
    num_ticks = 50  # Increased to allow for longer battles
    tick = 0
    for tick in range(1, num_ticks + 1):
        print("=" * 60)
        print(f"Tick {tick} (tree tick_count: {tree.tick_count})")
        print("=" * 60)

        # Reset tree for clean execution each tick
        tree.reset()

        print("Executing tree:")
        result = tree.tick(state)
        print(f"  Result: {result.value}")
        print()

        print_state(state, "State after tick")
        print()

        # Check win/lose conditions
        if state.get("health", 0) <= 0:
            print("*** DEFEAT: Agent has died! ***")
            break
        if state.get("enemy_health", 0) <= 0:
            print("*** VICTORY: Enemy defeated! ***")
            break

    print("=" * 60)
    print("Final Summary")
    print("=" * 60)
    print(f"Total ticks: {tick}")
    print_state(state, "Final state")


if __name__ == "__main__":
    main()
