import pytest

from core import Action, Condition, NodeStatus, Sequence


class AlwaysTrueCondition(Condition):
    """A condition that always returns True."""

    def evaluate(self, state) -> bool:
        return True


class AlwaysFalseCondition(Condition):
    """A condition that always returns False."""

    def evaluate(self, state) -> bool:
        return False


class ValueCheckCondition(Condition):
    """A condition that checks if a value in state exceeds a threshold."""

    def __init__(self, name: str, key: str, threshold: float):
        super().__init__(name)
        self.key = key
        self.threshold = threshold

    def evaluate(self, state) -> bool:
        return state.get(self.key, 0) > self.threshold


class HasKeyCondition(Condition):
    """A condition that checks if a key exists in state."""

    def __init__(self, name: str, key: str):
        super().__init__(name)
        self.key = key

    def evaluate(self, state) -> bool:
        return self.key in state


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
        condition = AlwaysTrueCondition("true")
        result = condition.tick({})
        assert result == NodeStatus.SUCCESS

    def test_tick_calls_evaluate_and_returns_failure_for_false(self):
        condition = AlwaysFalseCondition("false")
        result = condition.tick({})
        assert result == NodeStatus.FAILURE

    def test_condition_never_returns_running(self):
        # Conditions should never return RUNNING
        # They always complete immediately
        true_cond = AlwaysTrueCondition("true")
        false_cond = AlwaysFalseCondition("false")

        assert true_cond.tick({}) != NodeStatus.RUNNING
        assert false_cond.tick({}) != NodeStatus.RUNNING

    def test_name_is_stored(self):
        condition = AlwaysTrueCondition("my_condition")
        assert condition.name == "my_condition"


class TestConditionReset:
    def test_default_reset_does_nothing(self):
        condition = AlwaysTrueCondition("test")
        # Should not raise
        condition.reset()


class TestConditionIsNode:
    def test_condition_is_subclass_of_node(self):
        from core import Node

        assert issubclass(Condition, Node)

    def test_condition_can_be_used_in_composite(self):
        cond1 = AlwaysTrueCondition("cond1")
        cond2 = AlwaysTrueCondition("cond2")

        seq = Sequence("seq", [cond1, cond2])
        result = seq.tick({})

        assert result == NodeStatus.SUCCESS


class TestAlwaysTrueCondition:
    def test_returns_true(self):
        condition = AlwaysTrueCondition("true")
        assert condition.evaluate({}) is True

    def test_tick_returns_success(self):
        condition = AlwaysTrueCondition("true")
        assert condition.tick({}) == NodeStatus.SUCCESS


class TestAlwaysFalseCondition:
    def test_returns_false(self):
        condition = AlwaysFalseCondition("false")
        assert condition.evaluate({}) is False

    def test_tick_returns_failure(self):
        condition = AlwaysFalseCondition("false")
        assert condition.tick({}) == NodeStatus.FAILURE


class TestValueCheckCondition:
    def test_returns_true_when_value_exceeds_threshold(self):
        condition = ValueCheckCondition("check", "health", 50)
        state = {"health": 75}
        assert condition.evaluate(state) is True

    def test_returns_false_when_value_equals_threshold(self):
        condition = ValueCheckCondition("check", "health", 50)
        state = {"health": 50}
        assert condition.evaluate(state) is False

    def test_returns_false_when_value_below_threshold(self):
        condition = ValueCheckCondition("check", "health", 50)
        state = {"health": 25}
        assert condition.evaluate(state) is False

    def test_returns_false_when_key_missing(self):
        condition = ValueCheckCondition("check", "health", 50)
        state = {}
        assert condition.evaluate(state) is False

    def test_tick_returns_success_when_condition_true(self):
        condition = ValueCheckCondition("check", "health", 50)
        state = {"health": 75}
        assert condition.tick(state) == NodeStatus.SUCCESS

    def test_tick_returns_failure_when_condition_false(self):
        condition = ValueCheckCondition("check", "health", 50)
        state = {"health": 25}
        assert condition.tick(state) == NodeStatus.FAILURE


class TestHasKeyCondition:
    def test_returns_true_when_key_exists(self):
        condition = HasKeyCondition("check", "target")
        state = {"target": "enemy"}
        assert condition.evaluate(state) is True

    def test_returns_true_when_key_exists_with_none_value(self):
        condition = HasKeyCondition("check", "target")
        state = {"target": None}
        assert condition.evaluate(state) is True

    def test_returns_false_when_key_missing(self):
        condition = HasKeyCondition("check", "target")
        state = {}
        assert condition.evaluate(state) is False

    def test_tick_returns_success_when_key_exists(self):
        condition = HasKeyCondition("check", "target")
        state = {"target": "enemy"}
        assert condition.tick(state) == NodeStatus.SUCCESS

    def test_tick_returns_failure_when_key_missing(self):
        condition = HasKeyCondition("check", "target")
        state = {}
        assert condition.tick(state) == NodeStatus.FAILURE


# Helper action for integration tests
class SetValueAction(Action):
    """An action that sets a value in state."""

    def __init__(self, name: str, key: str, value):
        super().__init__(name)
        self.key = key
        self.value = value

    def execute(self, state) -> NodeStatus:
        state[self.key] = self.value
        return NodeStatus.SUCCESS


class IncrementAction(Action):
    """An action that increments a value in state."""

    def __init__(self, name: str, key: str):
        super().__init__(name)
        self.key = key

    def execute(self, state) -> NodeStatus:
        state[self.key] = state.get(self.key, 0) + 1
        return NodeStatus.SUCCESS
