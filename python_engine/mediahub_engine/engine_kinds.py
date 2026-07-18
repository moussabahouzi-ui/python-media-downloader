"""Leaf-level engine kind definitions.

This module has **zero internal imports** so it can be imported from anywhere
without risking a cycle. It defines the [EngineStrategy] enum and the
[EngineDecision] dataclass; the [pick_engine] helper lives in
[mediahub_engine.download.strategy] because it needs the [Capability] type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EngineStrategy(StrEnum):
    """Concrete extraction backends."""

    YTDLP = "yt-dlp"
    GALLERY_DL = "gallery-dl"
    INSTALOADER = "instaloader"
    FFMPEG = "ffmpeg"
    HTTP = "http"


@dataclass(frozen=True)
class EngineDecision:
    """The chosen [EngineStrategy] for a capability, with a display label."""

    strategy: EngineStrategy
    engine_label: str


__all__ = ["EngineDecision", "EngineStrategy"]
