# Download Manager

This document describes the Phase 3 download manager: concurrency control,
pause/resume, retry with backoff, persistence, and recovery.

> Authoritative for Phase 3. Mirrored in code at
> `python_engine/mediahub_engine/download/`.

## 1. Architecture

```
           ┌──────────────────────────────────────────────┐
           │            DownloadManager                    │
           │                                               │
           │  ┌─────────┐    ┌──────────────────────────┐ │
  enqueue─►│  │  Queue  │───►│  Worker Pool (N coros)   │ │
           │  │ (priority)│   │  semaphore-limited       │ │
           │  └─────────┘    └──────────┬───────────────┘ │
           │                            │                  │
           │  ┌─────────────────────────▼──────────────┐  │
           │  │  _run_task(task)                        │  │
           │  │   1. mark_started (FSM)                 │  │
           │  │   2. resolve provider + engine          │  │
           │  │   3. recovery.prepare_resume()          │  │
           │  │   4. provider.download() as asyncio.Task│  │
           │  │   5. await ──► completed | cancelled    │  │
           │  │                    | failed             │  │
           │  │   6. persist + notify                   │  │
           │  └─────────────────────────────────────────┘  │
           │                                               │
           │  RetryPolicy  RecoveryManager  TaskRepository │
           └──────────────────────────────────────────────┘
```

## 2. Task lifecycle (FSM)

```
QUEUED ──start──► ACTIVE ──complete──► COMPLETED
                   │  │
          pause ───┘  ├──fail──► FAILED ──retry──► QUEUED
                   │                  (if budget remains)
              pause │
                   ▼
                 PAUSED ──resume──► QUEUED

Any non-terminal state ──cancel──► CANCELLED
```

Every transition is enforced by the `mark_*` methods on `DownloadTask`, which
raise `IllegalStateTransition` on invalid attempts. This makes the FSM
testable and prevents corrupted state.

## 3. Concurrency

- A pool of N worker coroutines (N = `max_concurrent_downloads`, default 4)
  drains the queue.
- An `asyncio.Semaphore` caps simultaneous active downloads.
- `next_runnable()` returns the highest-priority QUEUED task whose
  `retry_after` backoff has elapsed (or is `None`).

## 4. Pause / Resume

1. **Pause** (active task): the manager sets the task's `CancellationTokenSource`
   to "pause" and cancels the running `asyncio.Task`. The provider's blocking
   call gets a `CancelledError`. The `_handle_cancellation` handler sees
   `reason == "pause"` and calls `mark_paused()`. Partial files are preserved.

2. **Pause** (queued task): directly transitions to PAUSED (no running task to
   interrupt).

3. **Resume**: transitions PAUSED → QUEUED. A worker picks it up. The
   `RecoveryManager.prepare_resume()` scans the dest_dir for `.part` files and
   known output paths, returning `{resume: True, partial_files: [...],
   resume_from: <bytes>}`. These options are merged into the provider call.
   yt-dlp resumes automatically from `.part` files; the generic HTTP provider
   uses `resume_from` for HTTP Range requests.

## 5. Cancel

Like pause, but:
- The cancellation reason is "cancel" → `mark_cancelled()`.
- `RecoveryManager.cleanup_partials()` removes `.part` files from dest_dir.

## 6. Retry

On failure (except permanent errors like provider-not-found), the `RetryPolicy`
decides whether to retry:

- `should_retry(retries_so_far)` — True if `retries < max_retries`.
- `delay_for(attempt)` — `min(base * multiplier^attempt, max_delay) + jitter`.

If retrying: `mark_retry_scheduled(delay)` transitions FAILED → QUEUED with
`retry_after = now + delay`. The worker's `next_runnable()` skips tasks whose
`retry_after` is in the future. Once the delay elapses, the task becomes
runnable again.

If exhausted: the task stays FAILED and emits `download.failed`.

**Manual retry**: `download.retry` resets `retries = 0` and immediately
re-queues (delay = 0).

Default policy: 3 retries, 1s base, 2x multiplier, 60s cap, 0.5s jitter.

## 7. Persistence

- `Database` (stdlib `sqlite3`, WAL mode) stores the `download_tasks` table.
- `TaskRepository.save()` upserts on every state transition.
- On engine `start()`, `load_non_terminal()` restores QUEUED/ACTIVE/PAUSED
  tasks. ACTIVE tasks are moved back to QUEUED (the worker re-runs them; the
  recovery manager handles partial-file resume).
- `clear_terminal()` deletes terminal tasks from both the queue and the DB.
- Persistence is configurable via `EngineConfig.persist_downloads` (default
  True); disabled in unit tests for speed.

## 8. Recovery

`RecoveryManager` scans the dest_dir for:
- `.part` files (yt-dlp convention)
- Previously-known `output_paths` from the task

Returns `{resume, partial_files, resume_from}` which the manager merges into
the provider's download options. yt-dlp resumes `.part` files automatically;
the generic HTTP provider uses the `resume_from` byte offset for Range requests.

## 9. Engine method surface (Phase 3 additions)

| Method | Params | Returns |
|--------|--------|---------|
| `download.pause` | `{taskId}` | `{taskId, paused}` |
| `download.resume` | `{taskId}` | `{taskId, resumed}` |
| `download.retry` | `{taskId}` | `{taskId, retried}` |
| `download.clear` | `{}` | `{cleared: int}` |

New notifications: `download.paused`, `download.resumed`,
`download.retry_scheduled`.

`TaskDict` now includes: `lastError`, `retries`, `retryAfter`.

## 10. Performance

- Progress notifications are throttled to 4 Hz per task.
- SQLite writes are serialized through a lock; WAL mode allows concurrent
  reads.
- Worker coroutines are lightweight; the semaphore is the real concurrency cap.
- All blocking provider calls run in a `ThreadPoolExecutor` (via the backend)
  so the asyncio loop stays responsive for IPC.
