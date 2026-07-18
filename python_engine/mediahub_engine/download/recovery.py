"""Recovery manager: detects partial downloads and prepares resume options.

When a task is paused or the engine restarts mid-download, partial files are
left on disk. The recovery manager scans the destination directory for `.part`
files (yt-dlp convention) or incomplete files, and passes resume hints to the
provider via the task options.

- yt-dlp resumes automatically when it sees a `.part` file with the same
  `outtmpl`; the recovery manager just ensures the dest_dir is unchanged.
- The generic HTTP provider supports HTTP Range requests via the `resume_from`
  option (byte offset).
"""

from __future__ import annotations

from pathlib import Path

from mediahub_engine.download.task import DownloadState, DownloadTask
from mediahub_engine.utils.logging import get_logger

log = get_logger(__name__)


class RecoveryManager:
    """Detects partial files and enriches task options for resume."""

    def __init__(self) -> None:
        pass

    def prepare_resume(self, task: DownloadTask) -> dict[str, object]:
        """Returns resume options to merge into the download call.

        Called by the manager when a task transitions PAUSED -> QUEUED ->
        ACTIVE. Returns a dict with:
          - ``resume``: True if partial files were found
          - ``partial_files``: list of detected partial file paths
          - ``resume_from``: byte offset (for the generic HTTP provider)
        """
        if task.state not in (DownloadState.QUEUED, DownloadState.ACTIVE):
            return {"resume": False}

        if not task.dest_dir:
            return {"resume": False}

        dest = Path(task.dest_dir)
        if not dest.is_dir():
            return {"resume": False}

        partials = self._find_partials(dest, task)
        if not partials:
            log.info("recovery: no partial files for task %s", task.task_id)
            return {"resume": False}

        log.info("recovery: found %d partial file(s) for task %s", len(partials), task.task_id)
        return {
            "resume": True,
            "partial_files": [str(p) for p in partials],
            "resume_from": task.bytes_done,
        }

    def _find_partials(self, dest: Path, task: DownloadTask) -> list[Path]:
        """Finds `.part` files and any previously-known output paths."""
        found: list[Path] = []

        # Known output paths from a prior run.
        for p in task.output_paths:
            path = Path(p)
            if path.exists() and path.is_file():
                found.append(path)

        # yt-dlp `.part` files.
        try:
            for entry in dest.iterdir():
                if entry.is_file() and entry.suffix == ".part":
                    found.append(entry)
        except OSError:
            pass

        return found

    def cleanup_partials(self, task: DownloadTask) -> int:
        """Removes partial files for a cancelled task. Returns count removed."""
        if not task.dest_dir:
            return 0
        dest = Path(task.dest_dir)
        if not dest.is_dir():
            return 0

        removed = 0
        try:
            for entry in dest.iterdir():
                if entry.is_file() and entry.suffix == ".part":
                    entry.unlink(missing_ok=True)
                    removed += 1
        except OSError:
            pass
        return removed


__all__ = ["RecoveryManager"]
