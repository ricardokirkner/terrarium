import pytest

from core import Action, NodeStatus


class ConcreteSuccessAction(Action):
    """An action that always returns SUCCESS."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.SUCCESS


class ConcreteFailureAction(Action):
    """An action that always returns FAILURE."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.FAILURE


class ConcreteRunningAction(Action):
    """An action that always returns RUNNING."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.RUNNING


class StateModifyingAction(Action):
    """An action that modifies state."""

    def execute(self, state) -> NodeStatus:
        state["action_executed"] = True
        return NodeStatus.SUCCESS


class CountingAction(Action):
    """An action that counts how many times it was executed."""

    def __init__(self, name: str):
        super().__init__(name)
        self.execute_count = 0

    def execute(self, state) -> NodeStatus:
        self.execute_count += 1
        return NodeStatus.SUCCESS

    def reset(self):
        self.execute_count = 0


class TestActionAbstract:
    def test_cannot_instantiate_abstract_action(self):
        with pytest.raises(TypeError):
            Action("test")

    def test_must_implement_execute(self):
        with pytest.raises(TypeError):

            class MissingExecute(Action):
                pass

            MissingExecute("test")


class TestActionExecution:
    def test_tick_calls_execute(self):
        action = CountingAction("counting")
        assert action.execute_count == 0

        action.tick({})
        assert action.execute_count == 1

        action.tick({})
        assert action.execute_count == 2

    def test_tick_returns_execute_result_success(self):
        action = ConcreteSuccessAction("success")
        result = action.tick({})
        assert result == NodeStatus.SUCCESS

    def test_tick_returns_execute_result_failure(self):
        action = ConcreteFailureAction("failure")
        result = action.tick({})
        assert result == NodeStatus.FAILURE

    def test_tick_returns_execute_result_running(self):
        action = ConcreteRunningAction("running")
        result = action.tick({})
        assert result == NodeStatus.RUNNING

    def test_execute_receives_state(self):
        action = StateModifyingAction("modifier")
        state = {"initial": True}

        action.tick(state)

        assert state["action_executed"] is True
        assert state["initial"] is True

    def test_name_is_stored(self):
        action = ConcreteSuccessAction("my_action")
        assert action.name == "my_action"


class TestActionReset:
    def test_default_reset_does_nothing(self):
        action = ConcreteSuccessAction("test")
        # Should not raise
        action.reset()

    def test_custom_reset_is_called(self):
        action = CountingAction("counting")
        action.tick({})
        action.tick({})
        assert action.execute_count == 2

        action.reset()
        assert action.execute_count == 0


class TestActionIsNode:
    def test_action_is_subclass_of_node(self):
        from core import Node

        assert issubclass(Action, Node)

    def test_action_can_be_used_in_composite(self):
        from core import Sequence

        action1 = ConcreteSuccessAction("action1")
        action2 = ConcreteSuccessAction("action2")

        seq = Sequence("seq", [action1, action2])
        result = seq.tick({})

        assert result == NodeStatus.SUCCESS


# Concrete action implementations for common use cases


class AlwaysSucceedAction(Action):
    """An action that always succeeds."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.SUCCESS


class AlwaysFailAction(Action):
    """An action that always fails."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.FAILURE


class RunningAction(Action):
    """An action that always returns RUNNING."""

    def execute(self, state) -> NodeStatus:
        return NodeStatus.RUNNING


class CounterAction(Action):
    """An action that increments a counter in state."""

    def __init__(self, name: str, key: str = "counter"):
        super().__init__(name)
        self.key = key

    def execute(self, state) -> NodeStatus:
        state[self.key] = state.get(self.key, 0) + 1
        return NodeStatus.SUCCESS


class SetValueAction(Action):
    """An action that sets a value in state."""

    def __init__(self, name: str, key: str, value):
        super().__init__(name)
        self.key = key
        self.value = value

    def execute(self, state) -> NodeStatus:
        state[self.key] = self.value
        return NodeStatus.SUCCESS


class TestAlwaysSucceedAction:
    def test_returns_success(self):
        action = AlwaysSucceedAction("succeed")
        result = action.tick({})
        assert result == NodeStatus.SUCCESS


class TestAlwaysFailAction:
    def test_returns_failure(self):
        action = AlwaysFailAction("fail")
        result = action.tick({})
        assert result == NodeStatus.FAILURE


class TestRunningAction:
    def test_returns_running(self):
        action = RunningAction("running")
        result = action.tick({})
        assert result == NodeStatus.RUNNING


class TestCounterAction:
    def test_increments_counter_in_state(self):
        action = CounterAction("counter")
        state = {}

        action.tick(state)
        assert state["counter"] == 1

        action.tick(state)
        assert state["counter"] == 2

    def test_uses_custom_key(self):
        action = CounterAction("counter", key="my_counter")
        state = {}

        action.tick(state)
        assert state["my_counter"] == 1

    def test_initializes_counter_if_missing(self):
        action = CounterAction("counter")
        state = {}

        action.tick(state)
        assert state["counter"] == 1


class TestSetValueAction:
    def test_sets_value_in_state(self):
        action = SetValueAction("setter", "key", "value")
        state = {}

        action.tick(state)
        assert state["key"] == "value"

    def test_overwrites_existing_value(self):
        action = SetValueAction("setter", "key", "new_value")
        state = {"key": "old_value"}

        action.tick(state)
        assert state["key"] == "new_value"

    def test_sets_various_types(self):
        state = {}

        SetValueAction("int", "int_key", 42).tick(state)
        SetValueAction("list", "list_key", [1, 2, 3]).tick(state)
        SetValueAction("dict", "dict_key", {"nested": True}).tick(state)

        assert state["int_key"] == 42
        assert state["list_key"] == [1, 2, 3]
        assert state["dict_key"] == {"nested": True}
