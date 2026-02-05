"""Metrics and analysis for behavior tree execution traces."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .telemetry import ExecutionTrace, NodeExecution


def _token_counts(tokens: dict[str, int] | None) -> dict[str, int]:
    if not tokens:
        return {"prompt": 0, "completion": 0, "total": 0}
    return {
        "prompt": int(tokens.get("prompt", 0)),
        "completion": int(tokens.get("completion", 0)),
        "total": int(tokens.get("total", 0)),
    }


def _llm_present(execution: NodeExecution) -> bool:
    if execution.llm_prompt is not None:
        return True
    if execution.llm_tokens is not None:
        return True
    if execution.llm_cost is not None:
        return True
    if execution.llm_model is not None:
        return True
    return False


def calculate_metrics(trace: ExecutionTrace, top_n: int = 5) -> dict[str, Any]:
    """Calculate summary metrics for an execution trace.

    Args:
        trace: ExecutionTrace to analyze.
        top_n: Number of top items to include in rankings.

    Returns:
        Dictionary with totals, breakdowns, and rankings.
    """
    executions = trace.executions
    node_count = len(executions)

    total_duration_ms = 0.0
    if trace.start_time and trace.end_time:
        total_duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
    else:
        total_duration_ms = sum(e.duration_ms for e in executions)

    total_execution_duration_ms = sum(e.duration_ms for e in executions)

    token_totals = {"prompt": 0, "completion": 0, "total": 0}
    total_cost = 0.0
    llm_call_count = 0

    by_node_type: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "duration_ms": 0.0,
            "cost": 0.0,
            "tokens": {"prompt": 0, "completion": 0, "total": 0},
        }
    )

    for execution in executions:
        if _llm_present(execution):
            llm_call_count += 1

        tokens = _token_counts(execution.llm_tokens)
        token_totals["prompt"] += tokens["prompt"]
        token_totals["completion"] += tokens["completion"]
        token_totals["total"] += tokens["total"]

        if execution.llm_cost is not None:
            total_cost += execution.llm_cost

        node_type = execution.node_type
        by_node_type[node_type]["count"] += 1
        by_node_type[node_type]["duration_ms"] += execution.duration_ms
        by_node_type[node_type]["cost"] += execution.llm_cost or 0.0
        by_node_type[node_type]["tokens"]["prompt"] += tokens["prompt"]
        by_node_type[node_type]["tokens"]["completion"] += tokens["completion"]
        by_node_type[node_type]["tokens"]["total"] += tokens["total"]

    top_cost_nodes = [
        {
            "node_id": e.node_id,
            "node_type": e.node_type,
            "path_in_tree": e.path_in_tree,
            "cost": e.llm_cost or 0.0,
            "duration_ms": e.duration_ms,
        }
        for e in executions
        if (e.llm_cost or 0.0) > 0
    ]
    top_cost_nodes.sort(key=lambda item: item["cost"], reverse=True)
    top_cost_nodes = top_cost_nodes[:top_n]

    top_duration_nodes = [
        {
            "node_id": e.node_id,
            "node_type": e.node_type,
            "path_in_tree": e.path_in_tree,
            "duration_ms": e.duration_ms,
            "status": e.status,
        }
        for e in executions
        if e.duration_ms > 0
    ]
    top_duration_nodes.sort(key=lambda item: item["duration_ms"], reverse=True)
    top_duration_nodes = top_duration_nodes[:top_n]

    return {
        "trace_id": trace.trace_id,
        "tick_id": trace.tick_id,
        "status": trace.status,
        "node_count": node_count,
        "llm_call_count": llm_call_count,
        "total_duration_ms": total_duration_ms,
        "total_execution_duration_ms": total_execution_duration_ms,
        "total_tokens": token_totals,
        "total_cost": total_cost,
        "by_node_type": dict(by_node_type),
        "top_cost_nodes": top_cost_nodes,
        "top_duration_nodes": top_duration_nodes,
    }
