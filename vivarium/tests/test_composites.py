import pytest

from vivarium.core import (
    BehaviorTree,
    ListEventEmitter,
    Node,
    NodeStatus,
    Parallel,
    Selector,
    Sequence,
    State,
)

from .helpers import (
    MockNode,
    OrderTrackingNode,
    SuccessAction,
    TrueCondition,
)


class TestSequence:
    def test_empty_sequence_returns_success(self):
        seq = Sequence("empty")
        result = seq.tick({})
        assert result == NodeStatus.SUCCESS

    def test_all_children_succeed_returns_success(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.SUCCESS),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        seq = Sequence("seq", children)
        result = seq.tick({})
        assert result == NodeStatus.SUCCESS
        assert all(child.tick_count == 1 for child in children)

    def test_first_child_failure_returns_failure(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.SUCCESS),
        ]
        seq = Sequence("seq", children)
        result = seq.tick({})
        assert result == NodeStatus.FAILURE
        assert children[0].tick_count == 1
        assert children[1].tick_count == 0

    def test_middle_child_failure_returns_failure(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        seq = Sequence("seq", children)
        result = seq.tick({})
        assert result == NodeStatus.FAILURE
        assert children[0].tick_count == 1
        assert children[1].tick_count == 1
        assert children[2].tick_count == 0

    def test_running_child_returns_running(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.RUNNING),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        seq = Sequence("seq", children)
        result = seq.tick({})
        assert result == NodeStatus.RUNNING
        assert children[0].tick_count == 1
        assert children[1].tick_count == 1
        assert children[2].tick_count == 0

    def test_running_child_resumes_on_next_tick(self):
        running_node = MockNode("running", NodeStatus.RUNNING)
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            running_node,
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        seq = Sequence("seq", children)

        # First tick - stops at running node
        result = seq.tick({})
        assert result == NodeStatus.RUNNING
        assert children[0].tick_count == 1
        assert running_node.tick_count == 1

        # Change running node to succeed
        running_node._status = NodeStatus.SUCCESS

        # Second tick - resumes from running node
        result = seq.tick({})
        assert result == NodeStatus.SUCCESS
        assert children[0].tick_count == 1  # Not ticked again
        assert running_node.tick_count == 2
        assert children[2].tick_count == 1

    def test_reset_resets_index_and_children(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.RUNNING),
        ]
        seq = Sequence("seq", children)

        # Tick to advance index
        seq.tick({})
        assert seq.current_index == 1

        # Reset
        seq.reset()
        assert seq.current_index == 0
        assert all(child._reset_called for child in children)

    def test_stores_children(self):
        children = [MockNode("child1"), MockNode("child2")]
        seq = Sequence("seq", children)
        assert seq.children == children

    def test_tracks_current_index(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.RUNNING),
        ]
        seq = Sequence("seq", children)
        assert seq.current_index == 0

        seq.tick({})
        assert seq.current_index == 1

    def test_children_execute_in_order(self):
        execution_order: list[str] = []
        children = [
            OrderTrackingNode("first", execution_order),
            OrderTrackingNode("second", execution_order),
            OrderTrackingNode("third", execution_order),
        ]
        seq = Sequence("seq", children)
        seq.tick({})
        assert execution_order == ["first", "second", "third"]

    def test_reset_allows_re_execution(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.SUCCESS),
        ]
        seq = Sequence("seq", children)

        # First execution
        result = seq.tick({})
        assert result == NodeStatus.SUCCESS
        assert all(child.tick_count == 1 for child in children)

        # Reset and re-execute
        seq.reset()
        result = seq.tick({})
        assert result == NodeStatus.SUCCESS
        # MockNode.tick_count is reset to 0 by MockNode.reset(), then incremented to 1
        assert all(child.tick_count == 1 for child in children)

    def test_failure_does_not_execute_remaining_children(self):
        execution_order: list[str] = []
        children: list[Node] = [
            OrderTrackingNode("first", execution_order),
            MockNode("failing", NodeStatus.FAILURE),
            OrderTrackingNode("third", execution_order),
        ]
        seq = Sequence("seq", children)
        result = seq.tick({})
        assert result == NodeStatus.FAILURE
        assert execution_order == ["first"]  # "third" never executed

    def test_idle_child_raises_value_error(self):
        """A child returning IDLE during tick should raise ValueError."""
        idle_node = MockNode("idle_child", NodeStatus.IDLE)
        seq = Sequence("seq", [idle_node])
        with pytest.raises(ValueError) as exc_info:
            seq.tick({})
        assert "idle_child" in str(exc_info.value)
        assert "IDLE" in str(exc_info.value)

    def test_idle_child_without_name_uses_class_name(self):
        """A child without name attribute returning IDLE uses class name in error."""

        class NamelessNode(Node):
            def __init__(self):
                # Intentionally don't set self.name
                pass

            def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
                return NodeStatus.IDLE

            def reset(self):
                pass

        nameless: Node = NamelessNode()
        seq = Sequence("seq", [nameless])
        with pytest.raises(ValueError) as exc_info:
            seq.tick({})
        assert "NamelessNode" in str(exc_info.value)


class TestSelector:
    def test_empty_selector_returns_failure(self):
        sel = Selector("empty")
        result = sel.tick({})
        assert result == NodeStatus.FAILURE

    def test_first_child_success_returns_success(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
        ]
        sel = Selector("sel", children)
        result = sel.tick({})
        assert result == NodeStatus.SUCCESS
        assert children[0].tick_count == 1
        assert children[1].tick_count == 0  # Early exit

    def test_success_in_middle_returns_success(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.SUCCESS),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        sel = Selector("sel", children)
        result = sel.tick({})
        assert result == NodeStatus.SUCCESS
        assert children[0].tick_count == 1
        assert children[1].tick_count == 1
        assert children[2].tick_count == 0  # Early exit

    def test_all_children_fail_returns_failure(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        sel = Selector("sel", children)
        result = sel.tick({})
        assert result == NodeStatus.FAILURE
        assert all(child.tick_count == 1 for child in children)

    def test_running_child_returns_running(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.RUNNING),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        sel = Selector("sel", children)
        result = sel.tick({})
        assert result == NodeStatus.RUNNING
        assert children[0].tick_count == 1
        assert children[1].tick_count == 1
        assert children[2].tick_count == 0

    def test_running_child_resumes_on_next_tick(self):
        running_node = MockNode("running", NodeStatus.RUNNING)
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            running_node,
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        sel = Selector("sel", children)

        # First tick - stops at running node
        result = sel.tick({})
        assert result == NodeStatus.RUNNING
        assert children[0].tick_count == 1
        assert running_node.tick_count == 1

        # Change running node to succeed
        running_node._status = NodeStatus.SUCCESS

        # Second tick - resumes from running node
        result = sel.tick({})
        assert result == NodeStatus.SUCCESS
        assert children[0].tick_count == 1  # Not ticked again
        assert running_node.tick_count == 2
        assert children[2].tick_count == 0  # Early exit after success

    def test_reset_resets_index_and_children(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.RUNNING),
        ]
        sel = Selector("sel", children)

        # Tick to advance index
        sel.tick({})
        assert sel.current_index == 1

        # Reset
        sel.reset()
        assert sel.current_index == 0
        assert all(child._reset_called for child in children)

    def test_idle_child_raises_value_error(self):
        """A child returning IDLE during tick should raise ValueError."""
        idle_node = MockNode("idle_child", NodeStatus.IDLE)
        sel = Selector("sel", [idle_node])
        with pytest.raises(ValueError) as exc_info:
            sel.tick({})
        assert "idle_child" in str(exc_info.value)
        assert "IDLE" in str(exc_info.value)

    def test_idle_child_without_name_uses_class_name(self):
        """A child without name attribute returning IDLE uses class name in error."""

        class NamelessNode(Node):
            def __init__(self):
                # Intentionally don't set self.name
                pass

            def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
                return NodeStatus.IDLE

            def reset(self):
                pass

        nameless: Node = NamelessNode()
        sel = Selector("sel", [nameless])
        with pytest.raises(ValueError) as exc_info:
            sel.tick({})
        assert "NamelessNode" in str(exc_info.value)


class TestParallel:
    # Basic behavior tests
    def test_empty_parallel_returns_success(self):
        par = Parallel("empty")
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    def test_completed_children_not_reticked(self):
        """Children that complete (SUCCESS/FAILURE) should not be ticked again.

        This prevents side effects from being executed multiple times when
        some children take longer than others.
        """
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.SUCCESS),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children)
        par.tick({})
        assert all(child.tick_count == 1 for child in children)

        # Tick again - completed children should NOT be ticked again
        par.tick({})
        assert all(child.tick_count == 1 for child in children)

    def test_running_children_continue_to_be_ticked(self):
        """Children that return RUNNING should continue to be ticked."""

        class CountingRunningNode(Node):
            def __init__(self, name: str, ticks_until_done: int):
                self.name = name
                self.ticks_until_done = ticks_until_done
                self.tick_count = 0

            def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
                self.tick_count += 1
                if self.tick_count >= self.ticks_until_done:
                    return NodeStatus.SUCCESS
                return NodeStatus.RUNNING

            def reset(self):
                self.tick_count = 0

        fast = CountingRunningNode("fast", 1)  # Completes immediately
        slow = CountingRunningNode("slow", 3)  # Takes 3 ticks

        par = Parallel("par", [fast, slow])

        # Tick 1: fast completes, slow is running
        result = par.tick({})
        assert result == NodeStatus.RUNNING
        assert fast.tick_count == 1
        assert slow.tick_count == 1

        # Tick 2: fast should NOT be ticked again, slow continues
        result = par.tick({})
        assert result == NodeStatus.RUNNING
        assert fast.tick_count == 1  # Not ticked again
        assert slow.tick_count == 2

        # Tick 3: slow completes
        result = par.tick({})
        assert result == NodeStatus.SUCCESS
        assert fast.tick_count == 1  # Still not ticked again
        assert slow.tick_count == 3

    # Default threshold tests (all must succeed/fail)
    def test_all_succeed_returns_success_default(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.SUCCESS),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children)
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    def test_one_failure_prevents_success_default(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children)
        result = par.tick({})
        assert result == NodeStatus.FAILURE

    def test_all_fail_returns_failure_default(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children)
        result = par.tick({})
        assert result == NodeStatus.FAILURE

    # Success threshold tests
    def test_success_threshold_1_with_one_success(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.SUCCESS),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children, success_threshold=1)
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    def test_success_threshold_2_with_two_successes(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children, success_threshold=2)
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    def test_success_threshold_not_met_returns_failure(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children, success_threshold=2)
        result = par.tick({})
        assert result == NodeStatus.FAILURE

    # Failure threshold tests
    def test_failure_threshold_1_with_one_failure(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children, failure_threshold=1)
        result = par.tick({})
        assert result == NodeStatus.FAILURE

    def test_failure_threshold_2_with_two_failures(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.SUCCESS),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children, failure_threshold=2)
        result = par.tick({})
        assert result == NodeStatus.FAILURE

    def test_failure_threshold_not_met_with_success_threshold_met(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children, success_threshold=2, failure_threshold=2)
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    # RUNNING tests
    def test_running_child_returns_running(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.RUNNING),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children)
        result = par.tick({})
        assert result == NodeStatus.RUNNING

    def test_running_with_success_threshold_met_returns_success(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.RUNNING),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children, success_threshold=2)
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    def test_running_with_failure_threshold_met_returns_failure(self):
        children = [
            MockNode("child1", NodeStatus.FAILURE),
            MockNode("child2", NodeStatus.RUNNING),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children, failure_threshold=2)
        result = par.tick({})
        assert result == NodeStatus.FAILURE

    def test_running_when_thresholds_not_met(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.RUNNING),
            MockNode("child3", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children, success_threshold=2, failure_threshold=2)
        result = par.tick({})
        assert result == NodeStatus.RUNNING

    # Mixed success/failure/running tests
    def test_mixed_states_all_children_ticked(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
            MockNode("child3", NodeStatus.RUNNING),
        ]
        par = Parallel("par", children, success_threshold=2, failure_threshold=2)
        par.tick({})
        assert all(child.tick_count == 1 for child in children)

    def test_success_threshold_checked_before_failure(self):
        # When both thresholds could be met, success is checked first
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children, success_threshold=1, failure_threshold=1)
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    # Reset tests
    def test_reset_resets_all_children(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.FAILURE),
        ]
        par = Parallel("par", children)
        par.tick({})
        par.reset()
        assert all(child._reset_called for child in children)

    def test_reset_allows_re_execution(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children)

        par.tick({})
        assert all(child.tick_count == 1 for child in children)

        par.reset()
        par.tick({})
        assert all(child.tick_count == 1 for child in children)

    def test_dynamically_added_children_are_handled(self):
        """Children added after construction are properly tracked."""
        child1 = MockNode("child1", NodeStatus.RUNNING)
        par = Parallel("par", [child1])

        # First tick - only child1 exists
        result = par.tick({})
        assert result == NodeStatus.RUNNING
        assert child1.tick_count == 1

        # Dynamically add a new child
        child2 = MockNode("child2", NodeStatus.SUCCESS)
        par.children.append(child2)

        # Second tick - both children should be processed
        result = par.tick({})
        assert result == NodeStatus.RUNNING  # child1 still running
        assert child1.tick_count == 2
        assert child2.tick_count == 1

        # child1 now succeeds
        child1._status = NodeStatus.SUCCESS

        # Third tick - both succeed
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    def test_idle_child_raises_value_error(self):
        """A child returning IDLE during tick should raise ValueError."""
        idle_node = MockNode("idle_child", NodeStatus.IDLE)
        par = Parallel("par", [idle_node])
        with pytest.raises(ValueError) as exc_info:
            par.tick({})
        assert "idle_child" in str(exc_info.value)
        assert "IDLE" in str(exc_info.value)

    def test_idle_child_without_name_uses_class_name(self):
        """A child without name attribute returning IDLE uses class name in error."""

        class NamelessNode(Node):
            def __init__(self):
                # Intentionally don't set self.name
                pass

            def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
                return NodeStatus.IDLE

            def reset(self):
                pass

        nameless: Node = NamelessNode()
        par = Parallel("par", [nameless])
        with pytest.raises(ValueError) as exc_info:
            par.tick({})
        assert "NamelessNode" in str(exc_info.value)


@pytest.mark.integration
class TestNestedComposites:
    """Tests for nested composite node structures."""

    def test_sequence_with_nested_selector_all_succeed(self):
        """Sequence([Action1, Action2, Selector([Action3, Action4])]) - all succeed."""
        execution_order: list[str] = []

        action1 = OrderTrackingNode("action1", execution_order)
        action2 = OrderTrackingNode("action2", execution_order)
        action3 = OrderTrackingNode("action3", execution_order)
        action4 = OrderTrackingNode("action4", execution_order)

        tree: Node = Sequence(
            "root",
            [
                action1,
                action2,
                Selector("selector", [action3, action4]),
            ],
        )

        result = tree.tick({})

        assert result == NodeStatus.SUCCESS
        # Sequence executes action1, action2, then selector
        # Selector tries action3 which succeeds, so action4 is never tried
        assert execution_order == ["action1", "action2", "action3"]

    def test_sequence_with_nested_selector_first_action_fails(self):
        """Sequence fails early if first action fails."""
        action1 = MockNode("action1", NodeStatus.FAILURE)
        action2 = MockNode("action2", NodeStatus.SUCCESS)
        action3 = MockNode("action3", NodeStatus.SUCCESS)
        action4 = MockNode("action4", NodeStatus.SUCCESS)

        tree: Node = Sequence(
            "root",
            [
                action1,
                action2,
                Selector("selector", [action3, action4]),
            ],
        )

        result = tree.tick({})

        assert result == NodeStatus.FAILURE
        assert action1.tick_count == 1
        assert action2.tick_count == 0  # Never reached
        assert action3.tick_count == 0  # Never reached
        assert action4.tick_count == 0  # Never reached

    def test_sequence_with_nested_selector_selector_tries_fallback(self):
        """Selector tries fallback when first option fails."""
        execution_order: list[str] = []

        action1 = OrderTrackingNode("action1", execution_order)
        action2 = OrderTrackingNode("action2", execution_order)
        action3 = MockNode("action3", NodeStatus.FAILURE)
        action4 = OrderTrackingNode("action4", execution_order)

        tree: Node = Sequence(
            "root",
            [
                action1,
                action2,
                Selector("selector", [action3, action4]),
            ],
        )

        result = tree.tick({})

        assert result == NodeStatus.SUCCESS
        # action3 fails, so selector tries action4 which succeeds
        assert execution_order == ["action1", "action2", "action4"]
        assert action3.tick_count == 1

    def test_sequence_with_nested_selector_all_selector_children_fail(self):
        """Sequence fails when all selector children fail."""
        action1 = MockNode("action1", NodeStatus.SUCCESS)
        action2 = MockNode("action2", NodeStatus.SUCCESS)
        action3 = MockNode("action3", NodeStatus.FAILURE)
        action4 = MockNode("action4", NodeStatus.FAILURE)

        tree: Node = Sequence(
            "root",
            [
                action1,
                action2,
                Selector("selector", [action3, action4]),
            ],
        )

        result = tree.tick({})

        assert result == NodeStatus.FAILURE
        assert action1.tick_count == 1
        assert action2.tick_count == 1
        assert action3.tick_count == 1
        assert action4.tick_count == 1

    def test_sequence_with_nested_selector_running_in_selector(self):
        """Sequence returns RUNNING when selector child is RUNNING."""
        action1 = MockNode("action1", NodeStatus.SUCCESS)
        action2 = MockNode("action2", NodeStatus.SUCCESS)
        action3 = MockNode("action3", NodeStatus.RUNNING)
        action4 = MockNode("action4", NodeStatus.SUCCESS)

        tree: Node = Sequence(
            "root",
            [
                action1,
                action2,
                Selector("selector", [action3, action4]),
            ],
        )

        result = tree.tick({})

        assert result == NodeStatus.RUNNING
        assert action3.tick_count == 1
        assert action4.tick_count == 0  # Not tried yet

    def test_sequence_with_nested_selector_resumes_after_running(self):
        """Sequence resumes from RUNNING selector child."""
        action1 = MockNode("action1", NodeStatus.SUCCESS)
        action2 = MockNode("action2", NodeStatus.SUCCESS)
        action3 = MockNode("action3", NodeStatus.RUNNING)
        action4 = MockNode("action4", NodeStatus.SUCCESS)

        selector = Selector("selector", [action3, action4])
        tree: Node = Sequence("root", [action1, action2, selector])

        # First tick - stops at running action3
        result = tree.tick({})
        assert result == NodeStatus.RUNNING
        assert action1.tick_count == 1
        assert action2.tick_count == 1
        assert action3.tick_count == 1

        # action3 now succeeds
        action3._status = NodeStatus.SUCCESS

        # Second tick - resumes from selector (which resumes from action3)
        result = tree.tick({})
        assert result == NodeStatus.SUCCESS
        assert action1.tick_count == 1  # Not re-ticked (sequence resumed at selector)
        assert action2.tick_count == 1  # Not re-ticked
        assert action3.tick_count == 2  # Re-ticked and succeeds
        assert action4.tick_count == 0  # Not needed since action3 succeeded

    def test_reset_propagates_through_nested_structure(self):
        """Reset propagates through all nested nodes."""
        action1 = MockNode("action1", NodeStatus.SUCCESS)
        action2 = MockNode("action2", NodeStatus.SUCCESS)
        action3 = MockNode("action3", NodeStatus.SUCCESS)
        action4 = MockNode("action4", NodeStatus.SUCCESS)

        selector = Selector("selector", [action3, action4])
        tree = Sequence("root", [action1, action2, selector])

        tree.tick({})
        tree.reset()

        assert action1._reset_called
        assert action2._reset_called
        assert action3._reset_called
        assert action4._reset_called


class TestCompositeEventPaths:
    """Tests verifying that composites emit events with correct child paths."""

    def test_sequence_children_have_indexed_paths(self):
        """Children of a Sequence should have paths with positional indices."""
        a = SuccessAction("a")
        b = SuccessAction("b")
        seq = Sequence("seq", [a, b])
        emitter = ListEventEmitter()
        tree = BehaviorTree(seq, emitter)

        tree.tick(State())

        action_events = [e for e in emitter.events if e.event_type == "action_invoked"]
        assert len(action_events) == 2
        assert action_events[0].path_in_tree == "seq/a@0"
        assert action_events[1].path_in_tree == "seq/b@1"

    def test_selector_children_have_indexed_paths(self):
        """Children of a Selector should have paths with positional indices."""
        a_fail = MockNode("a", NodeStatus.FAILURE)
        b = SuccessAction("b")
        sel = Selector("sel", [a_fail, b])
        emitter = ListEventEmitter()
        tree = BehaviorTree(sel, emitter)

        tree.tick(State())

        # a_fail doesn't emit events (MockNode), b does
        action_events = [e for e in emitter.events if e.event_type == "action_invoked"]
        assert len(action_events) == 1
        assert action_events[0].path_in_tree == "sel/b@1"

    def test_parallel_children_have_indexed_paths(self):
        """Children of a Parallel should have paths with positional indices."""
        a = SuccessAction("a")
        b = SuccessAction("b")
        par = Parallel("par", [a, b])
        emitter = ListEventEmitter()
        tree = BehaviorTree(par, emitter)

        tree.tick(State())

        action_events = [e for e in emitter.events if e.event_type == "action_invoked"]
        assert len(action_events) == 2
        assert action_events[0].path_in_tree == "par/a@0"
        assert action_events[1].path_in_tree == "par/b@1"

    def test_nested_composites_have_correct_paths(self):
        """Nested composites produce correct hierarchical paths."""
        action = SuccessAction("attack")
        inner_seq = Sequence("inner", [action])
        outer_sel = Selector("outer", [inner_seq])
        emitter = ListEventEmitter()
        tree = BehaviorTree(outer_sel, emitter)

        tree.tick(State())

        # Check the full path chain
        entered_events = [e for e in emitter.events if e.event_type == "node_entered"]
        # outer selector, inner sequence
        assert entered_events[0].path_in_tree == "outer"
        assert entered_events[1].path_in_tree == "outer/inner@0"

        action_events = [e for e in emitter.events if e.event_type == "action_invoked"]
        assert action_events[0].path_in_tree == "outer/inner@0/attack@0"

    def test_condition_has_indexed_path(self):
        """Conditions inside composites get indexed paths."""
        cond = TrueCondition("check")
        seq = Sequence("seq", [cond])
        emitter = ListEventEmitter()
        tree = BehaviorTree(seq, emitter)

        tree.tick(State())

        cond_events = [
            e for e in emitter.events if e.event_type == "condition_evaluated"
        ]
        assert len(cond_events) == 1
        assert cond_events[0].path_in_tree == "seq/check@0"

    def test_same_name_children_have_distinct_paths(self):
        """Children with the same name are distinguished by index."""
        a1 = SuccessAction("action")
        a2 = SuccessAction("action")
        seq = Sequence("seq", [a1, a2])
        emitter = ListEventEmitter()
        tree = BehaviorTree(seq, emitter)

        tree.tick(State())

        action_events = [e for e in emitter.events if e.event_type == "action_invoked"]
        assert len(action_events) == 2
        assert action_events[0].path_in_tree == "seq/action@0"
        assert action_events[1].path_in_tree == "seq/action@1"
