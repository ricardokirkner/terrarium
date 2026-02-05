from __future__ import annotations

from datetime import datetime, timedelta, timezone

from treehouse.telemetry import ExecutionTrace, NodeExecution
from treehouse.visualizer.storage import TraceStorage, parse_timestamp


def _trace(trace_id: str) -> ExecutionTrace:
    now = datetime.now(timezone.utc)
    end = now + timedelta(milliseconds=50)
    return ExecutionTrace(
        trace_id=trace_id,
        tick_id=1,
        start_time=now,
        end_time=end,
        status="success",
        executions=[
            NodeExecution(
                node_id="work",
                node_name="work",
                node_type="Action",
                path_in_tree="root/work",
                start_time=now,
                timestamp=end,
                status="success",
                duration_ms=50.0,
            )
        ],
    )


def test_trace_storage_save_get_list_delete(tmp_path):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    trace = _trace("trace-1")

    storage.save_trace(trace)

    stored = storage.get_trace(trace.trace_id)
    assert stored is not None
    assert stored.trace_id == trace.trace_id
    assert stored.tick_id == trace.tick_id

    traces = storage.list_traces(limit=10)
    assert any(item["trace_id"] == trace.trace_id for item in traces)

    assert storage.delete_trace(trace.trace_id) is True
    assert storage.get_trace(trace.trace_id) is None


def test_trace_storage_export_import(tmp_path):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    trace = _trace("trace-export")
    storage.save_trace(trace)

    export_path = tmp_path / "trace.json"
    assert storage.export_trace_json(trace.trace_id, export_path) is True
    imported = storage.import_trace_json(export_path)

    assert imported.trace_id
    assert storage.get_trace(imported.trace_id) is not None


def test_trace_storage_export_missing_trace(tmp_path):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    export_path = tmp_path / "missing.json"
    assert storage.export_trace_json("missing", export_path) is False


def test_parse_timestamp_handles_empty():
    assert parse_timestamp(None) is None


def test_parse_timestamp_parses_value():
    now = datetime.now(timezone.utc)
    parsed = parse_timestamp(now.isoformat())
    assert parsed == now
