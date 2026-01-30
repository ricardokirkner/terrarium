from core import Node, NodeStatus, Sequence


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
