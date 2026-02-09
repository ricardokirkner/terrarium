"""Treehouse Web Visualizer - FastAPI Backend.

This module provides a WebSocket server for real-time behavior tree
visualization. Agents connect and stream execution events, while
browser clients connect to view the execution in real-time.

Usage:
    uvicorn treehouse.visualizer.server:app --reload

Or run directly:
    python -m treehouse.visualizer.server
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from treehouse.metrics import calculate_metrics
from treehouse.telemetry import ExecutionTrace
from treehouse.visualizer.storage import TraceStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TRACE_PAYLOAD = Body(...)


@dataclass
class ConnectionManager:
    """Manages WebSocket connections for agents and viewers.

    Agents send events, viewers receive them. This allows multiple
    browser windows to watch the same agent execution.
    """

    # Viewer connections (browser clients watching execution)
    viewers: list[WebSocket] = field(default_factory=list)
    # Agent connections (behavior tree agents sending events)
    agents: dict[str, WebSocket] = field(default_factory=dict)
    agent_by_socket: dict[WebSocket, str] = field(default_factory=dict)
    # Per-agent trace state (for new viewers joining mid-execution)
    agent_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    agent_info: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def connect_viewer(self, websocket: WebSocket) -> None:
        """Accept a new viewer connection."""
        await websocket.accept()
        self.viewers.append(websocket)
        logger.info(f"Viewer connected. Total viewers: {len(self.viewers)}")

        await websocket.send_json(
            {
                "type": "agent_list",
                "agents": [
                    {"id": agent_id, "name": info.get("name")}
                    for agent_id, info in sorted(self.agent_info.items())
                ],
            }
        )

        for agent_id, state in self.agent_state.items():
            current_trace = state.get("current_trace")
            tree_structure = state.get("tree_structure")
            if current_trace:
                await websocket.send_json(
                    {
                        "type": "trace_state",
                        "agent_id": agent_id,
                        "data": current_trace,
                    }
                )
                metrics = _calculate_metrics_from_state(current_trace)
                if metrics:
                    await websocket.send_json(
                        {
                            "type": "metrics_update",
                            "agent_id": agent_id,
                            "data": metrics,
                        }
                    )

            if tree_structure:
                await websocket.send_json(
                    {
                        "type": "tree_structure",
                        "agent_id": agent_id,
                        "data": tree_structure,
                    }
                )

    async def connect_agent(self, websocket: WebSocket) -> str:
        """Accept a new agent connection."""
        await websocket.accept()
        agent_id = uuid4().hex
        self.agents[agent_id] = websocket
        self.agent_by_socket[websocket] = agent_id
        self.agent_state.setdefault(
            agent_id, {"current_trace": None, "tree_structure": None}
        )
        self.agent_info.setdefault(agent_id, {"name": None})
        logger.info(f"Agent connected. Total agents: {len(self.agents)}")
        await self.broadcast_to_viewers(
            {
                "type": "agent_connected",
                "agent_id": agent_id,
                "name": self.agent_info.get(agent_id, {}).get("name"),
            }
        )
        return agent_id

    def disconnect_viewer(self, websocket: WebSocket) -> None:
        """Remove a viewer connection."""
        if websocket in self.viewers:
            self.viewers.remove(websocket)
            logger.info(f"Viewer disconnected. Total viewers: {len(self.viewers)}")

    def disconnect_agent(self, websocket: WebSocket) -> None:
        """Remove an agent connection."""
        agent_id = self.agent_by_socket.pop(websocket, None)
        if agent_id is None:
            for candidate_id, candidate_ws in list(self.agents.items()):
                if candidate_ws is websocket:
                    agent_id = candidate_id
                    break
        if agent_id and agent_id in self.agents:
            self.agents.pop(agent_id, None)
            self.agent_state.pop(agent_id, None)
            self.agent_info.pop(agent_id, None)
            logger.info(f"Agent disconnected. Total agents: {len(self.agents)}")
            logger.info(f"Agent disconnected: {agent_id}")
            asyncio.create_task(
                self.broadcast_to_viewers(
                    {"type": "agent_disconnected", "agent_id": agent_id}
                )
            )

    async def broadcast_to_viewers(self, message: dict[str, Any]) -> None:
        """Send a message to all connected viewers."""
        disconnected = []
        for viewer in self.viewers:
            try:
                await viewer.send_json(message)
            except Exception:
                disconnected.append(viewer)

        # Clean up disconnected viewers
        for viewer in disconnected:
            self.disconnect_viewer(viewer)

    async def broadcast_to_agents(
        self, message: dict[str, Any], agent_id: str | None = None
    ) -> None:
        """Send a message to all connected agents."""
        if agent_id:
            agent = self.agents.get(agent_id)
            if not agent:
                logger.warning(f"Agent not found for command: {agent_id}")
                return
            try:
                await agent.send_json(message)
                logger.info(f"✅ Sent to agent {agent_id} successfully")
            except Exception as e:
                logger.error(f"❌ Failed to send to agent {agent_id}: {e}")
                self.disconnect_agent(agent)
            return

        logger.info(f"📤 Broadcasting to {len(self.agents)} agent(s): {message}")
        disconnected_ids = []
        for agent_id, agent in list(self.agents.items()):
            try:
                await agent.send_json(message)
                logger.info("✅ Sent to agent successfully")
            except Exception as e:
                logger.error(f"❌ Failed to send to agent: {e}")
                disconnected_ids.append(agent_id)

        # Clean up disconnected agents
        for agent_id in disconnected_ids:
            agent = self.agents.get(agent_id)
            if agent:
                self.disconnect_agent(agent)

    async def _handle_agent_hello(self, agent_id: str, event: dict[str, Any]) -> bool:
        if event.get("type") != "agent_hello":
            return False
        info = self.agent_info.setdefault(agent_id, {"name": None})
        info["name"] = event.get("name") or info.get("name")
        await self.broadcast_to_viewers(
            {
                "type": "agent_info",
                "agent_id": agent_id,
                "name": info.get("name"),
            }
        )
        return True

    def _update_trace_state(
        self, agent_id: str, event: dict[str, Any]
    ) -> dict[str, Any] | None:
        state = self.agent_state.setdefault(
            agent_id, {"current_trace": None, "tree_structure": None}
        )
        current_trace = state.get("current_trace")
        tree_structure = state.get("tree_structure")
        event_type = event.get("type", "unknown")

        if event_type == "trace_start":
            metadata: dict[str, Any] = {}
            if tree_structure is not None:
                metadata["tree_structure"] = tree_structure
            current_trace = {
                "trace_id": event.get("trace_id"),
                "tick_id": event.get("tick_id"),
                "start_time": event.get("timestamp"),
                "executions": [],
                "status": "running",
                "metadata": metadata,
            }
            state["current_trace"] = current_trace
        elif event_type == "tree_structure":
            tree_structure = event.get("data", event)
            state["tree_structure"] = tree_structure
            if current_trace is not None:
                current_metadata = current_trace.get("metadata")
                if not isinstance(current_metadata, dict):
                    current_metadata = {}
                current_metadata["tree_structure"] = tree_structure
                current_trace["metadata"] = current_metadata
        elif event_type == "node_execution":
            if current_trace:
                current_trace["executions"].append(event.get("data", {}))
        elif event_type == "trace_complete":
            if current_trace:
                current_trace["end_time"] = event.get("timestamp")
                current_trace["status"] = event.get("status", "unknown")
                _save_trace_state(current_trace)

        return current_trace

    async def handle_agent_event(self, agent_id: str, event: dict[str, Any]) -> None:
        """Process an event from an agent and broadcast to viewers."""
        event_type = event.get("type", "unknown")
        logger.info(f"📡 Broadcasting {event_type} to {len(self.viewers)} viewer(s)")

        if await self._handle_agent_hello(agent_id, event):
            return

        current_trace = self._update_trace_state(agent_id, event)

        # Broadcast to all viewers
        event_with_agent = {**event, "agent_id": agent_id}
        await self.broadcast_to_viewers(event_with_agent)

        metrics = _calculate_metrics_from_state(current_trace)
        if metrics:
            await self.broadcast_to_viewers(
                {
                    "type": "metrics_update",
                    "agent_id": agent_id,
                    "data": metrics,
                }
            )


def _calculate_metrics_from_state(
    trace_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not trace_state:
        return None
    try:
        state = {
            "trace_id": trace_state.get("trace_id"),
            "tick_id": trace_state.get("tick_id", 0),
            "start_time": trace_state.get("start_time"),
            "end_time": trace_state.get("end_time"),
            "status": trace_state.get("status", "running"),
            "executions": trace_state.get("executions", []),
            "metadata": trace_state.get("metadata", {}),
        }
        trace = ExecutionTrace.from_dict(state)
        return calculate_metrics(trace)
    except Exception:
        logger.exception("Failed to calculate metrics")
        return None


def _save_trace_state(trace_state: dict[str, Any]) -> None:
    try:
        trace = ExecutionTrace.from_dict(trace_state)
        storage.save_trace(trace)
    except Exception:
        logger.exception("Failed to save trace")


# Global connection manager
manager = ConnectionManager()
storage = TraceStorage()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Treehouse Visualizer starting...")
    yield
    logger.info("Treehouse Visualizer shutting down...")


app = FastAPI(
    title="Treehouse Visualizer",
    description="Real-time behavior tree visualization",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "viewers": len(manager.viewers),
        "agents": len(manager.agents),
    }


@app.get("/api/traces")
async def list_traces(limit: int = 50, offset: int = 0):
    """List stored traces."""
    return {
        "traces": storage.list_traces(limit=limit, offset=offset),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a stored trace by ID."""
    trace = storage.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace.to_dict()


@app.get("/api/traces/{trace_id}/export")
async def export_trace(trace_id: str):
    """Export a stored trace as JSON."""
    trace = storage.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return Response(content=trace.to_json(), media_type="application/json")


@app.post("/api/traces")
async def save_trace(payload: dict = TRACE_PAYLOAD):
    """Save a trace from a JSON payload."""
    try:
        trace = ExecutionTrace.from_dict(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid trace payload: {exc}"
        ) from exc

    storage.save_trace(trace)
    return {"status": "saved", "trace_id": trace.trace_id}


@app.post("/api/traces/import")
async def import_trace(payload: dict = TRACE_PAYLOAD):
    """Import a trace from JSON payload."""
    try:
        trace = ExecutionTrace.from_dict(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid trace payload: {exc}"
        ) from exc

    storage.save_trace(trace)
    return {"status": "imported", "trace_id": trace.trace_id}


@app.delete("/api/traces/{trace_id}")
async def delete_trace(trace_id: str):
    """Delete a stored trace."""
    deleted = storage.delete_trace(trace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"status": "deleted", "trace_id": trace_id}


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main visualizer page."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>Treehouse Visualizer</title>
    <style>
        body { font-family: system-ui, sans-serif; padding: 20px; }
        .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
        .connected { background: #dcfce7; color: #166534; }
        .disconnected { background: #fee2e2; color: #991b1b; }
    </style>
</head>
<body>
    <h1>Treehouse Visualizer</h1>
    <div id="status" class="status disconnected">Connecting...</div>
    <p>Static files not found. Run from the visualizer directory.</p>
</body>
</html>
    """)


@app.websocket("/ws/viewer")
async def viewer_websocket(websocket: WebSocket):
    """WebSocket endpoint for browser viewers."""
    await manager.connect_viewer(websocket)
    try:
        while True:
            # Viewers can send debugger commands
            data = await websocket.receive_text()
            message = json.loads(data)
            logger.info(f"📨 Viewer sent: {message}")

            # Forward debugger commands to agents
            if message.get("type") in [
                "pause",
                "resume",
                "step",
                "set_breakpoint",
                "clear_breakpoint",
                "clear_all_breakpoints",
            ]:
                logger.info(f"🔀 Forwarding command '{message.get('type')}' to agents")
                await manager.broadcast_to_agents(
                    message, agent_id=message.get("agent_id")
                )
    except WebSocketDisconnect:
        manager.disconnect_viewer(websocket)
    except Exception as e:
        logger.error(f"Viewer error: {e}")
        manager.disconnect_viewer(websocket)


@app.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    """WebSocket endpoint for agents sending events."""
    agent_id = await manager.connect_agent(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            logger.info(
                f"📥 Server received from agent: {event.get('type', 'unknown')}"
            )
            await manager.handle_agent_event(agent_id, event)
    except WebSocketDisconnect:
        logger.info("Agent disconnected")
        manager.disconnect_agent(websocket)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        manager.disconnect_agent(websocket)


# Mount static files if directory exists
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
