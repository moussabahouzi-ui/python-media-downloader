"""FFmpeg-backed media processing (merge, convert, extract, embed).

Reserved for Phase 3. Phase 1 ships no media-processing handlers; the
namespace exists so providers can ``from mediahub_engine.media import ...``
once the FFmpeg wrappers land without restructuring.
"""

__all__: list[str] = []
