"""Module entry point: ``python -m mediahub_engine``.

Bridges the synchronous ``__main__`` contract to the async [Engine.run].
"""

from __future__ import annotations

import sys

from mediahub_engine.engine import main

if __name__ == "__main__":
    sys.exit(main())
