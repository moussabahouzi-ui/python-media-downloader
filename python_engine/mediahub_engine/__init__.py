"""MediaHub embedded media-processing engine.

The entire engine runs as a child process of the Android foreground service
and communicates over line-delimited JSON-RPC on stdio. See
``docs/BRIDGE_CONTRACT.md`` for the authoritative wire format.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
