"""Text-based visualization for behavior tree execution traces.

This module provides functions to display ExecutionTrace data in
human-readable terminal output, including tree structure view and
chronological timeline view.
"""

from __future__ import annotations

import os
import sys
from io import StringIO
from typing import TextIO

from .telemetry import ExecutionTrace, NodeExecution


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _supports_color(file: TextIO) -> bool:
    """Check if the output file supports ANSI colors."""
    # Respect NO_COLOR environment variable
    if os.environ.get("NO_COLOR"):
        return False

    # Check if FORCE_COLOR is set
    if os.environ.get("FORCE_COLOR"):
        return True

    # Check if output is a TTY
    if hasattr(file, "isatty") and file.isatty():
        return True

    return False


def _status_icon(status: str, use_color: bool = True) -> str:
    """Return a status icon with optional color."""
    icons = {
        "success": ("✓", Colors.GREEN),
        "failure": ("✗", Colors.RED),
        "running": ("⏸", Colors.YELLOW),
    }
    icon, color = icons.get(status, ("?", Colors.DIM))

    if use_color:
        return f"{color}{icon}{Colors.RESET}"
    return icon


def _format_duration(duration_ms: float) -> str:
    """Format duration in a human-readable way."""
    if duration_ms < 1:
        return "<1ms"
    elif duration_ms < 1000:
        return f"{duration_ms:.0f}ms"
    else:
        return f"{duration_ms / 1000:.2f}s"


def _truncate(text: str, max_len: int = 50) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    # Replace newlines with spaces for single-line display
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _format_tokens(tokens: dict[str, int] | None) -> str:
    """Format token usage dict for display."""
    if not tokens:
        return ""
    total = tokens.get("total", 0)
    prompt = tokens.get("prompt", 0)
    completion = tokens.get("completion", 0)
    return f"{total} tokens ({prompt}p/{completion}c)"


def _format_cost(cost: float | None) -> str:
    """Format cost for display."""
    if cost is None or cost == 0:
        return "free"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def _get_depth(path: str) -> int:
    """Get the depth of a node from its path."""
    if not path:
        return 0
    return path.count("/")


def _get_node_name(path: str) -> str:
    """Extract the node name from a path, removing index suffixes."""
    if not path:
        return ""
    name = path.split("/")[-1]
    # Remove index like [0], [1], etc.
    if "[" in name:
        name = name.split("[")[0]
    return name


def print_trace(
    trace: ExecutionTrace,
    file: TextIO | None = None,
    use_color: bool | None = None,
    show_duration: bool = True,
    show_path: bool = False,
    show_llm: bool = True,
) -> None:
    """Print an execution trace in a tree-like format.

    Args:
        trace: The ExecutionTrace to display.
        file: Output file (defaults to sys.stdout).
        use_color: Whether to use ANSI colors. Auto-detected if None.
        show_duration: Whether to show execution duration for each node.
        show_path: Whether to show the full path instead of just the name.
        show_llm: Whether to show LLM prompt/response for LLM nodes.

    Example output:
        Trace #1 [success] (12.5ms)
        ├── main_sequence [Sequence] ✓ (12.5ms)
        │   ├── check_health [Condition] ✓
        │   └── heal [Action] ✓ (10.2ms)
    """
    if file is None:
        file = sys.stdout

    if use_color is None:
        use_color = _supports_color(file)

    # Header
    total_duration = 0.0
    if trace.start_time and trace.end_time:
        total_duration = (trace.end_time - trace.start_time).total_seconds() * 1000

    status_str = _status_icon(trace.status, use_color)
    duration_str = f" ({_format_duration(total_duration)})" if show_duration else ""

    if use_color:
        header = (
            f"{Colors.BOLD}Trace #{trace.tick_id}{Colors.RESET} "
            f"[{status_str}]{duration_str}"
        )
    else:
        header = f"Trace #{trace.tick_id} [{trace.status}]{duration_str}"

    print(header, file=file)

    if not trace.executions:
        print("  (no executions)", file=file)
        return

    # Build tree structure from flat executions
    _print_executions_as_tree(
        trace.executions, file, use_color, show_duration, show_path, show_llm
    )


def _print_executions_as_tree(
    executions: list[NodeExecution],
    file: TextIO,
    use_color: bool,
    show_duration: bool,
    show_path: bool,
    show_llm: bool = True,
) -> None:
    """Print executions with tree-like indentation."""
    for i, execution in enumerate(executions):
        depth = _get_depth(execution.path_in_tree)
        is_last = i == len(executions) - 1 or (
            i + 1 < len(executions)
            and _get_depth(executions[i + 1].path_in_tree) <= depth
        )

        # Build prefix
        indent = "    " * depth
        connector = "└── " if is_last else "├── "

        # Node info
        name = (
            execution.path_in_tree
            if show_path
            else _get_node_name(execution.path_in_tree)
        )
        node_type = execution.node_type
        status = _status_icon(execution.status, use_color)

        # Duration (skip for conditions which are instant)
        duration = ""
        if show_duration and execution.duration_ms > 0:
            duration = f" ({_format_duration(execution.duration_ms)})"

        # Format node type
        if use_color:
            type_str = f"{Colors.DIM}[{node_type}]{Colors.RESET}"
        else:
            type_str = f"[{node_type}]"

        line = f"{indent}{connector}{name} {type_str} {status}{duration}"
        print(line, file=file)

        # Show LLM data if present and enabled
        if show_llm and execution.has_llm_data:
            _print_llm_data(execution, file, use_color, indent, is_last)


def _print_llm_data(
    execution: NodeExecution,
    file: TextIO,
    use_color: bool,
    parent_indent: str,
    is_last_node: bool,
) -> None:
    """Print LLM execution data for a node."""
    # Continue the tree line if not last node
    continuation = "    " if is_last_node else "│   "
    indent = parent_indent + continuation

    # Token/cost info
    tokens_str = _format_tokens(execution.llm_tokens)
    cost_str = _format_cost(execution.llm_cost)
    model = execution.llm_model or "unknown"

    if use_color:
        model_str = f"{Colors.CYAN}{model}{Colors.RESET}"
        info_line = (
            f"{indent}    {Colors.DIM}{model_str} | "
            f"{tokens_str} | {cost_str}{Colors.RESET}"
        )
    else:
        info_line = f"{indent}    [{model}] {tokens_str} | {cost_str}"
    print(info_line, file=file)

    # Prompt (truncated)
    if execution.llm_prompt:
        prompt_preview = _truncate(execution.llm_prompt, 60)
        if use_color:
            print(
                f"{indent}    {Colors.DIM}Prompt: {prompt_preview}{Colors.RESET}",
                file=file,
            )
        else:
            print(f"{indent}    Prompt: {prompt_preview}", file=file)

    # Response (truncated)
    if execution.llm_response:
        response_preview = _truncate(execution.llm_response, 60)
        if use_color:
            print(
                f"{indent}    {Colors.DIM}Response: {response_preview}{Colors.RESET}",
                file=file,
            )
        else:
            print(f"{indent}    Response: {response_preview}", file=file)


def print_timeline(
    trace: ExecutionTrace,
    file: TextIO | None = None,
    use_color: bool | None = None,
    bar_width: int = 40,
) -> None:
    """Print an execution trace as a chronological timeline.

    Shows each node execution as a horizontal bar, with bar length
    proportional to duration relative to the total trace duration.

    Args:
        trace: The ExecutionTrace to display.
        file: Output file (defaults to sys.stdout).
        use_color: Whether to use ANSI colors. Auto-detected if None.
        bar_width: Maximum width of the duration bar in characters.

    Example output:
        Timeline for Trace #1 (12.5ms total)
        ──────────────────────────────────────
        main_sequence    [████████████████████] 12.5ms
        check_health     [                    ]  <1ms
        heal             [████████████████    ] 10.2ms
    """
    if file is None:
        file = sys.stdout

    if use_color is None:
        use_color = _supports_color(file)

    # Calculate total duration
    total_duration = 0.0
    if trace.start_time and trace.end_time:
        total_duration = (trace.end_time - trace.start_time).total_seconds() * 1000

    # Header
    duration_fmt = _format_duration(total_duration)
    if use_color:
        header = (
            f"{Colors.BOLD}Timeline for Trace #{trace.tick_id}{Colors.RESET} "
            f"({duration_fmt} total)"
        )
    else:
        header = f"Timeline for Trace #{trace.tick_id} ({duration_fmt} total)"

    print(header, file=file)
    print("─" * (bar_width + 30), file=file)

    if not trace.executions:
        print("  (no executions)", file=file)
        return

    # Find max name length for alignment
    max_name_len = max(len(_get_node_name(e.path_in_tree)) for e in trace.executions)
    max_name_len = min(max_name_len, 20)  # Cap at 20 chars

    # Find max duration for scaling
    max_duration = max((e.duration_ms for e in trace.executions), default=1.0)
    if max_duration == 0:
        max_duration = 1.0  # Avoid division by zero

    for execution in trace.executions:
        name = _get_node_name(execution.path_in_tree)[:max_name_len].ljust(max_name_len)

        # Calculate bar length
        if total_duration > 0:
            bar_len = int((execution.duration_ms / total_duration) * bar_width)
        else:
            bar_len = 0

        # Choose bar color based on status
        if use_color:
            bar_color = {
                "success": Colors.GREEN,
                "failure": Colors.RED,
                "running": Colors.YELLOW,
            }.get(execution.status, Colors.DIM)
            bar = (
                f"{bar_color}{'█' * bar_len}{Colors.RESET}{'░' * (bar_width - bar_len)}"
            )
        else:
            bar = f"{'#' * bar_len}{'-' * (bar_width - bar_len)}"

        duration = _format_duration(execution.duration_ms).rjust(8)
        status = _status_icon(execution.status, use_color)

        line = f"{name} [{bar}] {duration} {status}"
        print(line, file=file)


def format_trace(
    trace: ExecutionTrace,
    use_color: bool = False,
    show_duration: bool = True,
    show_path: bool = False,
    show_llm: bool = True,
) -> str:
    """Format an execution trace as a string.

    Same as print_trace but returns a string instead of printing.

    Args:
        trace: The ExecutionTrace to format.
        use_color: Whether to include ANSI colors.
        show_duration: Whether to show execution duration.
        show_path: Whether to show full paths.
        show_llm: Whether to show LLM prompt/response for LLM nodes.

    Returns:
        Formatted string representation of the trace.
    """
    buffer = StringIO()
    print_trace(
        trace,
        file=buffer,
        use_color=use_color,
        show_duration=show_duration,
        show_path=show_path,
        show_llm=show_llm,
    )
    return buffer.getvalue()


def format_timeline(
    trace: ExecutionTrace,
    use_color: bool = False,
    bar_width: int = 40,
) -> str:
    """Format an execution trace timeline as a string.

    Same as print_timeline but returns a string instead of printing.

    Args:
        trace: The ExecutionTrace to format.
        use_color: Whether to include ANSI colors.
        bar_width: Maximum width of the duration bar.

    Returns:
        Formatted string representation of the timeline.
    """
    buffer = StringIO()
    print_timeline(trace, file=buffer, use_color=use_color, bar_width=bar_width)
    return buffer.getvalue()
