"""Tests that run examples to ensure they work correctly.

These tests catch issues that unit tests with mocks might miss,
by exercising real workflows end-to-end.
"""

import pytest

from vivarium.core import (
    Action,
    BehaviorTree,
    Condition,
    NodeStatus,
    Selector,
    Sequence,
    State,
)


class LowHealthCondition(Condition):
    """Check if health is below threshold."""

    def __init__(self, name: str, threshold: int = 50):
        super().__init__(name)
        self.threshold = threshold

    def evaluate(self, state) -> bool:
        return state.get("health", 0) < self.threshold


class HealAction(Action):
    """Heal the agent."""

    def __init__(self, name: str, amount: int = 20):
        super().__init__(name)
        self.amount = amount

    def execute(self, state) -> NodeStatus:
        old_health = state.get("health", 0)
        new_health = min(100, old_health + self.amount)
        state["health"] = new_health
        state["last_action"] = "heal"
        state["heal_count"] = state.get("heal_count", 0) + 1
        return NodeStatus.SUCCESS


class AttackAction(Action):
    """Attack an enemy."""

    def __init__(self, name: str, damage_dealt: int = 10, damage_taken: int = 5):
        super().__init__(name)
        self.damage_dealt = damage_dealt
        self.damage_taken = damage_taken

    def execute(self, state) -> NodeStatus:
        # Deal damage to enemy
        enemy_health = state.get("enemy_health", 100)
        state["enemy_health"] = max(0, enemy_health - self.damage_dealt)

        # Take damage (if enemy is active)
        if not state.get("passive_enemy", False):
            old_health = state.get("health", 100)
            state["health"] = max(0, old_health - self.damage_taken)

        state["last_action"] = "attack"
        state["attack_count"] = state.get("attack_count", 0) + 1
        return NodeStatus.SUCCESS


def build_combat_tree(damage_dealt: int = 10, damage_taken: int = 5) -> BehaviorTree:
    """Build the combat AI behavior tree."""
    return BehaviorTree(
        Selector(
            "combat_ai",
            [
                Sequence(
                    "heal_branch",
                    [
                        LowHealthCondition("check_low_health", threshold=50),
                        HealAction("heal", amount=20),
                    ],
                ),
                AttackAction(
                    "attack", damage_dealt=damage_dealt, damage_taken=damage_taken
                ),
            ],
        )
    )


@pytest.mark.integration
class TestCombatAIExample:
    """Test the combat AI example end-to-end."""

    def test_victory_scenario(self):
        """Agent should defeat enemy when conditions are favorable."""
        tree = build_combat_tree(damage_dealt=10, damage_taken=5)
        state = State(
            {
                "health": 100,
                "enemy_health": 50,
            }
        )

        ticks = 0
        while state.get("enemy_health", 0) > 0 and state.get("health", 0) > 0:
            tree.tick(state)
            ticks += 1
            if ticks > 100:
                pytest.fail("Game loop exceeded 100 ticks")

        assert state.get("enemy_health") == 0
        assert state.get("health") > 0
        assert tree.tick_count == ticks

    def test_defeat_scenario(self):
        """Agent should lose when damage taken exceeds survivability."""
        tree = build_combat_tree(damage_dealt=5, damage_taken=50)
        state = State(
            {
                "health": 50,
                "enemy_health": 100,
            }
        )

        ticks = 0
        while state.get("enemy_health", 0) > 0 and state.get("health", 0) > 0:
            tree.tick(state)
            ticks += 1
            if ticks > 100:
                pytest.fail("Game loop exceeded 100 ticks")

        assert state.get("health") == 0
        assert state.get("enemy_health") > 0
        assert tree.tick_count == ticks

    def test_heal_attack_alternation(self):
        """Agent should alternate between heal and attack when health oscillates."""
        tree = build_combat_tree(damage_dealt=10, damage_taken=15)
        state = State(
            {
                "health": 60,
                "enemy_health": 100,
                "heal_count": 0,
                "attack_count": 0,
            }
        )

        ticks = 0
        while state.get("enemy_health", 0) > 0 and state.get("health", 0) > 0:
            tree.tick(state)
            ticks += 1
            if ticks > 100:
                pytest.fail("Game loop exceeded 100 ticks")

        # Should have both healed and attacked multiple times
        assert state.get("heal_count", 0) >= 1
        assert state.get("attack_count", 0) >= 1
        assert tree.tick_count == ticks

    def test_passive_enemy_no_damage_taken(self):
        """Agent should take no damage when enemy is passive."""
        tree = build_combat_tree(damage_dealt=10, damage_taken=5)
        state = State(
            {
                "health": 100,
                "enemy_health": 30,
                "passive_enemy": True,
            }
        )

        initial_health = state.get("health")

        ticks = 0
        while state.get("enemy_health", 0) > 0:
            tree.tick(state)
            ticks += 1
            if ticks > 100:
                pytest.fail("Game loop exceeded 100 ticks")

        assert state.get("enemy_health") == 0
        assert state.get("health") == initial_health  # No damage taken
        assert tree.tick_count == ticks

    def test_tick_count_accumulates_across_resets(self):
        """tick_count must accumulate even when reset() is called between ticks.

        This is the key test that would have caught the reset() bug.
        """
        tree = build_combat_tree()
        state = State(
            {
                "health": 100,
                "enemy_health": 100,
            }
        )

        # Run exactly 10 ticks with reset between each
        for i in range(10):
            tree.reset()
            tree.tick(state)
            # Verify tick_count after each tick
            assert tree.tick_count == i + 1, (
                f"After tick {i + 1}, tick_count should be {i + 1}, "
                f"but was {tree.tick_count}"
            )

    def test_boundary_condition_health_exactly_at_threshold(self):
        """Test behavior when health is exactly at the threshold (50)."""
        tree = build_combat_tree(damage_dealt=10, damage_taken=0)
        state = State(
            {
                "health": 50,  # Exactly at threshold
                "enemy_health": 10,
                "passive_enemy": True,
            }
        )

        tree.tick(state)

        # At exactly 50, condition is "health < 50" which is False
        # So should attack, not heal
        assert state.get("last_action") == "attack"

    def test_boundary_condition_health_just_below_threshold(self):
        """Test behavior when health is just below threshold (49)."""
        tree = build_combat_tree()
        state = State(
            {
                "health": 49,  # Just below threshold
                "enemy_health": 100,
            }
        )

        tree.tick(state)

        # At 49, condition is "health < 50" which is True
        # So should heal
        assert state.get("last_action") == "heal"
        assert state.get("health") == 69  # 49 + 20
