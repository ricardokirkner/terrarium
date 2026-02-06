"""Tests for decorator nodes: Inverter, Repeater, RetryUntilSuccess."""

from vivarium.core import (
    Inverter,
    ListEventEmitter,
    NodeStatus,
    Repeater,
    RetryUntilSuccess,
    State,
)
from vivarium.core.context import ExecutionContext

from .helpers import (
    CountingAction,
    FailureAction,
    MockNode,
    RunningAction,
    SuccessAction,
)

# =============================================================================
# Decorator base class
# =============================================================================


class TestDecoratorBase:
    """Tests for the Decorator abstract base class."""

    def test_decorator_stores_child(self):
        child = MockNode("child")
        # Decorator is abstract (tick not implemented), but we can test
        # init through a concrete subclass
        dec = Inverter("inv", child)
        assert dec.child is child

    def test_decorator_stores_name(self):
        child = MockNode("child")
        dec = Inverter("my_inverter", child)
        assert dec.name == "my_inverter"

    def test_reset_resets_child(self):
        child = MockNode("child")
        child.tick(None)
        assert child.tick_count == 1
        dec = Inverter("inv", child)
        dec.reset()
        assert child._reset_called


# =============================================================================
# Inverter
# =============================================================================


class TestInverter:
    """Tests for the Inverter decorator node."""

    def test_inverts_success_to_failure(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        result = inverter.tick(State())
        assert result == NodeStatus.FAILURE

    def test_inverts_failure_to_success(self):
        child = FailureAction("action")
        inverter = Inverter("inv", child)
        result = inverter.tick(State())
        assert result == NodeStatus.SUCCESS

    def test_running_passes_through(self):
        child = RunningAction("action")
        inverter = Inverter("inv", child)
        result = inverter.tick(State())
        assert result == NodeStatus.RUNNING

    def test_child_is_ticked(self):
        child = CountingAction("counter")
        inverter = Inverter("inv", child)
        inverter.tick(State())
        assert child.execute_count == 1

    def test_multiple_ticks(self):
        child = CountingAction("counter")
        inverter = Inverter("inv", child)
        for _ in range(5):
            inverter.tick(State())
        assert child.execute_count == 5

    def test_reset_resets_child(self):
        child = CountingAction("counter")
        inverter = Inverter("inv", child)
        inverter.tick(State())
        inverter.reset()
        assert child.execute_count == 0


class TestInverterEvents:
    """Tests for event emission from Inverter."""

    def test_emits_entered_and_exited(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        inverter.tick(State(), emitter, ctx)

        event_types = [e.event_type for e in emitter.events]
        assert "node_entered" in event_types
        assert "node_exited" in event_types

    def test_event_node_type_is_inverter(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        inverter.tick(State(), emitter, ctx)

        entered = [e for e in emitter.events if e.event_type == "node_entered"]
        # First entered event should be the Inverter
        inverter_entered = [e for e in entered if e.node_type == "Inverter"]
        assert len(inverter_entered) == 1
        assert inverter_entered[0].node_id == "inv"

    def test_exited_event_has_inverted_result(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        inverter.tick(State(), emitter, ctx)

        exited = [
            e
            for e in emitter.events
            if e.event_type == "node_exited" and e.node_type == "Inverter"
        ]
        assert len(exited) == 1
        assert exited[0].result == NodeStatus.FAILURE

    def test_path_includes_inverter(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1, path="root")

        inverter.tick(State(), emitter, ctx)

        entered = [
            e
            for e in emitter.events
            if e.event_type == "node_entered" and e.node_type == "Inverter"
        ]
        assert entered[0].path_in_tree == "root/inv"

    def test_child_events_also_emitted(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        inverter.tick(State(), emitter, ctx)

        # Should have: Inverter entered, Action invoked, Action completed,
        # Inverter exited
        assert len(emitter.events) == 4

    def test_works_without_emitter(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)

        result = inverter.tick(State())
        assert result == NodeStatus.FAILURE

    def test_no_events_without_ctx(self):
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        emitter = ListEventEmitter()

        inverter.tick(State(), emitter)
        assert len(emitter.events) == 0


# =============================================================================
# Repeater
# =============================================================================


class TestRepeater:
    """Tests for the Repeater decorator node."""

    def test_finite_repeats_returns_running(self):
        """Each tick that succeeds returns RUNNING until count is met."""
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=3)

        result = repeater.tick(State())
        assert result == NodeStatus.RUNNING
        assert repeater.current_count == 1

    def test_finite_repeats_succeeds_after_n_ticks(self):
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=3)

        results = [repeater.tick(State()) for _ in range(3)]
        assert results == [
            NodeStatus.RUNNING,
            NodeStatus.RUNNING,
            NodeStatus.SUCCESS,
        ]

    def test_finite_repeats_resets_count_on_completion(self):
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=2)

        repeater.tick(State())
        repeater.tick(State())
        assert repeater.current_count == 0

    def test_finite_repeats_can_run_again_after_completion(self):
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=2)

        # First cycle
        repeater.tick(State())
        result = repeater.tick(State())
        assert result == NodeStatus.SUCCESS

        # Second cycle
        result = repeater.tick(State())
        assert result == NodeStatus.RUNNING

    def test_single_repeat(self):
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=1)

        result = repeater.tick(State())
        assert result == NodeStatus.SUCCESS

    def test_infinite_repeater_always_returns_running(self):
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=None)

        for _ in range(100):
            result = repeater.tick(State())
            assert result == NodeStatus.RUNNING

    def test_failure_stops_repeating(self):
        child = FailureAction("action")
        repeater = Repeater("rep", child, max_repeats=5)

        result = repeater.tick(State())
        assert result == NodeStatus.FAILURE

    def test_failure_resets_count(self):
        child = MockNode("child", NodeStatus.SUCCESS)
        repeater = Repeater("rep", child, max_repeats=5)

        repeater.tick(State())
        assert repeater.current_count == 1

        child._status = NodeStatus.FAILURE
        repeater.tick(State())
        assert repeater.current_count == 0

    def test_running_child_passes_through(self):
        child = RunningAction("action")
        repeater = Repeater("rep", child, max_repeats=3)

        result = repeater.tick(State())
        assert result == NodeStatus.RUNNING
        # Count should not increment for RUNNING
        assert repeater.current_count == 0

    def test_child_is_reset_after_each_success(self):
        child = CountingAction("counter")
        repeater = Repeater("rep", child, max_repeats=3)

        repeater.tick(State())
        # Child was executed once then reset
        assert child.execute_count == 0

    def test_child_ticked_correct_number_of_times(self):
        """The child should be ticked once per Repeater tick."""
        child = MockNode("child", NodeStatus.SUCCESS)
        repeater = Repeater("rep", child, max_repeats=3)

        repeater.tick(State())
        repeater.tick(State())
        repeater.tick(State())
        # On the final tick, child succeeds -> count reaches max_repeats
        # -> count resets to 0. Child was also reset after each success,
        # so tick_count is 0 after the last reset.
        assert child.tick_count == 0

    def test_reset(self):
        child = CountingAction("counter")
        repeater = Repeater("rep", child, max_repeats=5)

        repeater.tick(State())
        repeater.tick(State())
        repeater.reset()
        assert repeater.current_count == 0
        assert child.execute_count == 0


class TestRepeaterEvents:
    """Tests for event emission from Repeater."""

    def test_emits_entered_and_exited(self):
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=1)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        repeater.tick(State(), emitter, ctx)

        event_types = [e.event_type for e in emitter.events]
        assert "node_entered" in event_types
        assert "node_exited" in event_types

    def test_exit_status_matches_result(self):
        child = SuccessAction("action")
        repeater = Repeater("rep", child, max_repeats=2)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        # First tick: RUNNING
        repeater.tick(State(), emitter, ctx)
        exited = [
            e
            for e in emitter.events
            if e.event_type == "node_exited" and e.node_type == "Repeater"
        ]
        assert exited[-1].result == NodeStatus.RUNNING

        emitter.clear()

        # Second tick: SUCCESS
        repeater.tick(State(), emitter, ctx)
        exited = [
            e
            for e in emitter.events
            if e.event_type == "node_exited" and e.node_type == "Repeater"
        ]
        assert exited[-1].result == NodeStatus.SUCCESS


# =============================================================================
# RetryUntilSuccess
# =============================================================================


class TestRetryUntilSuccess:
    """Tests for the RetryUntilSuccess decorator node."""

    def test_success_on_first_try(self):
        child = SuccessAction("action")
        retry = RetryUntilSuccess("retry", child)

        result = retry.tick(State())
        assert result == NodeStatus.SUCCESS

    def test_returns_running_on_failure(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child)

        result = retry.tick(State())
        assert result == NodeStatus.RUNNING

    def test_unlimited_retries(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=None)

        for _ in range(100):
            result = retry.tick(State())
            assert result == NodeStatus.RUNNING

    def test_max_attempts_returns_failure(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=3)

        results = [retry.tick(State()) for _ in range(3)]
        assert results == [
            NodeStatus.RUNNING,
            NodeStatus.RUNNING,
            NodeStatus.FAILURE,
        ]

    def test_max_attempts_resets_count_on_exhaustion(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=2)

        retry.tick(State())
        retry.tick(State())
        assert retry.current_attempts == 0

    def test_success_resets_attempts(self):
        child = MockNode("child", NodeStatus.FAILURE)
        retry = RetryUntilSuccess("retry", child, max_attempts=5)

        retry.tick(State())
        assert retry.current_attempts == 1

        child._status = NodeStatus.SUCCESS
        retry.tick(State())
        assert retry.current_attempts == 0

    def test_running_child_passes_through(self):
        child = RunningAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=3)

        result = retry.tick(State())
        assert result == NodeStatus.RUNNING
        # Attempts should not increment on RUNNING
        assert retry.current_attempts == 0

    def test_child_reset_after_failure(self):
        failing_child = MockNode("child", NodeStatus.FAILURE)
        retry = RetryUntilSuccess("retry", failing_child, max_attempts=3)

        retry.tick(State())
        assert failing_child._reset_called

    def test_eventual_success(self):
        """Child fails twice then succeeds."""
        child = MockNode("child", NodeStatus.FAILURE)
        retry = RetryUntilSuccess("retry", child, max_attempts=5)

        result = retry.tick(State())
        assert result == NodeStatus.RUNNING

        result = retry.tick(State())
        assert result == NodeStatus.RUNNING

        child._status = NodeStatus.SUCCESS
        result = retry.tick(State())
        assert result == NodeStatus.SUCCESS

    def test_single_max_attempt(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=1)

        result = retry.tick(State())
        assert result == NodeStatus.FAILURE

    def test_can_run_again_after_max_attempts(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=2)

        # Exhaust attempts
        retry.tick(State())
        result = retry.tick(State())
        assert result == NodeStatus.FAILURE

        # Should be able to start over
        result = retry.tick(State())
        assert result == NodeStatus.RUNNING

    def test_reset(self):
        child = MockNode("child", NodeStatus.FAILURE)
        retry = RetryUntilSuccess("retry", child, max_attempts=5)

        retry.tick(State())
        retry.tick(State())
        retry.reset()
        assert retry.current_attempts == 0
        assert child._reset_called


class TestRetryUntilSuccessEvents:
    """Tests for event emission from RetryUntilSuccess."""

    def test_emits_entered_and_exited(self):
        child = SuccessAction("action")
        retry = RetryUntilSuccess("retry", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        retry.tick(State(), emitter, ctx)

        event_types = [e.event_type for e in emitter.events]
        assert "node_entered" in event_types
        assert "node_exited" in event_types

    def test_exit_status_success(self):
        child = SuccessAction("action")
        retry = RetryUntilSuccess("retry", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        retry.tick(State(), emitter, ctx)

        exited = [
            e
            for e in emitter.events
            if e.event_type == "node_exited" and e.node_type == "RetryUntilSuccess"
        ]
        assert exited[0].result == NodeStatus.SUCCESS

    def test_exit_status_running_on_retry(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=3)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        retry.tick(State(), emitter, ctx)

        exited = [
            e
            for e in emitter.events
            if e.event_type == "node_exited" and e.node_type == "RetryUntilSuccess"
        ]
        assert exited[0].result == NodeStatus.RUNNING

    def test_exit_status_failure_on_exhaustion(self):
        child = FailureAction("action")
        retry = RetryUntilSuccess("retry", child, max_attempts=1)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1)

        retry.tick(State(), emitter, ctx)

        exited = [
            e
            for e in emitter.events
            if e.event_type == "node_exited" and e.node_type == "RetryUntilSuccess"
        ]
        assert exited[0].result == NodeStatus.FAILURE


# =============================================================================
# Integration: Decorators with composites
# =============================================================================


class TestDecoratorIntegration:
    """Tests combining decorators with other node types."""

    def test_inverter_in_selector(self):
        """Inverter can flip a success into failure inside a Selector."""
        from vivarium.core import Selector

        inverted = Inverter("inv", SuccessAction("action"))
        fallback = SuccessAction("fallback")
        selector = Selector("sel", [inverted, fallback])

        state = State()
        result = selector.tick(state)
        # Inverter turns SUCCESS -> FAILURE, so Selector moves to fallback
        assert result == NodeStatus.SUCCESS

    def test_inverter_in_sequence(self):
        """Inverter can turn failure into success for a Sequence."""
        from vivarium.core import Sequence

        inverted = Inverter("inv", FailureAction("action"))
        next_action = CountingAction("counter")
        seq = Sequence("seq", [inverted, next_action])

        state = State()
        result = seq.tick(state)
        assert result == NodeStatus.SUCCESS
        assert next_action.execute_count == 1

    def test_nested_decorators(self):
        """Decorators can be nested: Inverter(Inverter(child))."""
        child = SuccessAction("action")
        double_inverted = Inverter("inv2", Inverter("inv1", child))

        result = double_inverted.tick(State())
        # Double inversion = original result
        assert result == NodeStatus.SUCCESS

    def test_repeater_with_state_modification(self):
        """Repeater executes child multiple times, modifying state."""
        from vivarium.core import State

        child = CountingAction("counter")
        repeater = Repeater("rep", child, max_repeats=3)
        state = State()

        # Tick 3 times, child executes once per tick (then reset)
        repeater.tick(state)
        repeater.tick(state)
        result = repeater.tick(state)

        assert result == NodeStatus.SUCCESS

    def test_retry_with_eventual_success(self):
        """RetryUntilSuccess retries until child succeeds."""
        child = MockNode("child", NodeStatus.FAILURE)
        retry = RetryUntilSuccess("retry", child, max_attempts=10)

        # Fail a few times
        retry.tick(State())
        retry.tick(State())

        # Now succeed
        child._status = NodeStatus.SUCCESS
        result = retry.tick(State())
        assert result == NodeStatus.SUCCESS

    def test_event_emission_through_decorator_chain(self):
        """Events propagate correctly through nested decorators."""
        child = SuccessAction("action")
        inverter = Inverter("inv", child)
        emitter = ListEventEmitter()
        ctx = ExecutionContext(tick_id=1, path="root")

        inverter.tick(State(), emitter, ctx)

        # Verify path nesting
        action_events = [e for e in emitter.events if e.event_type == "action_invoked"]
        assert len(action_events) == 1
        assert action_events[0].path_in_tree == "root/inv/action"
