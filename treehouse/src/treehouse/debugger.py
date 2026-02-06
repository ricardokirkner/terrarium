"""Debugger client for streaming behavior tree events to the visualizer.

This module provides DebuggerClient, which connects to the Treehouse
Visualizer server and streams execution events in real-time.

Usage:
    async with DebuggerClient() as client:
        collector = TraceCollector(debugger=client)
        tree = BehaviorTree(root=my_tree, emitter=collector)
        collector.set_state(state)
        tree.tick(state)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DebuggerClient:
    """WebSocket client for streaming events to the Treehouse Visualizer.

    Connects to the visualizer server's agent endpoint and sends
    execution events as the behavior tree runs.

    Example:
        async with DebuggerClient("ws://localhost:8000/ws/agent") as client:
            await client.send_trace_start(trace_id="abc", tick_id=1)
            await client.send_node_execution(node_data)
            await client.send_trace_complete(status="success")

    Attributes:
        url: WebSocket URL of the visualizer server.
        connected: Whether currently connected to the server.
    """

    def __init__(
        self,
        url: str = "ws://localhost:8000/ws/agent",
        auto_reconnect: bool = True,
        reconnect_delay: float = 2.0,
        command_handler: Any = None,
    ):
        """Initialize the debugger client.

        Args:
            url: WebSocket URL of the visualizer server.
            auto_reconnect: Whether to automatically reconnect on disconnect.
            reconnect_delay: Seconds to wait before reconnecting.
            command_handler: Optional handler for incoming debugger commands.
                           Should have a handle_command(command, data) method.
        """
        self.url = url
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self.command_handler = command_handler
        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._connected = False
        self._connecting = False
        self._send_queue: list[dict[str, Any]] = []
        self._receive_task: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None  # Store event loop ref

    @property
    def connected(self) -> bool:
        """Return True if connected to the server."""
        return self._connected

    async def connect(self) -> bool:
        """Connect to the visualizer server.

        Returns:
            True if connection succeeded, False otherwise.
        """
        if self._connected or self._connecting:
            return self._connected

        self._connecting = True
        try:
            import websockets

            self._ws = await websockets.connect(self.url)
            self._connected = True
            self._loop = asyncio.get_running_loop()  # Store event loop reference
            logger.info(f"Connected to visualizer at {self.url}")

            # Send any queued events
            while self._send_queue:
                event = self._send_queue.pop(0)
                await self._send(event)

            # Start receive loop if command handler is set
            if self.command_handler:
                self._receive_task = asyncio.create_task(self._receive_loop())

            return True
        except ImportError:
            logger.error(
                "websockets package not installed. Install with: pip install websockets"
            )
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to visualizer: {e}")
            self._connected = False
            return False
        finally:
            self._connecting = False

    async def disconnect(self) -> None:
        """Disconnect from the visualizer server."""
        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected = False
        logger.info("Disconnected from visualizer")

    async def _receive_loop(self) -> None:
        """Background task to receive messages from the server."""
        logger.info("🔄 Receive loop started")
        try:
            while self._connected and self._ws:
                try:
                    message = await self._ws.recv()
                    data = json.loads(message)
                    logger.info(f"📥 Agent received from server: {data}")

                    # Handle incoming commands
                    if data.get("type") and self.command_handler:
                        command = data.get("type")
                        payload = data.get("data", {})
                        logger.info(
                            f"🎯 Processing command: {command} with payload: {payload}"
                        )

                        try:
                            self.command_handler.handle_command(command, payload)
                            logger.info(f"✅ Command {command} handled successfully")
                        except Exception as e:
                            logger.error(f"❌ Error handling command {command}: {e}")

                except Exception as e:
                    if self._connected:
                        logger.warning(f"⚠️ Error in receive loop: {e}")
                        break
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
        finally:
            if self._connected:
                self._connected = False

    async def __aenter__(self) -> DebuggerClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def _send(self, event: dict[str, Any]) -> bool:
        """Send an event to the server.

        Args:
            event: Event dictionary to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._connected or not self._ws:
            if self.auto_reconnect:
                self._send_queue.append(event)
                # Try to reconnect in background
                asyncio.create_task(self._try_reconnect())
            return False

        try:
            await self._ws.send(json.dumps(event))
            return True
        except Exception as e:
            logger.warning(f"Failed to send event: {e}")
            self._connected = False
            if self.auto_reconnect:
                self._send_queue.append(event)
                asyncio.create_task(self._try_reconnect())
            return False

    async def _try_reconnect(self) -> None:
        """Try to reconnect after a delay."""
        if self._connecting:
            return
        await asyncio.sleep(self.reconnect_delay)
        await self.connect()

    def send_sync(self, event: dict[str, Any]) -> None:
        """Send an event synchronously (for non-async contexts).

        If connected and event loop is available, schedules the send to run
        in the event loop thread-safely. Otherwise queues the event.

        Args:
            event: Event dictionary to send.
        """
        if self._connected and self._ws and self._loop:
            try:
                # Use run_coroutine_threadsafe for thread-safe scheduling
                # This works even when called from worker threads
                asyncio.run_coroutine_threadsafe(self._send(event), self._loop)
            except Exception as e:
                logger.warning(f"Failed to schedule send: {e}")
                self._send_queue.append(event)
        else:
            self._send_queue.append(event)

    async def send_trace_start(
        self,
        trace_id: str,
        tick_id: int,
        timestamp: datetime | None = None,
    ) -> None:
        """Send a trace start event.

        Args:
            trace_id: Unique trace identifier.
            tick_id: Tick number.
            timestamp: When the trace started (defaults to now).
        """
        await self._send(
            {
                "type": "trace_start",
                "trace_id": trace_id,
                "tick_id": tick_id,
                "timestamp": (timestamp or datetime.now()).isoformat(),
            }
        )

    async def send_node_execution(self, node_data: dict[str, Any]) -> None:
        """Send a node execution event.

        Args:
            node_data: Node execution data (from NodeExecution.to_dict()).
        """
        await self._send(
            {
                "type": "node_execution",
                "data": node_data,
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def send_trace_complete(
        self,
        status: str,
        timestamp: datetime | None = None,
    ) -> None:
        """Send a trace complete event.

        Args:
            status: Final trace status (success/failure/running).
            timestamp: When the trace completed (defaults to now).
        """
        await self._send(
            {
                "type": "trace_complete",
                "status": status,
                "timestamp": (timestamp or datetime.now()).isoformat(),
            }
        )
