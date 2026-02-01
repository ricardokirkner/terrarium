import pytest

from vivarium.core import Condition, NodeStatus, Selector, Sequence

from .helpers import (
    FalseCondition,
    HasKeyCondition,
    IncrementAction,
    SetValueAction,
    TrueCondition,
    ValueCheckCondition,
)


class TestConditionAbstract:
    def test_cannot_instantiate_abstract_condition(self):
        with pytest.raises(TypeError):
            Condition("test")

    def test_must_implement_evaluate(self):
        with pytest.raises(TypeError):

            class MissingEvaluate(Condition):
                pass

            MissingEvaluate("test")


class TestConditionExecution:
    def test_tick_calls_evaluate_and_returns_success_for_true(self):
        condition = TrueCondition("true")
        result = condition.tick({})
        assert result == NodeStatus.SUCCESS

    def test_tick_calls_evaluate_and_returns_failure_for_false(self):
        condition = FalseCondition("false")
        result = condition.tick({})
        assert result == NodeStatus.FAILURE

    def test_condition_never_returns_running(self):
        # Conditions should never return RUNNING
        # They always complete immediately
        true_cond = TrueCondition("true")
        false_cond = FalseCondition("false")

        assert true_cond.tick({}) != NodeStatus.RUNNING
        assert false_cond.tick({}) != NodeStatus.RUNNING

    def test_name_is_stored(self):
        condition = TrueCondition("my_condition")
        assert condition.name == "my_condition"


class TestConditionReset:
    def test_default_reset_does_nothing(self):
        condition = TrueCondition("test")
        # Should not raise
        condition.reset()


class TestConditionIsNode:
    def test_condition_is_subclass_of_node(self):
        from vivarium.core import Node

        assert issubclass(Condition, Node)

    def test_condition_can_be_used_in_composite(self):
        cond1 = TrueCondition("cond1")
        cond2 = TrueCondition("cond2")

        seq = Sequence("seq", [cond1, cond2])
        result = seq.tick({})

        assert result == NodeStatus.SUCCESS


@pytest.mark.integration
class TestActionsAndConditionsIntegration:
    """Integration tests for behavior trees with actions and conditions."""

    def test_sequence_with_condition_guard(self):
        """Sequence that only executes action if condition passes."""
        condition = ValueCheckCondition("has_health", "health", 0)
        action = SetValueAction("attack", "attacked", True)

        tree = Sequence("guarded_attack", [condition, action])

        # With health > 0, both condition and action succeed
        state = {"health": 50}
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state["attacked"] is True

    def test_sequence_with_failing_condition_guard(self):
        """Sequence stops if condition fails."""
        condition = ValueCheckCondition("has_health", "health", 0)
        action = SetValueAction("attack", "attacked", True)

        tree = Sequence("guarded_attack", [condition, action])

        # With health = 0, condition fails and action never runs
        state = {"health": 0}
        result = tree.tick(state)
        assert result == NodeStatus.FAILURE
        assert "attacked" not in state

    def test_selector_with_condition_fallback(self):
        """Selector tries fallback when condition fails."""
        primary_condition = HasKeyCondition("has_target", "target")
        primary_action = SetValueAction("attack", "action", "attack")
        fallback_action = SetValueAction("patrol", "action", "patrol")

        tree = Selector(
            "combat_or_patrol",
            [
                Sequence("attack_sequence", [primary_condition, primary_action]),
                fallback_action,
            ],
        )

        # With target, attacks
        state = {"target": "enemy"}
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state["action"] == "attack"

        # Without target, patrols
        state = {}
        tree.reset()
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state["action"] == "patrol"

    def test_complex_tree_with_multiple_conditions(self):
        """Complex tree with multiple conditions and actions."""
        # If has health AND has target -> attack
        # Else if has health -> patrol
        # Else -> rest

        has_health = ValueCheckCondition("has_health", "health", 0)
        has_target = HasKeyCondition("has_target", "target")
        attack = SetValueAction("attack", "action", "attack")
        patrol = SetValueAction("patrol", "action", "patrol")
        rest = SetValueAction("rest", "action", "rest")

        tree = Selector(
            "ai",
            [
                Sequence("attack_branch", [has_health, has_target, attack]),
                Sequence(
                    "patrol_branch",
                    [ValueCheckCondition("has_health2", "health", 0), patrol],
                ),
                rest,
            ],
        )

        # Has health and target -> attack
        state = {"health": 50, "target": "enemy"}
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state["action"] == "attack"

        # Has health but no target -> patrol
        tree.reset()
        state = {"health": 50}
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state["action"] == "patrol"

        # No health -> rest
        tree.reset()
        state = {"health": 0}
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state["action"] == "rest"

    def test_condition_does_not_modify_state(self):
        """Verify that conditions don't modify state."""
        condition = ValueCheckCondition("check", "value", 10)
        state = {"value": 15}
        state_copy = state.copy()

        condition.tick(state)

        assert state == state_copy

    def test_action_modifies_state(self):
        """Verify that actions can modify state."""
        action = IncrementAction("increment", "counter")
        state = {"counter": 0}

        action.tick(state)
        assert state["counter"] == 1

        action.tick(state)
        assert state["counter"] == 2
