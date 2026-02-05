from __future__ import annotations

import asyncio
import builtins
import json
import sys
from types import SimpleNamespace

import pytest

from treehouse.debugger import DebuggerClient


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True


class FailingWebSocket(FakeWebSocket):
    async def send(self, data: str) -> None:
        raise RuntimeError("send failed")


@pytest.mark.asyncio
async def test_connect_flushes_queue(monkeypatch):
    fake_ws = FakeWebSocket()

    async def fake_connect(url):
        return fake_ws

    monkeypatch.setitem(
        __import__("sys").modules,
        "websockets",
        SimpleNamespace(connect=fake_connect),
    )

    client = DebuggerClient(url="ws://example")
    client._send_queue.append({"type": "queued"})

    connected = await client.connect()
    assert connected is True
    assert client.connected is True
    assert client._send_queue == []

    sent = json.loads(fake_ws.sent[0])
    assert sent["type"] == "queued"


@pytest.mark.asyncio
async def test_connect_import_error(monkeypatch):
    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "websockets":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    monkeypatch.setattr(builtins, "__import__", fake_import)

    client = DebuggerClient()
    connected = await client.connect()
    assert connected is False


@pytest.mark.asyncio
async def test_connect_failure(monkeypatch):
    async def fake_connect(_):
        raise RuntimeError("boom")

    monkeypatch.setitem(
        __import__("sys").modules,
        "websockets",
        SimpleNamespace(connect=fake_connect),
    )

    client = DebuggerClient()
    connected = await client.connect()
    assert connected is False
    assert client.connected is False


@pytest.mark.asyncio
async def test_send_queues_when_disconnected(monkeypatch):
    client = DebuggerClient(auto_reconnect=True, reconnect_delay=0)

    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    result = await client._send({"type": "event"})
    assert result is False
    assert client._send_queue[0]["type"] == "event"


@pytest.mark.asyncio
async def test_send_success(monkeypatch):
    client = DebuggerClient()
    client._connected = True
    client._ws = FakeWebSocket()

    sent = await client._send({"type": "ok"})
    assert sent is True
    assert json.loads(client._ws.sent[0])["type"] == "ok"


@pytest.mark.asyncio
async def test_send_failure_queues_and_reconnect(monkeypatch):
    client = DebuggerClient(auto_reconnect=True, reconnect_delay=0)
    client._connected = True
    client._ws = FailingWebSocket()

    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    sent = await client._send({"type": "fail"})
    assert sent is False
    assert client.connected is False
    assert client._send_queue[0]["type"] == "fail"


@pytest.mark.asyncio
async def test_disconnect_closes_socket():
    client = DebuggerClient()
    client._connected = True
    client._ws = FakeWebSocket()

    await client.disconnect()
    assert client.connected is False
    assert client._ws is None


@pytest.mark.asyncio
async def test_try_reconnect_skips_when_connecting(monkeypatch):
    client = DebuggerClient()
    client._connecting = True

    async def fake_connect():
        raise AssertionError("connect should not be called")

    monkeypatch.setattr(client, "connect", fake_connect)
    await client._try_reconnect()


def test_send_sync_queues_when_no_connection():
    client = DebuggerClient()
    client.send_sync({"type": "sync"})
    assert client._send_queue[0]["type"] == "sync"


@pytest.mark.asyncio
async def test_send_trace_events(monkeypatch):
    client = DebuggerClient()
    sent = []

    async def fake_send(event):
        sent.append(event)
        return True

    monkeypatch.setattr(client, "_send", fake_send)

    await client.send_trace_start(trace_id="t1", tick_id=2)
    await client.send_node_execution({"node_id": "n1"})
    await client.send_trace_complete(status="success")

    types = [item["type"] for item in sent]
    assert types == ["trace_start", "node_execution", "trace_complete"]


@pytest.mark.asyncio
async def test_send_sync_uses_running_loop(monkeypatch):
    client = DebuggerClient()
    client._connected = True
    client._ws = FakeWebSocket()

    sent = []

    async def fake_send(event):
        sent.append(event)
        return True

    monkeypatch.setattr(client, "_send", fake_send)

    client.send_sync({"type": "loop"})
    await asyncio.sleep(0)

    assert sent[0]["type"] == "loop"


def test_send_sync_runs_in_event_loop(monkeypatch):
    client = DebuggerClient()
    client._connected = True
    client._ws = FakeWebSocket()

    class DummyLoop:
        def __init__(self) -> None:
            self.ran = False

        def is_running(self):
            return False

        def run_until_complete(self, _coro):
            self.ran = True

    dummy_loop = DummyLoop()

    async def fake_send(event):
        return True

    monkeypatch.setattr(client, "_send", fake_send)
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: dummy_loop)

    client.send_sync({"type": "block"})
    assert dummy_loop.ran is True


@pytest.mark.asyncio
async def test_send_trace_start_includes_timestamp(monkeypatch):
    client = DebuggerClient()
    sent = []

    async def fake_send(event):
        sent.append(event)
        return True

    monkeypatch.setattr(client, "_send", fake_send)

    await client.send_trace_start(trace_id="t2", tick_id=1)
    assert "timestamp" in sent[0]


@pytest.mark.asyncio
async def test_connect_already_connected():
    """connect() should return early if already connected."""
    client = DebuggerClient()
    client._connected = True

    # Should return True without trying to connect again
    result = await client.connect()
    assert result is True


@pytest.mark.asyncio
async def test_disconnect_handles_exception():
    """disconnect() should handle exceptions when closing websocket."""
    client = DebuggerClient()

    class FakeWS:
        async def close(self):
            raise RuntimeError("close failed")

    client._ws = FakeWS()
    client._connected = True

    # Should not raise, just log and mark as disconnected
    await client.disconnect()
    assert client._connected is False
    assert client._ws is None


@pytest.mark.asyncio
async def test_context_manager():
    """DebuggerClient should work as async context manager."""
    client = DebuggerClient()

    async def fake_connect():
        client._connected = True
        return True

    async def fake_disconnect():
        client._connected = False

    client.connect = fake_connect
    client.disconnect = fake_disconnect

    async with client as ctx:
        assert ctx is client
        assert client._connected is True

    assert client._connected is False


@pytest.mark.asyncio
async def test_try_reconnect_with_delay(monkeypatch):
    """_try_reconnect should wait and call connect."""
    client = DebuggerClient(reconnect_delay=0.01)
    client._connecting = False

    connect_called = []

    async def fake_connect():
        connect_called.append(True)
        return True

    monkeypatch.setattr(client, "connect", fake_connect)

    await client._try_reconnect()
    assert len(connect_called) == 1


def test_send_sync_with_runtime_error(monkeypatch):
    """send_sync should queue event when RuntimeError occurs."""
    client = DebuggerClient()
    client._connected = True
    client._ws = object()

    def raise_runtime_error():
        raise RuntimeError("no event loop")

    monkeypatch.setattr(asyncio, "get_event_loop", raise_runtime_error)

    client.send_sync({"type": "test"})
    assert len(client._send_queue) == 1
    assert client._send_queue[0]["type"] == "test"


class MockCommandHandler:
    """Mock command handler for testing."""

    def __init__(self):
        self.commands = []

    def handle_command(self, command, data):
        self.commands.append((command, data))


class FakeWebSocketWithReceive(FakeWebSocket):
    """WebSocket that can receive messages."""

    def __init__(self):
        super().__init__()
        self.messages_to_receive = []
        self.receive_index = 0

    async def recv(self):
        if self.receive_index < len(self.messages_to_receive):
            msg = self.messages_to_receive[self.receive_index]
            self.receive_index += 1
            return msg
        # Block forever to simulate waiting for messages
        await asyncio.sleep(999)


@pytest.mark.asyncio
async def test_receive_loop_handles_commands(monkeypatch):
    """Test that receive loop processes incoming commands."""
    fake_ws = FakeWebSocketWithReceive()
    fake_ws.messages_to_receive = [
        json.dumps({"type": "pause", "data": {}}),
        json.dumps({"type": "resume", "data": {}}),
    ]

    async def fake_connect(url):
        return fake_ws

    monkeypatch.setitem(
        sys.modules,
        "websockets",
        SimpleNamespace(connect=fake_connect),
    )

    handler = MockCommandHandler()
    client = DebuggerClient(url="ws://example", command_handler=handler)

    await client.connect()
    assert client._receive_task is not None

    # Give receive loop time to process messages
    await asyncio.sleep(0.05)

    # Should have processed both commands
    assert len(handler.commands) == 2
    assert handler.commands[0] == ("pause", {})
    assert handler.commands[1] == ("resume", {})

    await client.disconnect()


@pytest.mark.asyncio
async def test_receive_loop_handles_command_errors(monkeypatch):
    """Test that receive loop continues after command handler errors."""
    fake_ws = FakeWebSocketWithReceive()

    # First command will fail, second should still process
    fake_ws.messages_to_receive = [
        json.dumps({"type": "bad_command", "data": {}}),
        json.dumps({"type": "good_command", "data": {}}),
    ]

    async def fake_connect(url):
        return fake_ws

    monkeypatch.setitem(
        sys.modules,
        "websockets",
        SimpleNamespace(connect=fake_connect),
    )

    class FailingHandler:
        def __init__(self):
            self.commands = []

        def handle_command(self, command, data):
            if command == "bad_command":
                raise ValueError("bad command")
            self.commands.append((command, data))

    handler = FailingHandler()
    client = DebuggerClient(url="ws://example", command_handler=handler)

    await client.connect()

    # Give receive loop time to process
    await asyncio.sleep(0.05)

    # Should have processed the good command despite the error
    assert len(handler.commands) == 1
    assert handler.commands[0] == ("good_command", {})

    await client.disconnect()


@pytest.mark.asyncio
async def test_receive_loop_stops_on_disconnect(monkeypatch):
    """Test that receive loop stops when disconnected."""
    fake_ws = FakeWebSocketWithReceive()

    async def fake_connect(url):
        return fake_ws

    monkeypatch.setitem(
        sys.modules,
        "websockets",
        SimpleNamespace(connect=fake_connect),
    )

    handler = MockCommandHandler()
    client = DebuggerClient(url="ws://example", command_handler=handler)

    await client.connect()
    assert client._receive_task is not None
    task = client._receive_task

    # Disconnect should cancel the receive task
    await client.disconnect()

    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_receive_loop_no_start_without_handler(monkeypatch):
    """Test that receive loop doesn't start without command handler."""
    fake_ws = FakeWebSocket()

    async def fake_connect(url):
        return fake_ws

    monkeypatch.setitem(
        sys.modules,
        "websockets",
        SimpleNamespace(connect=fake_connect),
    )

    # No command handler provided
    client = DebuggerClient(url="ws://example")

    await client.connect()

    # Should not have started receive task
    assert client._receive_task is None

    await client.disconnect()


class FakeWebSocketWithError(FakeWebSocket):
    """WebSocket that raises errors on recv."""

    async def recv(self):
        raise RuntimeError("recv error")


@pytest.mark.asyncio
async def test_receive_loop_handles_recv_errors(monkeypatch):
    """Test that receive loop handles recv errors gracefully."""
    fake_ws = FakeWebSocketWithError()

    async def fake_connect(url):
        return fake_ws

    monkeypatch.setitem(
        sys.modules,
        "websockets",
        SimpleNamespace(connect=fake_connect),
    )

    handler = MockCommandHandler()
    client = DebuggerClient(url="ws://example", command_handler=handler)

    await client.connect()

    # Give receive loop time to encounter error
    await asyncio.sleep(0.05)

    # Should have marked as disconnected
    assert not client.connected

    await client.disconnect()
