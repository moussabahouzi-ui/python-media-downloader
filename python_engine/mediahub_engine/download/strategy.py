"""Engine-selection strategy.

Maps a provider's declared preferred engine to a concrete [EngineStrategy].
Centralizing this in one place keeps provider implementations thin and makes
it trivial to add new backends.

The [EngineStrategy] enum and [EngineDecision] dataclass live in the leaf
module [mediahub_engine.engine_kinds] to avoid import cycles (backends need
the enum but not the [Capability] type this module imports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mediahub_engine.engine_kinds import EngineDecision, EngineStrategy
from mediahub_engine.utils.logging import get_logger

if TYPE_CHECKING:
    from mediahub_engine.providers.base import Capability

log = get_logger(__name__)


def pick_engine(capability: Capability) -> EngineDecision:
    """Maps a capability's preferred engine to an [EngineDecision]."""
    raw = capability.engine.strip().lower()
    try:
        strategy = EngineStrategy(raw)
    except ValueError:
        log.warning(
            "Unknown engine %r for %s; falling back to HTTP",
            raw,
            capability.name,
        )
        strategy = EngineStrategy.HTTP
    return EngineDecision(strategy=strategy, engine_label=strategy.value)


__all__ = ["EngineDecision", "EngineStrategy", "pick_engine"]
