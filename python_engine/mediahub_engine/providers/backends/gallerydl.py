"""gallery-dl backend.

gallery-dl is a synchronous library oriented toward image/gallery sites. Its
Python API is lower-level than yt-dlp's: callers configure extractors and
iterate over results. This backend wraps that flow behind the uniform
[ExtractionBackend] surface.
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


class GalleryDlBackend(ExtractionBackend):
    """Wraps `gallery_dl` for image/gallery platforms."""

    strategy = EngineStrategy.GALLERY_DL

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="gallerydl",
        )
        self._module: Any | None = None

    def is_available(self) -> bool:
        return self._import_module() is not None

    def _import_module(self) -> Any | None:
        if self._module is not None:
            return self._module
        try:
            import gallery_dl  # type: ignore[import-not-found]
            import gallery_dl.config  # type: ignore[import-not-found]
            import gallery_dl.job  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover — depends on env
            return None
        self._module = gallery_dl
        return gallery_dl

    async def extract_metadata(
        self,
        url: str,
        *,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        gdl = self._import_module()
        if gdl is None:
            raise BackendNotAvailableError(self.strategy)

        loop = asyncio.get_running_loop()
        try:
            items = await loop.run_in_executor(
                self._executor,
                _collect_metadata,
                gdl,
                url,
                options or {},
            )
        except Exception as exc:
            raise ProviderError(
                f"gallery-dl extraction failed: {exc}",
                code="EXTRACTION_FAILED",
                details={"url": url, "engine": self.strategy.value},
            ) from exc

        return _items_to_result(url, items)

    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        gdl = self._import_module()
        if gdl is None:
            raise BackendNotAvailableError(self.strategy)

        os.makedirs(dest_dir, exist_ok=True)
        loop = asyncio.get_running_loop()

        try:
            items, paths = await loop.run_in_executor(
                self._executor,
                _download_url,
                gdl,
                url,
                dest_dir,
                task_id,
                sink,
                options or {},
            )
        except Exception as exc:
            raise ProviderError(
                f"gallery-dl download failed: {exc}",
                code="DOWNLOAD_FAILED",
                details={"url": url, "engine": self.strategy.value},
            ) from exc

        result = _items_to_result(url, items)
        result.output_paths = paths
        result.bytes_written = sum(os.path.getsize(p) for p in paths if os.path.exists(p))
        return result


# ---------------------------------------------------------------------------
# Sync helpers (run in the thread pool)
# ---------------------------------------------------------------------------


def _collect_metadata(gdl: Any, url: str, options: dict[str, Any]) -> list[dict[str, Any]]:
    """Runs a gallery-dl `UrlJob` in dry mode and collects item metadata."""
    import gallery_dl.config as config  # type: ignore[import-not-found]
    import gallery_dl.job as job  # type: ignore[import-not-found]

    config.set(("proxy",), options.get("proxy"))
    config.set(("base-directory",), "/tmp/mediahub-gallerydl-meta")

    items: list[dict[str, Any]] = []

    def _sink(_job: Any, item: Any) -> None:
        items.append(dict(item) if hasattr(item, "items") else {"url": str(item)})

    j = job.UrlJob(url)
    j.handle_urlextract = _sink  # type: ignore[attr-defined]
    j.run()
    return items


def _download_url(
    gdl: Any,
    url: str,
    dest_dir: str,
    task_id: str,
    sink: DownloadSink | None,
    options: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Downloads via gallery-dl, reporting progress per item to `sink`."""
    import gallery_dl.config as config  # type: ignore[import-not-found]
    import gallery_dl.job as job  # type: ignore[import-not-found]

    config.set(("base-directory",), dest_dir)
    config.set(("proxy",), options.get("proxy"))
    if options.get("cookiefile"):
        config.set(("cookies",), options["cookiefile"])

    items: list[dict[str, Any]] = []
    paths: list[str] = []
    total = 0

    def _handle(_job: Any, item: Any) -> None:
        nonlocal total
        d = dict(item) if hasattr(item, "items") else {"url": str(item)}
        items.append(d)
        total += 1
        paths.append(d.get("filepath") or "")
        if sink is not None:
            sink.on_progress(
                task_id=task_id,
                percent=0.0,
                bytes_done=total,
                total_bytes=None,
            )

    j = job.DownloadJob(url)
    j.handle_prepare = _handle  # type: ignore[attr-defined]
    j.run()
    return items, [p for p in paths if p]


def _items_to_result(url: str, items: list[dict[str, Any]]) -> ExtractionResult:
    if not items:
        return ExtractionResult(
            metadata=MediaMetadata(title=_derive_title(url), extra={"url": url}),
            warnings=["gallery-dl returned no items"],
        )

    first = items[0]
    title = first.get("title") or first.get("filename") or first.get("name") or _derive_title(url)
    uploader = first.get("uploader") or first.get("user") or first.get("account")

    formats: list[FormatOption] = []
    seen: set[str] = set()
    for item in items:
        ext = str(
            item.get("extension") or os.path.splitext(item.get("url", ""))[1].lstrip(".") or "?"
        )
        if ext not in seen:
            seen.add(ext)
            formats.append(
                FormatOption(
                    format_id=ext,
                    label=f"image {ext}".strip(),
                    ext=ext,
                    resolution=item.get("resolution"),
                    is_audio_only=False,
                    filesize=item.get("size"),
                )
            )

    return ExtractionResult(
        metadata=MediaMetadata(
            title=str(title),
            uploader=str(uploader) if uploader else None,
            thumbnail_url=first.get("thumbnail"),
            tags=list(first.get("tags") or []),
            extra={
                "item_count": len(items),
                "url": url,
                "category": first.get("category"),
            },
        ),
        formats=formats,
        raw={"items": items},
    )


def _derive_title(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1] or "gallery"


__all__ = ["GalleryDlBackend"]
