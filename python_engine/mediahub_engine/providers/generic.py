"""The fallback generic provider.

The generic provider handles direct media URLs (mp4, mp3, images, etc.) that
no specialized provider claims. It performs a plain HTTP GET with streaming
and progress reporting. It deliberately has no third-party dependency so the
engine always has a working fallback.
"""

from __future__ import annotations

import os
import urllib.request
from typing import Any
from urllib.error import URLError

from mediahub_engine.providers.base import (
    Capability,
    DownloadSink,
    MediaMetadata,
    Provider,
    ProviderError,
    ProviderFeature,
    ProviderResult,
)
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)

_DIRECT_MEDIA_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".mp3",
    ".aac",
    ".m4a",
    ".flac",
    ".ogg",
    ".wav",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
)

_CHUNK_SIZE = 64 * 1024


class GenericProvider(Provider):
    """Downloads direct media URLs over plain HTTP(S)."""

    capability = Capability(
        name="generic",
        engine="http",
        url_patterns=("http://", "https://", "file://"),
        features=ProviderFeature.SINGLE | ProviderFeature.RESUMABLE,
        auth_required=False,
        max_batch=1,
    )

    def matches(self, url: str) -> bool:
        # The generic provider only claims direct media URLs; specialized
        # providers run first (see registry ordering) and grab platform URLs.
        if not url.lower().startswith(("http://", "https://", "file://")):
            return False
        lowered = url.split("?", 1)[0].lower()
        return lowered.endswith(_DIRECT_MEDIA_EXTENSIONS)

    async def extract_metadata(self, url: str) -> MediaMetadata:
        # Best-effort: derive a title from the URL path.
        name = os.path.basename(url.split("?", 1)[0]) or "media"
        return MediaMetadata(title=name, extra={"url": url})

    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ProviderResult:
        options = options or {}
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as exc:
            raise ProviderError(
                f"Cannot create destination directory: {exc}",
                code="STORAGE",
                details={"dir": dest_dir},
            ) from exc

        filename = (
            options.get("filename")
            or os.path.basename(
                url.split("?", 1)[0],
            )
            or f"mediahub-{task_id}"
        )
        output_path = os.path.join(dest_dir, filename)

        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                total = int(response.headers.get("Content-Length", "0") or 0) or None
                bytes_done = 0
                with open(output_path, "wb") as fh:
                    while True:
                        chunk = response.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        fh.write(chunk)
                        bytes_done += len(chunk)
                        percent = (bytes_done / total * 100.0) if total else 0.0
                        if sink is not None:
                            sink.on_progress(
                                task_id=task_id,
                                percent=percent,
                                bytes_done=bytes_done,
                                total_bytes=total,
                            )
        except URLError as exc:
            raise ProviderError(
                f"Download failed: {exc.reason}",
                code="NETWORK",
                details={"url": url},
            ) from exc
        except OSError as exc:
            raise ProviderError(
                f"File write failed: {exc}",
                code="STORAGE",
                details={"path": output_path},
            ) from exc

        log.info("generic provider downloaded %s -> %s", url, output_path)
        return ProviderResult(
            output_paths=[output_path],
            bytes_written=os.path.getsize(output_path),
            metadata=await self.extract_metadata(url),
        )


__all__ = ["GenericProvider"]
