"""Line-delimited JSON-RPC 2.0 framing and dispatch.

Protocol (see ``docs/BRIDGE_CONTRACT.md`` §2):

- One JSON object per line, UTF-8, terminated by ``\\n``.
- Requests carry an ``id``; the engine MUST reply with the same ``id``.
- Notifications have no ``id``; the engine MUST NOT reply.
- stdout is reserved for JSON-RPC; logs go to stderr.

The dispatcher is fully synchronous on the read side (one line at a time) and
delegates handler execution to the asyncio loop owned by the engine. This keeps
framing dead simple and easy to test.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterator
from typing import Any, Final

from mediahub_engine.contracts import (
    EngineError,
    JsonRpcErrorData,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
)
from mediahub_engine.utils.logging import get_logger

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover — pydantic is a hard dep at runtime.
    BaseModel = None  # type: ignore[assignment]

log = get_logger(__name__)

#: Type of an async handler: takes params, returns a result dict.
Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

#: Type of a notification sink.
NotificationSink = Callable[[str, dict[str, Any]], None]


class RpcError(Exception):
    """Raised by handlers to produce a structured JSON-RPC error."""

    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class RpcDispatcher:
    """Routes JSON-RPC requests to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}
        self._notification_sink: NotificationSink | None = None

    def register(self, method: str, handler: Handler) -> None:
        if method in self._handlers:
            raise ValueError(f"Method already registered: {method}")
        self._handlers[method] = handler

    def set_notification_sink(self, sink: NotificationSink) -> None:
        self._notification_sink = sink

    @property
    def methods(self) -> tuple[str, ...]:
        return tuple(self._handlers.keys())

    async def dispatch(self, request: JsonRpcRequest) -> JsonRpcResponse | None:
        """Dispatches one request; returns a response or ``None`` for notifications."""
        if request.id is None:
            # Notification — fire and forget, no response.
            handler = self._handlers.get(request.method)
            if handler is None:
                log.warning("Unknown notification method: %s", request.method)
                return None
            try:
                await handler(request.params)
            except Exception:
                log.exception("Notification handler failed: %s", request.method)
            return None

        handler = self._handlers.get(request.method)
        if handler is None:
            return _error_response(
                request.id,
                EngineError.UNKNOWN_METHOD,
                f"Unknown method: {request.method}",
                {"method": request.method},
            )

        try:
            result = await handler(request.params)
        except RpcError as exc:
            return _error_response(request.id, exc.code, exc.message, exc.data)
        except Exception as exc:
            log.exception("Handler crashed: %s", request.method)
            return _error_response(
                request.id,
                EngineError.INTERNAL,
                "Internal error",
                {"detail": str(exc)},
            )

        return JsonRpcResponse(id=request.id, result=result)

    def emit_notification(self, method: str, params: dict[str, Any]) -> None:
        """Sends a notification to the host via the configured sink."""
        if self._notification_sink is None:
            log.debug("No notification sink; dropping %s", method)
            return
        self._notification_sink(method, params)


# ---------------------------------------------------------------------------
# Framing helpers (stdin/stdout)
# ---------------------------------------------------------------------------


def read_messages(stream: Any) -> Iterator[JsonRpcRequest]:
    """Yields parsed [JsonRpcRequest] objects, one per non-blank line."""
    for line in stream:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            log.warning("Malformed JSON-RPC line: %s (%s)", text[:120], exc)
            continue
        try:
            yield JsonRpcRequest.model_validate(payload)
        except Exception as exc:
            log.warning("Invalid JSON-RPC payload: %s (%s)", payload, exc)


def write_message(stream: Any, message: Any) -> None:
    """Serializes ``message`` to compact JSON and writes it as one line."""
    payload: Final[str] = _serialize(message)
    stream.write(payload + "\n")
    stream.flush()


def _serialize(message: Any) -> str:
    if isinstance(message, (JsonRpcResponse, JsonRpcNotification, JsonRpcRequest)) or (
        BaseModel is not None and isinstance(message, BaseModel)
    ):
        data = message.model_dump(by_alias=True, exclude_none=True)
    else:
        data = message
    # Compact, no embedded newlines — critical for line framing.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _error_response(
    request_id: int | str,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> JsonRpcResponse:
    return JsonRpcResponse(
        id=request_id,
        error=JsonRpcErrorData(code=code, message=message, data=data),
    )


__all__ = [
    "Handler",
    "NotificationSink",
    "RpcDispatcher",
    "RpcError",
    "read_messages",
    "write_message",
]
