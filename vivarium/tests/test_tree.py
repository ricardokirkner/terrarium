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

from .helpers import (
    FailureAction,
    FalseCondition,
    IncrementAction,
    RunningAction,
    SetValueAction,
    SuccessAction,
    TrueCondition,
)


class TestBehaviorTreeCreation:
    """Test creating BehaviorTree with different root nodes."""

    def test_create_with_action_root(self):
        action = SuccessAction("root")
        tree = BehaviorTree(action)
        assert tree.root is action

    def test_create_with_condition_root(self):
        condition = TrueCondition("root")
        tree = BehaviorTree(condition)
        assert tree.root is condition

    def test_create_with_sequence_root(self):
        seq = Sequence("root", [SuccessAction("a1"), SuccessAction("a2")])
        tree = BehaviorTree(seq)
        assert tree.root is seq

    def test_create_with_selector_root(self):
        sel = Selector("root", [FailureAction("a1"), SuccessAction("a2")])
        tree = BehaviorTree(sel)
        assert tree.root is sel

    def test_initial_tick_count_is_zero(self):
        tree = BehaviorTree(SuccessAction("root"))
        assert tree.tick_count == 0


class TestBehaviorTreeTick:
    """Test ticking the behavior tree."""

    def test_tick_returns_root_status_success(self):
        tree = BehaviorTree(SuccessAction("root"))
        result = tree.tick({})
        assert result == NodeStatus.SUCCESS

    def test_tick_returns_root_status_failure(self):
        tree = BehaviorTree(FailureAction("root"))
        result = tree.tick({})
        assert result == NodeStatus.FAILURE

    def test_tick_returns_root_status_running(self):
        tree = BehaviorTree(RunningAction("root"))
        result = tree.tick({})
        assert result == NodeStatus.RUNNING

    def test_tick_increments_tick_count(self):
        tree = BehaviorTree(SuccessAction("root"))
        assert tree.tick_count == 0

        tree.tick({})
        assert tree.tick_count == 1

        tree.tick({})
        assert tree.tick_count == 2

        tree.tick({})
        assert tree.tick_count == 3


class TestBehaviorTreeStatePassthrough:
    """Test that state is passed through correctly."""

    def test_state_passed_to_root(self):
        action = IncrementAction("inc", "counter")
        tree = BehaviorTree(action)
        state = {"counter": 0}

        tree.tick(state)

        assert state["counter"] == 1

    def test_state_passed_through_sequence(self):
        seq = Sequence(
            "root",
            [
                SetValueAction("set", "a", 1),
                SetValueAction("set", "b", 2),
            ],
        )
        tree = BehaviorTree(seq)
        state = {}

        tree.tick(state)

        assert state["a"] == 1
        assert state["b"] == 2

    def test_state_object_passed_through(self):
        action = IncrementAction("inc", "counter")
        tree = BehaviorTree(action)
        state = State()
        state.set("counter", 10)

        tree.tick(state)

        assert state.get("counter") == 11


class TestBehaviorTreeMultipleTicks:
    """Test multiple ticks modify state correctly."""

    def test_multiple_ticks_accumulate_state_changes(self):
        action = IncrementAction("inc", "counter")
        tree = BehaviorTree(action)
        state = {"counter": 0}

        tree.tick(state)
        assert state["counter"] == 1

        tree.tick(state)
        assert state["counter"] == 2

        tree.tick(state)
        assert state["counter"] == 3

    def test_sequence_needs_reset_between_complete_runs(self):
        seq = Sequence(
            "root",
            [
                IncrementAction("inc1", "counter"),
                IncrementAction("inc2", "counter"),
            ],
        )
        tree = BehaviorTree(seq)
        state = {"counter": 0}

        # First complete run
        tree.tick(state)
        assert state["counter"] == 2

        # Second tick - sequence auto-resets after completion, runs again
        tree.tick(state)
        assert state["counter"] == 4  # Runs again from start

        # Explicit reset has same effect (already at start)
        tree.reset()
        tree.tick(state)
        assert state["counter"] == 6


class TestBehaviorTreeReset:
    """Test reset functionality."""

    def test_reset_preserves_tick_count(self):
        tree = BehaviorTree(SuccessAction("root"))
        tree.tick({})
        tree.tick({})
        assert tree.tick_count == 2

        tree.reset()
        assert tree.tick_count == 2  # tick_count is preserved across reset

    def test_reset_resets_root_node(self):
        """Reset clears any partial progress (e.g., from RUNNING children)."""
        seq = Sequence(
            "root",
            [
                SuccessAction("a1"),
                RunningAction("a2"),  # Returns RUNNING, so sequence doesn't complete
            ],
        )
        tree = BehaviorTree(seq)

        tree.tick({})
        assert seq.current_index == 1  # Paused at second child

        tree.reset()
        assert seq.current_index == 0  # Reset back to start


@pytest.mark.integration
class TestBehaviorTreeIntegration:
    """Integration tests for BehaviorTree with state changes."""

    def test_ai_behavior_with_state(self):
        """Simulate an AI that attacks if it has health, otherwise rests."""

        class HasHealthCondition(Condition):
            def evaluate(self, state) -> bool:
                return state.get("health", 0) > 0

        class AttackAction(Action):
            def execute(self, state) -> NodeStatus:
                state["action"] = "attack"
                return NodeStatus.SUCCESS

        class RestAction(Action):
            def execute(self, state) -> NodeStatus:
                state["action"] = "rest"
                return NodeStatus.SUCCESS

        tree = BehaviorTree(
            Selector(
                "ai",
                [
                    Sequence(
                        "attack_branch",
                        [HasHealthCondition("has_health"), AttackAction("attack")],
                    ),
                    RestAction("rest"),
                ],
            )
        )

        # With health, attacks
        state = State({"health": 100})
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state.get("action") == "attack"

        # Without health, rests
        tree.reset()
        state = State({"health": 0})
        result = tree.tick(state)
        assert result == NodeStatus.SUCCESS
        assert state.get("action") == "rest"

    def test_tick_count_tracks_behavior_iterations(self):
        """Track how many times the tree has been evaluated."""
        tree = BehaviorTree(
            Sequence(
                "root",
                [
                    IncrementAction("inc", "ticks"),
                ],
            )
        )
        state = State()

        for _ in range(5):
            tree.tick(state)
            tree.reset()

        assert tree.tick_count == 5  # tick_count preserved across resets
        assert state.get("ticks") == 5  # State also persists

    def test_complex_tree_with_multiple_levels(self):
        """Test a complex tree structure."""
        tree = BehaviorTree(
            Selector(
                "root",
                [
                    Sequence(
                        "seq1",
                        [
                            FalseCondition("fail"),
                            SetValueAction("set", "branch", "seq1"),
                        ],
                    ),
                    Sequence(
                        "seq2",
                        [
                            TrueCondition("pass"),
                            SetValueAction("set", "branch", "seq2"),
                        ],
                    ),
                    SetValueAction("set", "branch", "fallback"),
                ],
            )
        )

        state = State()
        result = tree.tick(state)

        assert result == NodeStatus.SUCCESS
        assert state.get("branch") == "seq2"  # First seq fails, second succeeds
