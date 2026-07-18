"""Engine-strategy re-export for the providers package.

Delegates to [mediahub_engine.engine_kinds] (leaf module) and
[mediahub_engine.download.strategy] (pick_engine helper) so providers can
import everything from one place without depending on download internals.
"""

from mediahub_engine.download.strategy import pick_engine
from mediahub_engine.engine_kinds import EngineDecision, EngineStrategy

__all__ = ["EngineDecision", "EngineStrategy", "pick_engine"]
