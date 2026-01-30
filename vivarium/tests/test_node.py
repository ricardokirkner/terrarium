import pytest

from core import Node, NodeStatus


class ConcreteSuccessNode(Node):
    """A concrete node implementation that always returns SUCCESS."""

    def __init__(self, name: str):
        self.name = name
        self._reset_called = False

    def tick(self, state) -> NodeStatus:
        return NodeStatus.SUCCESS

    def reset(self):
        self._reset_called = True


class TestNodeAbstract:
    def test_cannot_instantiate_abstract_node(self):
        with pytest.raises(TypeError):
            Node("test")


class TestConcreteNode:
    def test_tick_returns_success(self):
        node = ConcreteSuccessNode("test_node")
        result = node.tick({})
        assert result == NodeStatus.SUCCESS

    def test_reset_works(self):
        node = ConcreteSuccessNode("test_node")
        assert node._reset_called is False
        node.reset()
        assert node._reset_called is True
