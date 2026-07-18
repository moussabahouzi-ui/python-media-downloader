"""Tests for the JSON-RPC framing + dispatcher."""

from __future__ import annotations

import io
import json

import pytest

from mediahub_engine.contracts import EngineError, JsonRpcRequest
from mediahub_engine.ipc.jsonrpc import (
    RpcDispatcher,
    RpcError,
    read_messages,
    write_message,
)


@pytest.mark.asyncio
async def test_dispatcher_returns_result_for_known_method(dispatcher: RpcDispatcher) -> None:
    async def handler(params: dict) -> dict:
        return {"echo": params["value"]}

    dispatcher.register("test.echo", handler)
    request = JsonRpcRequest(jsonrpc="2.0", id=7, method="test.echo", params={"value": 42})
    response = await dispatcher.dispatch(request)
    assert response is not None
    assert response.id == 7
    assert response.result == {"echo": 42}
    assert response.error is None


@pytest.mark.asyncio
async def test_dispatcher_unknown_method_returns_error(dispatcher: RpcDispatcher) -> None:
    request = JsonRpcRequest(jsonrpc="2.0", id=1, method="nope", params={})
    response = await dispatcher.dispatch(request)
    assert response is not None
    assert response.error is not None
    assert response.error.code == EngineError.UNKNOWN_METHOD


@pytest.mark.asyncio
async def test_dispatcher_propagates_rpc_error(dispatcher: RpcDispatcher) -> None:
    async def handler(params: dict) -> dict:
        raise RpcError(EngineError.INVALID_PARAMS, "bad input", {"k": "v"})

    dispatcher.register("test.bad", handler)
    request = JsonRpcRequest(jsonrpc="2.0", id=3, method="test.bad")
    response = await dispatcher.dispatch(request)
    assert response is not None
    assert response.error is not None
    assert response.error.code == EngineError.INVALID_PARAMS
    assert response.error.data == {"k": "v"}


@pytest.mark.asyncio
async def test_dispatcher_wraps_unexpected_exception(dispatcher: RpcDispatcher) -> None:
    async def handler(params: dict) -> dict:
        raise RuntimeError("boom")

    dispatcher.register("test.crash", handler)
    request = JsonRpcRequest(jsonrpc="2.0", id=4, method="test.crash")
    response = await dispatcher.dispatch(request)
    assert response is not None
    assert response.error is not None
    assert response.error.code == EngineError.INTERNAL


@pytest.mark.asyncio
async def test_notification_has_no_response(dispatcher: RpcDispatcher) -> None:
    called: list[bool] = []

    async def handler(params: dict) -> dict:
        called.append(True)
        return {}

    dispatcher.register("test.notify", handler)
    request = JsonRpcRequest(jsonrpc="2.0", id=None, method="test.notify")
    response = await dispatcher.dispatch(request)
    assert response is None
    assert called == [True]


def test_read_messages_parses_lines() -> None:
    raw = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"a","params":{}}\n'
        "\n"
        '{"jsonrpc":"2.0","id":2,"method":"b","params":{"x":1}}\n'
        "not-json\n"
    )
    messages = list(read_messages(raw))
    assert [m.method for m in messages] == ["a", "b"]
    assert messages[1].params == {"x": 1}


def test_write_message_emits_single_compact_line(stdout_buffer: io.StringIO) -> None:
    write_message(
        stdout_buffer,
        {"jsonrpc": "2.0", "id": 1, "result": {"pong": True, "version": "0.1.0"}},
    )
    out = stdout_buffer.getvalue()
    # Exactly one newline, no embedded newlines.
    assert out.count("\n") == 1
    parsed = json.loads(out.strip())
    assert parsed["result"]["pong"] is True


def test_write_message_excludes_none_fields(stdout_buffer: io.StringIO) -> None:
    from mediahub_engine.contracts import JsonRpcResponse

    write_message(stdout_buffer, JsonRpcResponse(id=1, result={"ok": True}))
    parsed = json.loads(stdout_buffer.getvalue().strip())
    assert "error" not in parsed
    assert parsed["result"] == {"ok": True}


def test_emit_notification_uses_sink(
    dispatcher: RpcDispatcher,
    captured_notifications: tuple[list, callable],
) -> None:
    events, sink = captured_notifications
    dispatcher.set_notification_sink(sink)
    dispatcher.emit_notification("download.progress", {"percent": 50.0})
    assert events == [("download.progress", {"percent": 50.0})]
