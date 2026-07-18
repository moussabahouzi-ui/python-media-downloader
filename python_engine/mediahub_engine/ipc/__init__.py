"""IPC subpackage — line-delimited JSON-RPC 2.0 over stdio."""

from mediahub_engine.ipc.jsonrpc import RpcDispatcher, RpcError, read_messages, write_message

__all__ = ["RpcDispatcher", "RpcError", "read_messages", "write_message"]
