"""Pydantic models for the JSON-RPC request/response payload surface.

These models are the *Python-side mirror* of the bridge contract documented in
``docs/BRIDGE_CONTRACT.md``. Only the Phase 1 method surface is modelled here;
later phases extend ``METHOD_PARAMS`` and ``METHOD_RESULTS``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Generic JSON-RPC envelope
# ---------------------------------------------------------------------------


class JsonRpcRequest(BaseModel):
    """A single JSON-RPC 2.0 request."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: int | str | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcErrorData(BaseModel):
    """JSON-RPC error object."""

    model_config = ConfigDict(extra="allow")

    code: int
    message: str
    data: dict[str, Any] | None = None


class JsonRpcResponse(BaseModel):
    """A JSON-RPC 2.0 response (success or error)."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None = None
    result: dict[str, Any] | None = None
    error: JsonRpcErrorData | None = None


class JsonRpcNotification(BaseModel):
    """A JSON-RPC notification (no id, no response expected)."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 1 method payloads
# ---------------------------------------------------------------------------


class EnginePingResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    pong: bool = True
    version: str


class EngineVersionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    app: str
    engine: str
    bridge_version: int = Field(alias="bridgeVersion")


class EngineShutdownResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    stopped: bool = True


# ---------------------------------------------------------------------------
# Application error codes (mirror docs/BRIDGE_CONTRACT.md §2.5)
# ---------------------------------------------------------------------------


class EngineError:
    """Application-level JSON-RPC error codes."""

    UNKNOWN_METHOD = -1
    INVALID_PARAMS = -2
    PROVIDER_NOT_FOUND = -3
    ENGINE_TIMEOUT = -4
    INTERNAL = -5


__all__ = [
    "EngineError",
    "EnginePingResult",
    "EngineShutdownResult",
    "EngineVersionResult",
    "JsonRpcErrorData",
    "JsonRpcNotification",
    "JsonRpcRequest",
    "JsonRpcResponse",
]
