"""Tests for treehouse visualization module."""

from datetime import datetime, timedelta, timezone
from typing import TextIO, cast

import pytest

from treehouse.telemetry import ExecutionTrace, NodeExecution
from treehouse.visualization import (
    _format_cost,
    _format_duration,
    _format_tokens,
    _get_depth,
    _get_node_name,
    _status_icon,
    _supports_color,
    _truncate,
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


def test_format_tokens_empty():
    assert _format_tokens(None) == ""


def test_format_tokens_values():
    assert (
        _format_tokens({"prompt": 1, "completion": 2, "total": 3}) == "3 tokens (1p/2c)"
    )


def test_format_cost():
    assert _format_cost(None) == "free"
    assert _format_cost(0.0) == "free"
    assert _format_cost(0.005) == "$0.0050"
    assert _format_cost(0.1) == "$0.10"


def test_truncate():
    assert _truncate("", 5) == ""
    assert _truncate("hello", 5) == "hello"
    assert _truncate("hello world", 5) == "he..."


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


def test_supports_color_env(monkeypatch):
    class Dummy:
        def isatty(self):
            return True

    dummy = Dummy()

    monkeypatch.setenv("NO_COLOR", "1")
    assert _supports_color(cast(TextIO, dummy)) is False

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert _supports_color(cast(TextIO, dummy)) is True

    monkeypatch.delenv("FORCE_COLOR", raising=False)


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


def test_format_trace_llm_data():
    now = datetime.now(timezone.utc)
    execution = NodeExecution(
        node_id="llm",
        node_name="llm",
        node_type="Action",
        path_in_tree="root/llm",
        timestamp=now,
        status="success",
        duration_ms=2.0,
        llm_prompt="Summarize this text",
        llm_response="Summary",
        llm_tokens={"prompt": 2, "completion": 3, "total": 5},
        llm_cost=0.01,
        llm_model="mock",
    )
    trace = ExecutionTrace(
        tick_id=1,
        start_time=now,
        end_time=now + timedelta(milliseconds=2),
        status="success",
        executions=[execution],
    )
    output = format_trace(trace, use_color=False, show_llm=True)
    assert "Prompt:" in output
    assert "Response:" in output
    assert "5 tokens" in output
    assert "$0.01" in output


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


def test_format_timeline_output():
    trace = _make_trace(
        executions=[
            ("action", "Action", "success", 10.0),
            ("check", "Condition", "failure", 0.0),
        ],
        duration_ms=20.0,
    )
    output = format_timeline(trace, use_color=False, bar_width=10)
    assert "Timeline for Trace #1" in output
    assert "action" in output
    assert "check" in output


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


def test_supports_color_not_tty(monkeypatch):
    """_supports_color should return False when file is not a TTY."""
    import io

    from treehouse.visualization import _supports_color

    # Test with a StringIO (not a TTY)
    string_file = io.StringIO()
    assert _supports_color(string_file) is False


def test_status_icon_without_color():
    """_status_icon should return plain icons when use_color=False."""
    from treehouse.visualization import _status_icon

    assert _status_icon("success", use_color=False) == "✓"
    assert _status_icon("failure", use_color=False) == "✗"
    assert _status_icon("running", use_color=False) == "⏸"
    assert _status_icon("unknown", use_color=False) == "?"


def test_get_node_name_empty():
    """_get_node_name should handle empty path."""
    from treehouse.visualization import _get_node_name

    assert _get_node_name("") == ""


def test_print_trace_with_custom_file():
    """print_trace should write to provided file object."""
    import io

    from treehouse.visualization import print_trace

    trace = _make_trace(
        executions=[("task", "Action", "success", 10.0)],
    )
    output_file = io.StringIO()
    print_trace(trace, file=output_file, use_color=False)

    output = output_file.getvalue()
    assert "task" in output
    assert "Action" in output


def test_format_trace_without_color():
    """format_trace should format without color codes when use_color=False."""
    trace = _make_trace(
        executions=[("work", "Action", "success", 25.0)],
    )
    output = format_trace(trace, use_color=False)

    # Should not contain ANSI escape codes
    assert "\x1b[" not in output
    # Should contain the node info
    assert "work" in output
    assert "[Action]" in output


def test_format_trace_llm_without_color():
    """format_trace should format LLM data without color."""
    from datetime import datetime, timezone

    from treehouse.telemetry import NodeExecution

    now = datetime.now(timezone.utc)
    trace = _make_trace(executions=[])
    trace.executions = [
        NodeExecution(
            node_id="llm_task",
            node_name="llm_task",
            node_type="Action",
            path_in_tree="root/llm_task",
            timestamp=now,
            status="success",
            duration_ms=100.0,
            llm_prompt="Long prompt text that should be truncated properly",
            llm_response="Response text that should also be truncated",
            llm_model="gpt-4",
            llm_tokens={"total": 50},
            llm_cost=0.001,
        )
    ]

    output = format_trace(trace, use_color=False, show_llm=True)

    # Should show LLM data without color codes
    assert "\x1b[" not in output
    assert "gpt-4" in output or "model" in output.lower()
    assert "Prompt:" in output
    assert "Response:" in output


def test_print_timeline_with_custom_file():
    """print_timeline should write to provided file object."""
    import io

    from treehouse.visualization import print_timeline

    trace = _make_trace(
        executions=[("task", "Action", "success", 10.0)],
    )
    output_file = io.StringIO()
    print_timeline(trace, file=output_file, use_color=False)

    output = output_file.getvalue()
    assert "task" in output
    assert "Timeline" in output


def test_format_timeline_without_color():
    """format_timeline should format without color when use_color=False."""
    trace = _make_trace(
        executions=[
            ("fast", "Action", "success", 10.0),
            ("slow", "Action", "success", 50.0),
        ],
    )
    output = format_timeline(trace, use_color=False)

    # Should not contain ANSI escape codes
    assert "\x1b[" not in output
    # Should contain timeline header
    assert "Timeline" in output
    assert "fast" in output
    assert "slow" in output


def test_print_trace_with_color():
    """print_trace should include color codes when use_color=True."""
    import io

    from treehouse.visualization import print_trace

    trace = _make_trace(
        executions=[("task", "Action", "success", 10.0)],
    )
    output_file = io.StringIO()
    print_trace(trace, file=output_file, use_color=True)

    output = output_file.getvalue()
    # Should contain ANSI escape codes
    assert "\x1b[" in output


def test_print_trace_with_llm_and_color():
    """print_trace should format LLM data with color."""
    import io
    from datetime import datetime, timezone

    from treehouse.telemetry import NodeExecution
    from treehouse.visualization import print_trace

    now = datetime.now(timezone.utc)
    trace = _make_trace(executions=[])
    trace.executions = [
        NodeExecution(
            node_id="llm_task",
            node_name="llm_task",
            node_type="Action",
            path_in_tree="root/llm_task",
            timestamp=now,
            status="success",
            duration_ms=100.0,
            llm_prompt="Test prompt",
            llm_response="Test response",
            llm_model="gpt-4",
            llm_tokens={"total": 50},
            llm_cost=0.001,
        )
    ]

    output_file = io.StringIO()
    print_trace(trace, file=output_file, use_color=True, show_llm=True)

    output = output_file.getvalue()
    # Should contain color codes and LLM data
    assert "\x1b[" in output
    assert "gpt-4" in output or "model" in output.lower()


def test_print_timeline_with_color():
    """print_timeline should include color codes when use_color=True."""
    import io

    from treehouse.visualization import print_timeline

    trace = _make_trace(
        executions=[
            ("fast", "Action", "success", 10.0),
            ("slow", "Action", "failure", 50.0),
        ],
    )
    output_file = io.StringIO()
    print_timeline(trace, file=output_file, use_color=True)

    output = output_file.getvalue()
    # Should contain ANSI escape codes for colors
    assert "\x1b[" in output


def test_print_timeline_zero_duration():
    """print_timeline should handle zero total duration."""
    import io
    from datetime import datetime, timezone

    from treehouse.telemetry import ExecutionTrace, NodeExecution
    from treehouse.visualization import print_timeline

    now = datetime.now(timezone.utc)
    trace = ExecutionTrace(tick_id=1, start_time=now, end_time=now, status="success")
    trace.executions = [
        NodeExecution(
            node_id="instant",
            node_name="instant",
            node_type="Action",
            path_in_tree="root/instant",
            timestamp=now,
            status="success",
            duration_ms=0.0,
        )
    ]

    output_file = io.StringIO()
    print_timeline(trace, file=output_file, use_color=False)

    output = output_file.getvalue()
    assert "instant" in output


def test_print_timeline_all_zero_durations():
    """print_timeline should handle all executions with zero duration."""
    import io
    from datetime import datetime, timezone

    from treehouse.telemetry import ExecutionTrace, NodeExecution
    from treehouse.visualization import print_timeline

    now = datetime.now(timezone.utc)
    trace = ExecutionTrace(tick_id=1, start_time=now, end_time=now, status="success")
    trace.executions = [
        NodeExecution(
            node_id="instant1",
            node_name="instant1",
            node_type="Action",
            path_in_tree="root/instant1",
            timestamp=now,
            status="success",
            duration_ms=0.0,
        ),
        NodeExecution(
            node_id="instant2",
            node_name="instant2",
            node_type="Action",
            path_in_tree="root/instant2",
            timestamp=now,
            status="success",
            duration_ms=0.0,
        ),
    ]

    output_file = io.StringIO()
    print_timeline(trace, file=output_file, use_color=False)

    output = output_file.getvalue()
    # Should handle division by zero
    assert "instant1" in output
    assert "instant2" in output


# --- Integration test ---


@pytest.mark.integration
def test_visualization_with_real_trace():
    """Test visualization with a real trace from Vivarium."""
    from vivarium import Action, BehaviorTree, NodeStatus, Sequence, State

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
