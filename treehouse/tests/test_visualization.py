"""Tests for treehouse visualization module."""

from datetime import datetime, timedelta, timezone

import pytest

from treehouse.telemetry import ExecutionTrace, NodeExecution
from treehouse.visualization import (
    _format_duration,
    _get_depth,
    _get_node_name,
    _status_icon,
    format_timeline,
    format_trace,
)

# --- Helper functions tests ---


def test_status_icon_success():
    """Status icon for success should be checkmark."""
    icon = _status_icon("success", use_color=False)
    assert icon == "✓"


def test_status_icon_failure():
    """Status icon for failure should be X."""
    icon = _status_icon("failure", use_color=False)
    assert icon == "✗"


def test_status_icon_running():
    """Status icon for running should be pause."""
    icon = _status_icon("running", use_color=False)
    assert icon == "⏸"


def test_status_icon_unknown():
    """Status icon for unknown status should be question mark."""
    icon = _status_icon("unknown", use_color=False)
    assert icon == "?"


def test_format_duration_submillisecond():
    """Durations under 1ms should show as <1ms."""
    assert _format_duration(0.5) == "<1ms"
    assert _format_duration(0) == "<1ms"


def test_format_duration_milliseconds():
    """Durations under 1s should show in milliseconds."""
    assert _format_duration(5) == "5ms"
    assert _format_duration(100) == "100ms"
    assert _format_duration(999) == "999ms"


def test_format_duration_seconds():
    """Durations over 1s should show in seconds."""
    assert _format_duration(1000) == "1.00s"
    assert _format_duration(1500) == "1.50s"
    assert _format_duration(10000) == "10.00s"


def test_get_depth_empty():
    """Empty path should have depth 0."""
    assert _get_depth("") == 0


def test_get_depth_root():
    """Root node should have depth 0."""
    assert _get_depth("root") == 0


def test_get_depth_nested():
    """Nested paths should count slashes."""
    assert _get_depth("root/child") == 1
    assert _get_depth("root/child/grandchild") == 2
    assert _get_depth("a/b/c/d/e") == 4


def test_get_node_name_simple():
    """Simple path should return the name."""
    assert _get_node_name("action") == "action"


def test_get_node_name_nested():
    """Nested path should return last segment."""
    assert _get_node_name("root/sequence/action") == "action"


def test_get_node_name_with_index():
    """Path with index should strip the index."""
    assert _get_node_name("root/action[0]") == "action"
    assert _get_node_name("sequence/child[2]") == "child"


# --- format_trace tests ---


def _make_trace(
    executions: list[tuple[str, str, str, float]] | None = None,
    status: str = "success",
    duration_ms: float = 100.0,
) -> ExecutionTrace:
    """Create a test trace.

    Args:
        executions: List of (path, node_type, status, duration_ms) tuples.
        status: Overall trace status.
        duration_ms: Total trace duration.
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(milliseconds=duration_ms)

    exec_list = []
    if executions:
        for path, node_type, exec_status, exec_duration in executions:
            name = path.split("/")[-1].split("[")[0] if path else ""
            exec_list.append(
                NodeExecution(
                    node_id=name,
                    node_name=name,
                    node_type=node_type,
                    path_in_tree=path,
                    timestamp=now,
                    status=exec_status,
                    duration_ms=exec_duration,
                )
            )

    return ExecutionTrace(
        trace_id="test-trace",
        tick_id=1,
        start_time=now,
        end_time=end,
        status=status,
        executions=exec_list,
    )


def test_format_trace_empty():
    """format_trace should handle empty executions."""
    trace = _make_trace()
    output = format_trace(trace, use_color=False)

    assert "Trace #1" in output
    assert "success" in output
    assert "(no executions)" in output


def test_format_trace_single_node():
    """format_trace should show a single node."""
    trace = _make_trace(
        executions=[("action", "Action", "success", 10.0)],
    )
    output = format_trace(trace, use_color=False)

    assert "Trace #1" in output
    assert "action" in output
    assert "[Action]" in output
    assert "✓" in output
    assert "10ms" in output


def test_format_trace_multiple_nodes():
    """format_trace should show multiple nodes."""
    trace = _make_trace(
        executions=[
            ("check", "Condition", "success", 0.0),
            ("heal", "Action", "success", 50.0),
        ],
    )
    output = format_trace(trace, use_color=False)

    assert "check" in output
    assert "heal" in output
    assert "[Condition]" in output
    assert "[Action]" in output


def test_format_trace_nested_nodes():
    """format_trace should show nested nodes with indentation."""
    trace = _make_trace(
        executions=[
            ("sequence", "Sequence", "success", 100.0),
            ("sequence/check", "Condition", "success", 0.0),
            ("sequence/heal", "Action", "success", 50.0),
        ],
    )
    output = format_trace(trace, use_color=False)
    lines = output.strip().split("\n")

    # Should have header + 3 nodes
    assert len(lines) == 4
    # Nested nodes should be indented
    assert "    " in lines[2]  # check is indented
    assert "    " in lines[3]  # heal is indented


def test_format_trace_failure_status():
    """format_trace should show failure status."""
    trace = _make_trace(
        executions=[("action", "Action", "failure", 10.0)],
        status="failure",
    )
    output = format_trace(trace, use_color=False)

    assert "✗" in output


def test_format_trace_with_path():
    """format_trace with show_path should show full paths."""
    trace = _make_trace(
        executions=[("root/sequence/action", "Action", "success", 10.0)],
    )
    output = format_trace(trace, use_color=False, show_path=True)

    assert "root/sequence/action" in output


def test_format_trace_without_duration():
    """format_trace without duration should hide timing."""
    trace = _make_trace(
        executions=[("action", "Action", "success", 10.0)],
    )
    output = format_trace(trace, use_color=False, show_duration=False)

    # Duration should not appear in output
    assert "10ms" not in output


# --- format_timeline tests ---


def test_format_timeline_empty():
    """format_timeline should handle empty executions."""
    trace = _make_trace()
    output = format_timeline(trace, use_color=False)

    assert "Timeline for Trace #1" in output
    assert "(no executions)" in output


def test_format_timeline_single_node():
    """format_timeline should show a single node with bar."""
    trace = _make_trace(
        executions=[("action", "Action", "success", 50.0)],
        duration_ms=100.0,
    )
    output = format_timeline(trace, use_color=False, bar_width=20)

    assert "Timeline" in output
    assert "action" in output
    # Should have some filled characters for 50% duration
    assert "#" in output


def test_format_timeline_multiple_nodes():
    """format_timeline should show multiple nodes."""
    trace = _make_trace(
        executions=[
            ("fast", "Action", "success", 10.0),
            ("slow", "Action", "success", 90.0),
        ],
        duration_ms=100.0,
    )
    output = format_timeline(trace, use_color=False, bar_width=20)
    lines = output.strip().split("\n")

    # Header, separator, 2 nodes
    assert len(lines) == 4

    # slow should have more filled characters than fast
    fast_line = [ln for ln in lines if "fast" in ln][0]
    slow_line = [ln for ln in lines if "slow" in ln][0]
    assert fast_line.count("#") < slow_line.count("#")


def test_format_timeline_status_icons():
    """format_timeline should show status icons."""
    trace = _make_trace(
        executions=[
            ("success_node", "Action", "success", 10.0),
            ("failure_node", "Action", "failure", 10.0),
        ],
    )
    output = format_timeline(trace, use_color=False)

    assert "✓" in output
    assert "✗" in output


# --- Integration test ---


@pytest.mark.integration
def test_visualization_with_real_trace():
    """Test visualization with a real trace from Vivarium."""
    from vivarium.core import Action, BehaviorTree, NodeStatus, Sequence, State

    from treehouse import TraceCollector

    class CheckHealth(Action):
        def __init__(self):
            super().__init__("check_health")

        def execute(self, state) -> NodeStatus:
            return NodeStatus.SUCCESS

    class Heal(Action):
        def __init__(self):
            super().__init__("heal")

        def execute(self, state) -> NodeStatus:
            return NodeStatus.SUCCESS

    collector = TraceCollector()
    tree = BehaviorTree(
        root=Sequence("main", [CheckHealth(), Heal()]),
        emitter=collector,
    )

    tree.tick(State())

    trace = collector.get_trace()
    assert trace is not None

    # Test tree view
    tree_output = format_trace(trace, use_color=False)
    assert "Trace #1" in tree_output
    assert "main" in tree_output
    assert "check_health" in tree_output
    assert "heal" in tree_output

    # Test timeline view
    timeline_output = format_timeline(trace, use_color=False)
    assert "Timeline" in timeline_output
