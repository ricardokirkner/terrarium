from __future__ import annotations

from datetime import datetime, timedelta

from treehouse.metrics import calculate_metrics
from treehouse.telemetry import ExecutionTrace, NodeExecution


def _execution(
    *,
    node_id: str,
    node_type: str,
    path_in_tree: str,
    duration_ms: float,
    status: str = "success",
    llm_tokens: dict[str, int] | None = None,
    llm_cost: float | None = None,
    llm_model: str | None = None,
) -> NodeExecution:
    return NodeExecution(
        node_id=node_id,
        node_name=node_id,
        node_type=node_type,
        path_in_tree=path_in_tree,
        timestamp=datetime.now(),
        status=status,
        duration_ms=duration_ms,
        llm_tokens=llm_tokens,
        llm_cost=llm_cost,
        llm_model=llm_model,
        llm_prompt="prompt" if llm_tokens or llm_cost or llm_model else None,
        llm_response="response" if llm_tokens or llm_cost or llm_model else None,
    )


def test_calculate_metrics_totals_and_breakdowns():
    start = datetime.now()
    end = start + timedelta(milliseconds=1000)

    trace = ExecutionTrace(
        tick_id=1,
        start_time=start,
        end_time=end,
        status="success",
        executions=[
            _execution(
                node_id="a1",
                node_type="Action",
                path_in_tree="root/a1",
                duration_ms=120,
            ),
            _execution(
                node_id="llm_action",
                node_type="Action",
                path_in_tree="root/llm_action",
                duration_ms=500,
                llm_tokens={"prompt": 100, "completion": 20, "total": 120},
                llm_cost=0.02,
                llm_model="mock",
            ),
            _execution(
                node_id="llm_condition",
                node_type="Condition",
                path_in_tree="root/llm_condition",
                duration_ms=0,
                llm_tokens={"prompt": 50, "completion": 10, "total": 60},
                llm_cost=0.005,
                llm_model="mock",
            ),
        ],
    )

    metrics = calculate_metrics(trace, top_n=2)

    assert metrics["node_count"] == 3
    assert metrics["llm_call_count"] == 2
    assert metrics["total_cost"] == 0.025
    assert metrics["total_tokens"] == {"prompt": 150, "completion": 30, "total": 180}
    assert metrics["total_duration_ms"] == 1000

    by_type = metrics["by_node_type"]
    assert by_type["Action"]["count"] == 2
    assert by_type["Condition"]["count"] == 1
    assert by_type["Action"]["tokens"]["total"] == 120
    assert by_type["Condition"]["tokens"]["total"] == 60

    top_cost = metrics["top_cost_nodes"]
    assert len(top_cost) == 2
    assert top_cost[0]["node_id"] == "llm_action"
    assert top_cost[0]["cost"] == 0.02

    top_duration = metrics["top_duration_nodes"]
    assert len(top_duration) == 2
    assert top_duration[0]["node_id"] == "llm_action"
    assert top_duration[0]["duration_ms"] == 500


def test_total_duration_fallback_to_execution_sum():
    trace = ExecutionTrace(
        tick_id=2,
        status="failure",
        executions=[
            _execution(
                node_id="a1",
                node_type="Action",
                path_in_tree="root/a1",
                duration_ms=100,
            ),
            _execution(
                node_id="a2",
                node_type="Action",
                path_in_tree="root/a2",
                duration_ms=250,
            ),
        ],
    )

    metrics = calculate_metrics(trace)
    assert metrics["total_duration_ms"] == 350
    assert metrics["total_execution_duration_ms"] == 350


def test_metrics_handles_missing_llm_data():
    trace = ExecutionTrace(
        tick_id=3,
        status="success",
        executions=[
            _execution(
                node_id="a1",
                node_type="Action",
                path_in_tree="root/a1",
                duration_ms=10,
            ),
        ],
    )

    metrics = calculate_metrics(trace)
    assert metrics["llm_call_count"] == 0
    assert metrics["total_tokens"] == {"prompt": 0, "completion": 0, "total": 0}
    assert metrics["total_cost"] == 0.0


def test_llm_present_with_only_tokens():
    """_llm_present should detect LLM data when only tokens are present."""
    from datetime import datetime

    # Create execution with only llm_tokens (no llm_prompt)
    execution = NodeExecution(
        node_id="task",
        node_name="task",
        node_type="Action",
        path_in_tree="root/task",
        timestamp=datetime.now(),
        status="success",
        duration_ms=10.0,
        llm_tokens={"total": 100},
    )

    trace = ExecutionTrace(tick_id=1, status="success", executions=[execution])
    metrics = calculate_metrics(trace)
    # Should count as LLM call even without prompt
    assert metrics["llm_call_count"] == 1


def test_llm_present_with_only_cost():
    """_llm_present should detect LLM data when only cost is present."""
    from datetime import datetime

    # Create execution with only llm_cost (no llm_prompt or tokens)
    execution = NodeExecution(
        node_id="task",
        node_name="task",
        node_type="Action",
        path_in_tree="root/task",
        timestamp=datetime.now(),
        status="success",
        duration_ms=10.0,
        llm_cost=0.01,
    )

    trace = ExecutionTrace(tick_id=1, status="success", executions=[execution])
    metrics = calculate_metrics(trace)
    # Should count as LLM call
    assert metrics["llm_call_count"] == 1
    assert metrics["total_cost"] == 0.01


def test_llm_present_with_only_model():
    """_llm_present should detect LLM data when only model is present."""
    from datetime import datetime

    # Create execution with only llm_model (no llm_prompt, tokens, or cost)
    execution = NodeExecution(
        node_id="task",
        node_name="task",
        node_type="Action",
        path_in_tree="root/task",
        timestamp=datetime.now(),
        status="success",
        duration_ms=10.0,
        llm_model="gpt-4",
    )

    trace = ExecutionTrace(tick_id=1, status="success", executions=[execution])
    metrics = calculate_metrics(trace)
    # Should count as LLM call
    assert metrics["llm_call_count"] == 1
