"""yt-dlp backend.

yt-dlp is a synchronous library; all calls are offloaded to a thread executor
so the asyncio loop stays responsive. The library is lazy-imported so the
engine boots (and tests run) without it installed.
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


class YtDlpBackend(ExtractionBackend):
    """Wraps `yt_dlp.YoutubeDL` for video/audio platforms."""

    strategy = EngineStrategy.YTDLP

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ytdlp",
        )
        self._yt_dlp: Any | None = None

    # ---- availability ----

    def is_available(self) -> bool:
        return self._import_module() is not None

    def _import_module(self) -> Any | None:
        if self._yt_dlp is not None:
            return self._yt_dlp
        try:
            import yt_dlp  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover — depends on env
            return None
        self._yt_dlp = yt_dlp
        return yt_dlp

    # ---- public API ----

    async def extract_metadata(
        self,
        url: str,
        *,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        yt_dlp = self._import_module()
        if yt_dlp is None:
            raise BackendNotAvailableError(self.strategy)

        opts = _merge_options(options, download=False)
        loop = asyncio.get_running_loop()

        def _extract() -> dict[str, Any]:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[union-attr]
                return ydl.extract_info(url, download=False) or {}

        try:
            info = await loop.run_in_executor(self._executor, _extract)
        except Exception as exc:
            raise ProviderError(
                f"yt-dlp extraction failed: {exc}",
                code="EXTRACTION_FAILED",
                details={"url": url, "engine": self.strategy.value},
            ) from exc

        return _info_to_result(info)

    async def download(
        self,
        url: str,
        *,
        dest_dir: str,
        task_id: str,
        sink: DownloadSink | None = None,
        options: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        yt_dlp = self._import_module()
        if yt_dlp is None:
            raise BackendNotAvailableError(self.strategy)

        os.makedirs(dest_dir, exist_ok=True)
        opts = _merge_options(
            options,
            download=True,
            dest_dir=dest_dir,
            progress_hooks=[_make_progress_hook(task_id, sink)],
        )
        loop = asyncio.get_running_loop()

        def _download() -> dict[str, Any]:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[union-attr]
                return ydl.extract_info(url, download=True) or {}

        try:
            info = await loop.run_in_executor(self._executor, _download)
        except Exception as exc:
            raise ProviderError(
                f"yt-dlp download failed: {exc}",
                code="DOWNLOAD_FAILED",
                details={"url": url, "engine": self.strategy.value},
            ) from exc

        result = _info_to_result(info)
        result.output_paths = _resolve_output_paths(info, dest_dir)
        result.bytes_written = sum(
            os.path.getsize(p) for p in result.output_paths if os.path.exists(p)
        )
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _merge_options(
    options: dict[str, Any] | None,
    *,
    download: bool,
    dest_dir: str | None = None,
    progress_hooks: list[Any] | None = None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": True,
        "retries": 3,
        "fragment_retries": 3,
        "noplaylist": True,
    }
    if not download:
        opts["skip_download"] = True
    if dest_dir is not None:
        opts["outtmpl"] = os.path.join(dest_dir, "%(title).200B.%(ext)s")
    if progress_hooks:
        opts["progress_hooks"] = progress_hooks
    if options:
        # Allow callers to override a curated allowlist of keys.
        for key in (
            "format",
            "writesubtitles",
            "writeautomaticsub",
            "subtitleslangs",
            "merge_output_format",
            "postprocessors",
            "username",
            "password",
            "cookiefile",
            "age_limit",
            "noplaylist",
            "playlist_items",
        ):
            if key in options:
                opts[key] = options[key]
    return opts


def _make_progress_hook(task_id: str, sink: DownloadSink | None) -> Any:
    def _hook(d: dict[str, Any]) -> None:
        if sink is None:
            return
        status = d.get("status")
        if status == "downloading":
            done = int(d.get("downloaded_bytes") or 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            total_int = int(total) if total else None
            percent = (done / total_int * 100.0) if total_int else 0.0
            sink.on_progress(
                task_id=task_id,
                percent=percent,
                bytes_done=done,
                total_bytes=total_int,
            )
        elif status == "finished":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            total_int = int(total) if total else None
            done = total_int or int(d.get("downloaded_bytes") or 0)
            sink.on_progress(
                task_id=task_id,
                percent=100.0,
                bytes_done=done,
                total_bytes=total_int,
            )

    return _hook


def _info_to_result(info: dict[str, Any]) -> ExtractionResult:
    meta = MediaMetadata(
        title=str(info.get("title") or info.get("id") or "media"),
        uploader=info.get("uploader") or info.get("channel"),
        duration_seconds=info.get("duration"),
        thumbnail_url=info.get("thumbnail"),
        categories=list(info.get("categories") or []),
        tags=list(info.get("tags") or []),
        extra={
            "uploader_id": info.get("uploader_id"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "webpage_url": info.get("webpage_url"),
            "extractor_key": info.get("extractor_key"),
            "resolution": info.get("resolution"),
            "vcodec": info.get("vcodec"),
            "acodec": info.get("acodec"),
            "fps": info.get("fps"),
            "ext": info.get("ext"),
        },
    )

    formats: list[FormatOption] = []
    for fmt in info.get("formats") or []:
        formats.append(
            FormatOption(
                format_id=str(fmt.get("format_id")),
                label=_format_label(fmt),
                ext=str(fmt.get("ext") or "?"),
                resolution=fmt.get("resolution") or _resolution_from_dims(fmt),
                fps=fmt.get("fps"),
                vcodec=fmt.get("vcodec"),
                acodec=fmt.get("acodec"),
                filesize=fmt.get("filesize") or fmt.get("filesize_approx"),
                is_audio_only=bool(
                    fmt.get("vcodec") in ("none", None) and fmt.get("acodec") not in ("none", None)
                ),
            )
        )

    return ExtractionResult(metadata=meta, formats=formats, raw=info)


def _format_label(fmt: dict[str, Any]) -> str:
    res = fmt.get("resolution") or _resolution_from_dims(fmt) or ""
    ext = fmt.get("ext") or ""
    vcodec = fmt.get("vcodec") or ""
    if vcodec == "none":
        return f"audio {ext}".strip()
    return f"{res} {ext}".strip()


def _resolution_from_dims(fmt: dict[str, Any]) -> str | None:
    w = fmt.get("width")
    h = fmt.get("height")
    if w and h:
        return f"{int(w)}x{int(h)}"
    if h:
        return f"{int(h)}p"
    return None


def _resolve_output_paths(info: dict[str, Any], dest_dir: str) -> list[str]:
    requested = info.get("requested_downloads") or []
    if requested:
        return [r["filepath"] for r in requested if r.get("filepath")]
    try:
        files = [os.path.join(dest_dir, f) for f in os.listdir(dest_dir)]
        files = [f for f in files if os.path.isfile(f)]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return files[:1]
    except OSError:
        return []


__all__ = ["YtDlpBackend"]
