import pytest

from core import Action, Condition, NodeStatus, Sequence, State


class TestStateBasicOperations:
    """Test get/set/has operations."""

    def test_set_and_get(self):
        state = State()
        state.set("health", 100)
        assert state.get("health") == 100

    def test_get_with_default(self):
        state = State()
        assert state.get("missing") is None
        assert state.get("missing", 50) == 50

    def test_has_returns_true_for_existing_key(self):
        state = State()
        state.set("health", 100)
        assert state.has("health") is True

    def test_has_returns_false_for_missing_key(self):
        state = State()
        assert state.has("missing") is False

    def test_has_returns_true_for_none_value(self):
        state = State()
        state.set("nullable", None)
        assert state.has("nullable") is True

    def test_bracket_notation_set_and_get(self):
        state = State()
        state["health"] = 100
        assert state["health"] == 100

    def test_in_operator(self):
        state = State()
        state.set("health", 100)
        assert "health" in state
        assert "missing" not in state

    def test_len(self):
        state = State()
        assert len(state) == 0
        state.set("a", 1)
        state.set("b", 2)
        assert len(state) == 2

    def test_iteration(self):
        state = State()
        state.set("a", 1)
        state.set("b", 2)
        keys = list(state)
        assert "a" in keys
        assert "b" in keys

    def test_keys_values_items(self):
        state = State()
        state.set("a", 1)
        state.set("b", 2)

        assert set(state.keys()) == {"a", "b"}
        assert set(state.values()) == {1, 2}
        assert set(state.items()) == {("a", 1), ("b", 2)}

    def test_update(self):
        state = State()
        state.update({"a": 1, "b": 2})
        assert state.get("a") == 1
        assert state.get("b") == 2

    def test_init_with_data(self):
        state = State({"health": 100, "name": "player"})
        assert state.get("health") == 100
        assert state.get("name") == "player"


class TestStateDotNotation:
    """Test dot notation access."""

    def test_dot_notation_set_and_get(self):
        state = State()
        state.health = 100
        assert state.health == 100

    def test_underscore_prefixed_getattr_raises(self):
        state = State()
        with pytest.raises(AttributeError):
            _ = state._private

    def test_dot_notation_mixed_with_methods(self):
        state = State()
        state.health = 100
        assert state.get("health") == 100

        state.set("mana", 50)
        assert state.mana == 50

    def test_dot_notation_with_bracket_notation(self):
        state = State()
        state.health = 100
        assert state["health"] == 100

        state["mana"] = 50
        assert state.mana == 50


class TestStateNestedAccess:
    """Test nested state access."""

    def test_nested_dot_notation_assignment(self):
        state = State()
        state.player.health = 100
        assert state.player.health == 100

    def test_deeply_nested_access(self):
        state = State()
        state.game.player.stats.health = 100
        assert state.game.player.stats.health == 100

    def test_nested_state_is_state_object(self):
        state = State()
        state.player.health = 100
        assert isinstance(state.player, State)

    def test_nested_dict_converted_to_state(self):
        state = State()
        state.set("player", {"health": 100, "mana": 50})
        assert isinstance(state.player, State)
        assert state.player.health == 100
        assert state.player.mana == 50

    def test_init_with_nested_dict(self):
        state = State({"player": {"health": 100, "mana": 50}})
        assert state.player.health == 100
        assert state.player.mana == 50

    def test_to_dict_with_nested_state(self):
        state = State()
        state.player.health = 100
        state.player.mana = 50

        result = state.to_dict()
        assert result == {"player": {"health": 100, "mana": 50}}

    def test_nested_update(self):
        state = State()
        state.player.health = 100
        state.player.update({"mana": 50, "stamina": 75})

        assert state.player.health == 100
        assert state.player.mana == 50
        assert state.player.stamina == 75


class TestStateRepr:
    def test_repr(self):
        state = State()
        state.health = 100
        repr_str = repr(state)
        assert "State" in repr_str
        assert "health" in repr_str


# Helper nodes for integration tests


class SetHealthAction(Action):
    def __init__(self, name: str, value: int):
        super().__init__(name)
        self.value = value

    def execute(self, state) -> NodeStatus:
        state.health = self.value
        return NodeStatus.SUCCESS


class IncrementHealthAction(Action):
    def __init__(self, name: str, amount: int = 1):
        super().__init__(name)
        self.amount = amount

    def execute(self, state) -> NodeStatus:
        current = state.get("health", 0)
        state.health = current + self.amount
        return NodeStatus.SUCCESS


class HealthCheckCondition(Condition):
    def __init__(self, name: str, threshold: int):
        super().__init__(name)
        self.threshold = threshold

    def evaluate(self, state) -> bool:
        return state.get("health", 0) > self.threshold


class SetNestedValueAction(Action):
    def __init__(self, name: str):
        super().__init__(name)

    def execute(self, state) -> NodeStatus:
        state.player.health = 100
        state.player.mana = 50
        return NodeStatus.SUCCESS


@pytest.mark.integration
class TestStateWithNodes:
    """Test that state works with behavior tree nodes."""

    def test_state_persists_across_ticks(self):
        """State accumulates changes across multiple ticks."""
        state = State()
        action = IncrementHealthAction("increment", 10)
        tree = Sequence("seq", [action])

        tree.tick(state)
        assert state.health == 10

        tree.reset()
        tree.tick(state)
        assert state.health == 20

        tree.reset()
        tree.tick(state)
        assert state.health == 30

    def test_tree_reset_does_not_reset_state(self):
        """Tree reset only resets tree internals, not agent state.

        This is by design: the State represents the world/agent which
        persists independently of the behavior tree's execution state.
        """
        state = State()
        state.health = 100

        action = IncrementHealthAction("increment", 10)
        tree = Sequence("seq", [action])

        tree.tick(state)
        assert state.health == 110

        # Reset the tree - this resets current_index, NOT the state
        tree.reset()

        # State is preserved after tree reset
        assert state.health == 110

    def test_nodes_can_modify_state(self):
        state = State()
        action = SetHealthAction("set_health", 100)

        action.tick(state)

        assert state.health == 100

    def test_condition_reads_state(self):
        state = State()
        state.health = 75

        condition = HealthCheckCondition("check", 50)
        result = condition.tick(state)

        assert result == NodeStatus.SUCCESS

    def test_sequence_modifies_then_checks_state(self):
        state = State()
        set_action = SetHealthAction("set", 100)
        check_condition = HealthCheckCondition("check", 50)

        tree = Sequence("seq", [set_action, check_condition])
        result = tree.tick(state)

        assert result == NodeStatus.SUCCESS
        assert state.health == 100

    def test_nested_state_with_nodes(self):
        state = State()
        action = SetNestedValueAction("set_nested")

        action.tick(state)

        assert state.player.health == 100
        assert state.player.mana == 50

    def test_state_passed_through_tree(self):
        state = State()
        state.initial = True

        action1 = SetHealthAction("set1", 50)
        action2 = IncrementHealthAction("inc", 25)

        tree = Sequence("seq", [action1, action2])
        tree.tick(state)

        # Original value preserved
        assert state.initial is True
        # Actions modified state
        assert state.health == 75
