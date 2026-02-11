"""Treehouse: External observability and interpretability for behavior trees."""

__version__ = "0.1.1"

from treehouse.debugger import DebuggerClient
from treehouse.debugging import BreakpointConfig, DebuggerCommand, DebuggerTree
from treehouse.metrics import calculate_metrics
from treehouse.telemetry import ExecutionTrace, NodeExecution, TraceCollector
from treehouse.visualization import (
    format_timeline,
    format_trace,
    print_timeline,
    print_trace,
)

__all__ = [
    "__version__",
    "BreakpointConfig",
    "DebuggerClient",
    "DebuggerCommand",
    "DebuggerTree",
    "ExecutionTrace",
    "NodeExecution",
    "TraceCollector",
    "calculate_metrics",
    "format_timeline",
    "format_trace",
    "print_timeline",
    "print_trace",
]
