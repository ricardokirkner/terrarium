from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

import pytest
from fastapi.testclient import TestClient

from treehouse.telemetry import ExecutionTrace, NodeExecution
from treehouse.visualizer import server
from treehouse.visualizer.storage import TraceStorage


def _trace(trace_id: str) -> ExecutionTrace:
    now = datetime.now(timezone.utc)
    end = now + timedelta(milliseconds=25)
    return ExecutionTrace(
        trace_id=trace_id,
        tick_id=3,
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
                duration_ms=25.0,
            )
        ],
    )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    monkeypatch.setattr(server, "storage", storage)
    server.manager.current_trace = None
    server.manager.viewers = []
    server.manager.agents = []
    with TestClient(server.app) as test_client:
        yield test_client


def test_trace_api_roundtrip(client):
    trace = _trace("trace-1")
    response = client.post("/api/traces", json=trace.to_dict())
    assert response.status_code == 200

    trace_id = response.json()["trace_id"]
    response = client.get(f"/api/traces/{trace_id}")
    assert response.status_code == 200
    assert response.json()["trace_id"] == trace_id

    response = client.get("/api/traces?limit=10")
    assert response.status_code == 200
    assert any(item["trace_id"] == trace_id for item in response.json()["traces"])

    response = client.delete(f"/api/traces/{trace_id}")
    assert response.status_code == 200

    response = client.get(f"/api/traces/{trace_id}")
    assert response.status_code == 404


def test_trace_api_export_import(client):
    trace = _trace("trace-2")
    response = client.post("/api/traces", json=trace.to_dict())
    trace_id = response.json()["trace_id"]

    response = client.get(f"/api/traces/{trace_id}/export")
    assert response.status_code == 200
    payload = response.json()

    response = client.post("/api/traces/import", json=payload)
    assert response.status_code == 200


def test_trace_api_missing_returns_404(client):
    response = client.get("/api/traces/missing")
    assert response.status_code == 404

    response = client.get("/api/traces/missing/export")
    assert response.status_code == 404

    response = client.delete("/api/traces/missing")
    assert response.status_code == 404


def test_trace_api_invalid_payload(client):
    response = client.post("/api/traces", json={"bad": "payload"})
    assert response.status_code == 400


def test_metrics_from_partial_state():
    state = {
        "trace_id": "trace-3",
        "tick_id": 1,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "executions": [],
        "status": "running",
    }
    metrics = server._calculate_metrics_from_state(state)
    assert metrics is not None
    assert metrics["tick_id"] == 1


def test_metrics_from_invalid_state():
    metrics = server._calculate_metrics_from_state(None)
    assert metrics is None

    metrics = server._calculate_metrics_from_state({"trace_id": "bad"})
    assert metrics is not None


def test_health_endpoint_counts(client):
    server.manager.viewers = cast(list, [object(), object()])
    server.manager.agents = cast(list, [object()])

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["viewers"] == 2
    assert data["agents"] == 1


@pytest.mark.asyncio
async def test_connect_viewer_sends_state_and_metrics(tmp_path, monkeypatch):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    monkeypatch.setattr(server, "storage", storage)

    manager = server.ConnectionManager()
    manager.current_trace = {
        "trace_id": "trace-5",
        "tick_id": 1,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "executions": [],
        "status": "running",
    }

    class FakeViewer:
        def __init__(self) -> None:
            self.accepted = False
            self.messages: list[dict] = []

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)

    viewer = FakeViewer()
    await manager.connect_viewer(viewer)  # type: ignore[arg-type]

    assert viewer.accepted is True
    types = [message["type"] for message in viewer.messages]
    assert "trace_state" in types
    assert "metrics_update" in types


@pytest.mark.asyncio
async def test_handle_agent_event_broadcasts_and_saves(tmp_path, monkeypatch):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    monkeypatch.setattr(server, "storage", storage)
    manager = server.ConnectionManager()

    class FakeViewer:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)

    viewer = FakeViewer()
    manager.viewers = cast(list, [viewer])

    await manager.handle_agent_event(
        {
            "type": "trace_start",
            "trace_id": "trace-4",
            "tick_id": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    await manager.handle_agent_event(
        {
            "type": "node_execution",
            "data": {
                "node_id": "task",
                "node_name": "task",
                "node_type": "Action",
                "path_in_tree": "root/task",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "duration_ms": 1.0,
            },
        }
    )
    await manager.handle_agent_event(
        {
            "type": "trace_complete",
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    types = {message.get("type") for message in viewer.messages}
    assert "trace_start" in types
    assert "node_execution" in types
    assert "trace_complete" in types
    assert "metrics_update" in types

    traces = storage.list_traces(limit=5)
    assert any(item["trace_id"] == "trace-4" for item in traces)


@pytest.mark.asyncio
async def test_connect_agent_and_disconnect(tmp_path, monkeypatch):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    monkeypatch.setattr(server, "storage", storage)
    manager = server.ConnectionManager()

    class FakeAgent:
        def __init__(self) -> None:
            self.accepted = False

        async def accept(self) -> None:
            self.accepted = True

    agent = FakeAgent()
    await manager.connect_agent(agent)  # type: ignore[arg-type]
    assert agent.accepted is True
    assert agent in manager.agents

    manager.disconnect_agent(agent)  # type: ignore[arg-type]
    assert agent not in manager.agents


@pytest.mark.asyncio
async def test_broadcast_removes_failed_viewers(tmp_path, monkeypatch):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    monkeypatch.setattr(server, "storage", storage)
    manager = server.ConnectionManager()

    class GoodViewer:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)

    class BadViewer:
        async def send_json(self, _message: dict) -> None:
            raise RuntimeError("boom")

    good = GoodViewer()
    bad = BadViewer()
    manager.viewers = cast(list, [good, bad])

    await manager.broadcast_to_viewers({"type": "test"})
    assert good in manager.viewers
    assert bad not in manager.viewers


def test_calculate_metrics_from_state_exception():
    # Pass malformed state that will raise during from_dict
    bad_state = {"trace_id": "test", "executions": "not-a-list"}
    metrics = server._calculate_metrics_from_state(bad_state)
    assert metrics is None


def test_save_trace_state_exception(tmp_path, monkeypatch):
    storage = TraceStorage(db_path=tmp_path / "traces.db")
    monkeypatch.setattr(server, "storage", storage)

    # Malformed state that will raise during from_dict
    bad_state = {"trace_id": "test", "executions": "not-a-list"}
    # Should not raise, just log exception
    server._save_trace_state(bad_state)


def test_import_trace_invalid_payload(client):
    response = client.post("/api/traces/import", json={"trace_id": "bad"})
    assert response.status_code == 400
    assert "Invalid trace payload" in response.json()["detail"]


def test_index_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Should return either index.html or fallback HTML
    assert "<!DOCTYPE html>" in response.text or "<html" in response.text.lower()


@pytest.mark.asyncio
async def test_viewer_websocket_disconnect():
    from fastapi import WebSocketDisconnect

    manager = server.ConnectionManager()

    class FakeViewerWS:
        def __init__(self) -> None:
            self.accepted = False
            self.disconnect_on_receive = True

        async def accept(self) -> None:
            self.accepted = True

        async def receive_text(self) -> str:
            if self.disconnect_on_receive:
                raise WebSocketDisconnect()
            return "{}"

    viewer_ws = FakeViewerWS()
    manager.viewers = []

    # Run the websocket handler which should handle disconnect
    try:
        await server.viewer_websocket(viewer_ws)  # type: ignore[arg-type]
    except WebSocketDisconnect:
        pass

    # Viewer should not be in list after disconnect
    assert viewer_ws not in manager.viewers


@pytest.mark.asyncio
async def test_viewer_websocket_exception():
    manager = server.ConnectionManager()

    class FakeViewerWS:
        def __init__(self) -> None:
            self.accepted = False

        async def accept(self) -> None:
            self.accepted = True

        async def receive_text(self) -> str:
            raise RuntimeError("test error")

    viewer_ws = FakeViewerWS()
    manager.viewers = []

    # Run the websocket handler which should handle exception
    await server.viewer_websocket(viewer_ws)  # type: ignore[arg-type]

    # Viewer should not be in list after error
    assert viewer_ws not in manager.viewers


@pytest.mark.asyncio
async def test_agent_websocket_disconnect():
    from fastapi import WebSocketDisconnect

    manager = server.ConnectionManager()

    class FakeAgentWS:
        def __init__(self) -> None:
            self.accepted = False

        async def accept(self) -> None:
            self.accepted = True

        async def receive_text(self) -> str:
            raise WebSocketDisconnect()

    agent_ws = FakeAgentWS()
    manager.agents = []

    # Run the websocket handler which should handle disconnect
    try:
        await server.agent_websocket(agent_ws)  # type: ignore[arg-type]
    except WebSocketDisconnect:
        pass

    # Agent should not be in list after disconnect
    assert agent_ws not in manager.agents


@pytest.mark.asyncio
async def test_agent_websocket_exception():
    manager = server.ConnectionManager()

    class FakeAgentWS:
        def __init__(self) -> None:
            self.accepted = False

        async def accept(self) -> None:
            self.accepted = True

        async def receive_text(self) -> str:
            raise RuntimeError("test error")

    agent_ws = FakeAgentWS()
    manager.agents = []

    # Run the websocket handler which should handle exception
    await server.agent_websocket(agent_ws)  # type: ignore[arg-type]

    # Agent should not be in list after error
    assert agent_ws not in manager.agents


def test_index_returns_fallback_when_no_static(monkeypatch):
    """index() should return fallback HTML when static file doesn't exist."""
    from pathlib import Path

    from fastapi.testclient import TestClient

    from treehouse.visualizer import server

    # Mock Path.exists to return False for index.html
    original_exists = Path.exists

    def fake_exists(self):
        if "index.html" in str(self):
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)

    with TestClient(server.app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Treehouse Visualizer" in response.text
        assert "Static files not found" in response.text


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_broadcast_to_agents_cleanup():
    """Test that broadcast_to_agents removes failed agents."""
    manager = server.ConnectionManager()

    class GoodAgent:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)

    class BadAgent:
        async def send_json(self, _message: dict) -> None:
            raise RuntimeError("boom")

    good = GoodAgent()
    bad = BadAgent()
    manager.agents = cast(list, [good, bad])

    await manager.broadcast_to_agents({"type": "test"})
    assert good in manager.agents
    assert bad not in manager.agents
