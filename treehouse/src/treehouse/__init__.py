"""Treehouse: External observability and interpretability for behavior trees."""

from treehouse.debugger import DebuggerClient
from treehouse.metrics import calculate_metrics
from treehouse.telemetry import ExecutionTrace, NodeExecution, TraceCollector
from treehouse.visualization import (
    format_timeline,
    format_trace,
    print_timeline,
    print_trace,
)

__all__ = [
    "DebuggerClient",
    "calculate_metrics",
    "ExecutionTrace",
    "NodeExecution",
    "TraceCollector",
    "format_timeline",
    "format_trace",
    "print_timeline",
    "print_trace",
]
