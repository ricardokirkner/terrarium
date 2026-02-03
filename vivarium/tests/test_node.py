import pytest

from vivarium.core import Node, NodeStatus


class ConcreteSuccessNode(Node):
    """A concrete node implementation that always returns SUCCESS."""

    def __init__(self, name: str):
        self.name = name
        self._reset_called = False

    def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
        return NodeStatus.SUCCESS

    def reset(self):
        self._reset_called = True


class ConcreteFailureNode(Node):
    """A concrete node implementation that always returns FAILURE."""

    def __init__(self, name: str):
        self.name = name

    def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
        return NodeStatus.FAILURE

    def reset(self):
        pass


class ConcreteRunningNode(Node):
    """A concrete node implementation that always returns RUNNING."""

    def __init__(self, name: str):
        self.name = name

    def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
        return NodeStatus.RUNNING

    def reset(self):
        pass


class ConcreteIdleNode(Node):
    """A concrete node implementation that always returns IDLE."""

    def __init__(self, name: str):
        self.name = name

    def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
        return NodeStatus.IDLE

    def reset(self):
        pass


class StateCapturingNode(Node):
    """A node that captures the state passed to tick."""

    def __init__(self, name: str):
        self.name = name
        self.captured_state = None

    def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
        self.captured_state = state
        return NodeStatus.SUCCESS

    def reset(self):
        self.captured_state = None


class TestNodeStatus:
    def test_success_status_exists(self):
        assert NodeStatus.SUCCESS.value == "success"

    def test_failure_status_exists(self):
        assert NodeStatus.FAILURE.value == "failure"

    def test_running_status_exists(self):
        assert NodeStatus.RUNNING.value == "running"

    def test_idle_status_exists(self):
        assert NodeStatus.IDLE.value == "idle"

    def test_all_statuses_are_unique(self):
        statuses = [s.value for s in NodeStatus]
        assert len(statuses) == len(set(statuses))

    def test_status_count(self):
        assert len(NodeStatus) == 4


class TestNodeAbstract:
    def test_cannot_instantiate_abstract_node(self):
        with pytest.raises(TypeError):
            Node("test")

    def test_must_implement_init(self):
        with pytest.raises(TypeError):

            class MissingInit(Node):
                def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
                    return NodeStatus.SUCCESS

                def reset(self):
                    pass

            MissingInit("test")

    def test_must_implement_tick(self):
        with pytest.raises(TypeError):

            class MissingTick(Node):
                def __init__(self, name: str):
                    self.name = name

                def reset(self):
                    pass

            MissingTick("test")

    def test_must_implement_reset(self):
        with pytest.raises(TypeError):

            class MissingReset(Node):
                def __init__(self, name: str):
                    self.name = name

                def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
                    return NodeStatus.SUCCESS

            MissingReset("test")


class TestConcreteNode:
    def test_tick_returns_success(self):
        node = ConcreteSuccessNode("test_node")
        result = node.tick({})
        assert result == NodeStatus.SUCCESS

    def test_tick_returns_failure(self):
        node = ConcreteFailureNode("test_node")
        result = node.tick({})
        assert result == NodeStatus.FAILURE

    def test_tick_returns_running(self):
        node = ConcreteRunningNode("test_node")
        result = node.tick({})
        assert result == NodeStatus.RUNNING

    def test_tick_returns_idle(self):
        node = ConcreteIdleNode("test_node")
        result = node.tick({})
        assert result == NodeStatus.IDLE

    def test_reset_works(self):
        node = ConcreteSuccessNode("test_node")
        assert node._reset_called is False
        node.reset()
        assert node._reset_called is True

    def test_name_is_stored(self):
        node = ConcreteSuccessNode("my_node_name")
        assert node.name == "my_node_name"

    def test_state_is_passed_to_tick(self):
        node = StateCapturingNode("test_node")
        test_state = {"key": "value", "count": 42}
        node.tick(test_state)
        assert node.captured_state == test_state

    def test_state_can_be_modified_in_tick(self):
        class StateModifyingNode(Node):
            def __init__(self, name: str):
                self.name = name

            def tick(self, state, emitter=None, ctx=None) -> NodeStatus:
                state["modified"] = True
                return NodeStatus.SUCCESS

            def reset(self):
                pass

        node = StateModifyingNode("test_node")
        state = {"original": True}
        node.tick(state)
        assert state["modified"] is True
        assert state["original"] is True
