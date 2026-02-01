import pytest

from vivarium.core import Action, NodeStatus, Sequence

from .helpers import (
    CountingAction,
    FailureAction,
    RunningAction,
    SetValueAction,
    SuccessAction,
)


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
        action = SuccessAction("success")
        result = action.tick({})
        assert result == NodeStatus.SUCCESS

    def test_tick_returns_execute_result_failure(self):
        action = FailureAction("failure")
        result = action.tick({})
        assert result == NodeStatus.FAILURE

    def test_tick_returns_execute_result_running(self):
        action = RunningAction("running")
        result = action.tick({})
        assert result == NodeStatus.RUNNING

    def test_execute_receives_state(self):
        action = SetValueAction("modifier", "action_executed", True)
        state = {"initial": True}

        action.tick(state)

        assert state["action_executed"] is True
        assert state["initial"] is True

    def test_name_is_stored(self):
        action = SuccessAction("my_action")
        assert action.name == "my_action"


class TestActionReset:
    def test_default_reset_does_nothing(self):
        action = SuccessAction("test")
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
        from vivarium.core import Node

        assert issubclass(Action, Node)

    def test_action_can_be_used_in_composite(self):
        action1 = SuccessAction("action1")
        action2 = SuccessAction("action2")

        seq = Sequence("seq", [action1, action2])
        result = seq.tick({})

        assert result == NodeStatus.SUCCESS
