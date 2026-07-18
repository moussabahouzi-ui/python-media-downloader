"""Instaloader backend.

Instaloader targets Instagram (posts, reels, stories, profiles). It is
synchronous and auth-gated for most operations; this backend lazy-imports the
library and threads credential injection through its options.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
from typing import Any

from mediahub_engine.engine_kinds import EngineStrategy
from mediahub_engine.providers.backends.base import (
    BackendNotAvailableError,
    ExtractionBackend,
    ExtractionResult,
    FormatOption,
)
from mediahub_engine.providers.base import DownloadSink, MediaMetadata, ProviderError
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class InstaloaderBackend(ExtractionBackend):
    """Wraps `instaloader.Instaloader`."""

    strategy = EngineStrategy.INSTALOADER

    def __init__(self, max_workers: int = 1) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="instaloader",
        )
        self._module: Any | None = None

    def is_available(self) -> bool:
        return self._import_module() is not None

    def _import_module(self) -> Any | None:
        if self._module is not None:
            return self._module
        try:
            import instaloader  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover — depends on env
            return None
        self._module = instaloader
        return instaloader

    async def extract_metadata(
        self,
        url: str,
        *,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        instaloader = self._import_module()
        if instaloader is None:
            raise BackendNotAvailableError(self.strategy)

        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(
                self._executor,
                _extract_post,
                instaloader,
                url,
                options or {},
            )
        except Exception as exc:
            raise ProviderError(
                f"instaloader extraction failed: {exc}",
                code="EXTRACTION_FAILED",
                details={"url": url, "engine": self.strategy.value},
            ) from exc

        return _post_to_result(url, data)

    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        instaloader = self._import_module()
        if instaloader is None:
            raise BackendNotAvailableError(self.strategy)

        os.makedirs(dest_dir, exist_ok=True)
        loop = asyncio.get_running_loop()
        try:
            data, paths = await loop.run_in_executor(
                self._executor,
                _download_post,
                instaloader,
                url,
                dest_dir,
                task_id,
                sink,
                options or {},
            )
        except Exception as exc:
            raise ProviderError(
                f"instaloader download failed: {exc}",
                code="DOWNLOAD_FAILED",
                details={"url": url, "engine": self.strategy.value},
            ) from exc

        result = _post_to_result(url, data)
        result.output_paths = paths
        result.bytes_written = sum(os.path.getsize(p) for p in paths if os.path.exists(p))
        return result


# ---------------------------------------------------------------------------
# Sync helpers
# ---------------------------------------------------------------------------


def _new_loader(instaloader: Any, dest_dir: str, options: dict[str, Any]) -> Any:
    L = instaloader.Instaloader(
        dirname_pattern=dest_dir,
        save_metadata=False,
        post_metadata_txt_pattern="",
        download_comments=False,
        download_geotags=False,
        quiet=True,
        user_agent=options.get("user_agent"),
    )
    if options.get("username") and options.get("password"):
        L.login(options["username"], options["password"])
    if options.get("sessionfile"):
        L.load_session_from_file(options.get("username"), options["sessionfile"])
    return L


def _extract_post(instaloader: Any, url: str, options: dict[str, Any]) -> dict[str, Any]:
    L = _new_loader(instaloader, "/tmp/mediahub-instaloader-meta", options)
    post = instaloader.Post.from_shortcode(L.context, _extract_shortcode(url))
    return {
        "shortcode": post.shortcode,
        "title": post.title or post.caption or post.shortcode,
        "uploader": post.owner_username,
        "is_video": post.is_video,
        "url": post.url,
        "video_url": getattr(post, "video_url", None),
        "duration": getattr(post, "video_duration", None),
        "view_count": post.video_view_count if post.is_video else None,
        "like_count": post.likes,
        "caption": post.caption,
        "sidecar": [n.url for n in post.get_sidecar_nodes()] if post.mediacount > 1 else [],
        "mediacount": post.mediacount,
    }


def _download_post(
    instaloader: Any,
    url: str,
    dest_dir: str,
    task_id: str,
    sink: DownloadSink | None,
    options: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    L = _new_loader(instaloader, dest_dir, options)
    post = instaloader.Post.from_shortcode(L.context, _extract_shortcode(url))

    before = set(os.listdir(dest_dir))
    L.download_post(post, target=post.owner_username or "mediahub")
    after = set(os.listdir(dest_dir))
    new_files = sorted(after - before)
    paths = [
        os.path.join(dest_dir, f) for f in new_files if os.path.isfile(os.path.join(dest_dir, f))
    ]

    if sink is not None and paths:
        sink.on_progress(
            task_id=task_id,
            percent=100.0,
            bytes_done=len(paths),
            total_bytes=len(paths),
        )

    data = {
        "shortcode": post.shortcode,
        "title": post.title or post.caption or post.shortcode,
        "uploader": post.owner_username,
        "is_video": post.is_video,
        "url": post.url,
        "video_url": getattr(post, "video_url", None),
        "duration": getattr(post, "video_duration", None),
        "view_count": post.video_view_count if post.is_video else None,
        "like_count": post.likes,
        "caption": post.caption,
        "sidecar": [n.url for n in post.get_sidecar_nodes()] if post.mediacount > 1 else [],
        "mediacount": post.mediacount,
    }
    return data, paths


def _extract_shortcode(url: str) -> str:
    """Extracts an Instagram shortcode from a post URL."""
    import re

    m = re.search(r"/(?:p|reel|reels)/([^/?#]+)", url)
    if not m:
        raise ProviderError(
            "Could not extract Instagram shortcode",
            code="INVALID_URL",
            details={"url": url},
        )
    return m.group(1)


def _post_to_result(url: str, data: dict[str, Any]) -> ExtractionResult:
    meta = MediaMetadata(
        title=str(data.get("title") or data.get("shortcode") or "instagram"),
        uploader=data.get("uploader"),
        duration_seconds=data.get("duration"),
        thumbnail_url=data.get("url"),
        tags=[],
        extra={
            "shortcode": data.get("shortcode"),
            "is_video": data.get("is_video"),
            "view_count": data.get("view_count"),
            "like_count": data.get("like_count"),
            "mediacount": data.get("mediacount"),
            "url": url,
        },
    )
    formats: list[FormatOption] = []
    if data.get("is_video"):
        formats.append(
            FormatOption(
                format_id="video",
                label="video mp4",
                ext="mp4",
                is_audio_only=False,
            )
        )
    formats.append(
        FormatOption(
            format_id="image",
            label="image jpg",
            ext="jpg",
            is_audio_only=False,
        )
    )
    return ExtractionResult(metadata=meta, formats=formats, raw=data)


__all__ = ["InstaloaderBackend"]
