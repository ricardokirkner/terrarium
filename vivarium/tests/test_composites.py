import pytest

from core import Node, NodeStatus, Parallel, Selector, Sequence


class MockNode(Node):
    """A mock node that returns a configurable status."""

    def __init__(self, name: str, status: NodeStatus = NodeStatus.SUCCESS):
        self.name = name
        self._status = status
        self.tick_count = 0
        self._reset_called = False

    def tick(self, state) -> NodeStatus:
        self.tick_count += 1
        return self._status

    def reset(self):
        self._reset_called = True
        self.tick_count = 0


class OrderTrackingNode(Node):
    """A node that records its execution order to a shared list."""

    def __init__(self, name: str, execution_order: list[str]):
        self.name = name
        self._execution_order = execution_order

    def tick(self, state) -> NodeStatus:
        self._execution_order.append(self.name)
        return NodeStatus.SUCCESS

    def reset(self):
        pass


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
        # tick_count is reset to 0 by reset(), then incremented to 1
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


class TestParallel:
    # Basic behavior tests
    def test_empty_parallel_returns_success(self):
        par = Parallel("empty")
        result = par.tick({})
        assert result == NodeStatus.SUCCESS

    def test_all_children_ticked_on_each_tick(self):
        children = [
            MockNode("child1", NodeStatus.SUCCESS),
            MockNode("child2", NodeStatus.SUCCESS),
            MockNode("child3", NodeStatus.SUCCESS),
        ]
        par = Parallel("par", children)
        par.tick({})
        assert all(child.tick_count == 1 for child in children)

        # Tick again - all children should be ticked again
        par.tick({})
        assert all(child.tick_count == 2 for child in children)

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
