"""SQLite-backed trace storage for the visualizer."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from treehouse.telemetry import ExecutionTrace


@dataclass
class TraceRecord:
    trace_id: str
    tick_id: int
    status: str
    start_time: str | None
    end_time: str | None
    trace_json: str
    metadata_json: str


class TraceStorage:
    """SQLite storage for execution traces."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".treehouse" / "traces.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    tick_id INTEGER,
                    status TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    trace_json TEXT,
                    metadata_json TEXT
                )
                """)

    def save_trace(self, trace: ExecutionTrace) -> None:
        trace_dict = trace.to_dict()
        record = TraceRecord(
            trace_id=trace.trace_id,
            tick_id=trace.tick_id,
            status=trace.status,
            start_time=trace_dict.get("start_time"),
            end_time=trace_dict.get("end_time"),
            trace_json=json.dumps(trace_dict),
            metadata_json=json.dumps(trace.metadata or {}),
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO traces
                (
                    trace_id,
                    tick_id,
                    status,
                    start_time,
                    end_time,
                    trace_json,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.trace_id,
                    record.tick_id,
                    record.status,
                    record.start_time,
                    record.end_time,
                    record.trace_json,
                    record.metadata_json,
                ),
            )

    def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT trace_json FROM traces WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()

        if not row:
            return None

        trace_dict = json.loads(row["trace_json"])
        return ExecutionTrace.from_dict(trace_dict)

    def list_traces(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trace_id, tick_id, status, start_time, end_time, metadata_json
                FROM traces
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        results = []
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            results.append(
                {
                    "trace_id": row["trace_id"],
                    "tick_id": row["tick_id"],
                    "status": row["status"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "metadata": metadata,
                }
            )
        return results

    def delete_trace(self, trace_id: str) -> bool:
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM traces WHERE trace_id = ?",
                (trace_id,),
            )
        return result.rowcount > 0

    def export_trace_json(self, trace_id: str, output_path: str | Path) -> bool:
        trace = self.get_trace(trace_id)
        if trace is None:
            return False

        output_path = Path(output_path)
        output_path.write_text(trace.to_json())
        return True

    def import_trace_json(self, input_path: str | Path) -> ExecutionTrace:
        input_path = Path(input_path)
        trace = ExecutionTrace.from_json(input_path.read_text())
        self.save_trace(trace)
        return trace


def parse_timestamp(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp)
