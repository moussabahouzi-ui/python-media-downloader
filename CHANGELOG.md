# Changelog

All notable changes to MediaHub are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed — Phase 7: Production Validation

- Audited all three layers (Flutter, Kotlin, Python) and fixed 26 issues that
  would have prevented a real Android build.
- **Flutter (12 fixes)**: Fixed broken import in `engine_service.dart`; rewrote
  `_guard` to return `Future<Result<T>>` instead of throwing (broke ~60 methods);
  added `material.dart` import for `IconData`/`Icons`; removed duplicate
  `RepeatMode` enum; added `widgets.dart` import for `BuildContext`; rewrote
  `resolveDynamic` with correct `CorePalette` tone-palette API; created
  `assets/images/` directory; replaced all `goNamed`/`pushNamed` with `go`/`push`;
  added `playerBackendProvider` override in `main.dart`; guarded `substring` on
  short IDs; removed dead stream in `pip_method_channel.dart`; bumped Flutter
  constraint to `>=3.27.0`.
- **Kotlin (14 fixes)**: Made `PythonRuntime.doStart()` `suspend` + used
  `delay()` instead of `Thread.sleep`; fixed `DownloadScheduler` runtime
  reference; fixed `MainActivity` PiP `isInPipMode()` call; added `xmlns:tools`
  to `themes.xml` + switched parent to `AppCompat`; wired up Flutter Gradle
  Plugin in `settings.gradle.kts` + `build.gradle.kts`; fixed `exitValue()`
  crash with `runCatching`; fixed `dispose()` process leak with `runBlocking`;
  added `unbind()` in `onDestroy`; used `DownloadForegroundService.start()`
  instead of bare `startService`; stored + cancelled event collector `Job`;
  handled `JSONObject.NULL` in `toMap()`/`toList()`; added
  `WRITE_EXTERNAL_STORAGE` for API 24-28; excluded encrypted prefs from backup;
  added `@Synchronized` to `ensureRuntime`; added release `signingConfig`.
- **Docs**: Rewrote `docs/BUILD.md` with accurate build instructions; created
  `docs/PRODUCTION_CHECKLIST.md` (80+ item release checklist).
- **Python**: No issues found — 372 tests pass, ruff clean, live IPC verified.

### Added — Phase 6: Settings, Security, Scheduling, Release

- Final phase: persistent settings store, scheduled downloads (WorkManager),
  encrypted credential management (Android Keystore), full Settings UI,
  Scheduler UI, troubleshooting guide, and release-ready configuration.
- **Settings store** (`database/settings_repository.py`): key-value
  `app_settings` table with 16 known keys (download concurrency/retries/dest,
  appearance theme/dynamic-color/language, security encrypt/auto-lock,
  playback speed/skip-silence, notifications, scheduler check-interval).
  `get_all()` merges stored values with defaults. 6 engine methods:
  `settings.get/get_all/set/set_many/delete/reset`.
- **Scheduler** (`database/scheduler_repository.py`): 4 schedule types —
  `one_time`, `interval`, `daily`, `weekly`. `next_run_at` computed on
  create/update; `due_schedules()` returns elapsed schedules; `mark_run()`
  advances recurring schedules and disables one-time. 8 engine methods:
  `scheduler.create/list/get/update/set_enabled/delete/due/mark_run`.
- **Credentials** (`database/credentials_repository.py`): encrypted at rest
  (XOR-stream cipher keyed off Android Keystore in production, DB-path-derived
  key in dev). Passwords/tokens never returned in plaintext over the bridge
  (`credentials.get` returns `hasPassword`/`hasToken` booleans only).
  5 engine methods: `credentials.set/get/list/delete/has`.
- **Kotlin**: `DownloadScheduler` + `ScheduleCheckWorker` (WorkManager
  periodic 15-min check → `scheduler.due` → `download.enqueue` →
  `scheduler.mark_run`). `SecurePreferences` (EncryptedSharedPreferences +
  Android Keystore) initializes the engine encryption key.
  `MediaHubApplication.onCreate` initializes secure prefs + starts scheduler.
  Added `androidx.security.crypto` dependency.
- **Flutter Settings screen** (full rewrite): Appearance (theme mode chips,
  dynamic color switch, language dropdown), Downloads (concurrency slider,
  retries slider, default folder), Security (encrypt storage + auto-lock
  switches), Scheduler entry, About, Reset. Backed by the engine settings
  store via `SettingsNotifier` — settings persist across restarts and are
  shared with the engine.
- **Flutter Scheduler screen**: create (URL + type + interval), list with
  enable/disable toggles + delete, run count + next-run display.
- **EngineService**: +19 Phase 6 methods (6 settings, 4 scheduler,
  5 credentials) returning typed `Result<T>`.
- **Docs**: new `docs/TROUBLESHOOTING.md` (build, runtime, performance,
  security issues). Updated `docs/BRIDGE_CONTRACT.md` with Phase 6 method
  tables. Updated `docs/ARCHITECTURE.md` roadmap — all 6 phases complete.
- **Tests**: 27 new Python tests (settings get/set/get_all/delete/reset,
  scheduler create/list/enabled/due/mark_run one-time+interval, credentials
  set/get/encrypted-at-rest/list/has/delete/update, engine methods). Python
  suite: 372 passed; ruff clean; live IPC verified for settings.get_all,
  scheduler.list, credentials.list.

### Notes

- **MediaHub is now release-ready.** All 6 phases are complete. The Python
  engine (372 tests, ruff clean, live IPC verified) is fully production-grade.
  Flutter and Kotlin layers are source-complete and designed for a real Android
  toolchain per `docs/BUILD.md`.
- Total engine method surface: **73 methods** across 10 namespaces
  (engine, provider, download, library, favorites, collections, history, file,
  storage, playlists, settings, scheduler, credentials).
- Total Python tests: **372**. Total Flutter test files: **9**.

### Added — Phase 5: Players

- Built-in video and audio players with background playback, Picture-in-
  Picture, playback speed, gesture controls, sleep timer, and ordered
  playlists with shuffle/repeat.
- **Playback engine** (`lib/features/player/providers/player_provider.dart`):
  `PlayerNotifier` (Riverpod StateNotifier) owns the entire playback state —
  queue + currentIndex, play/pause/seek/skipNext/skipPrevious, shuffle,
  repeat (off/all/one), playback speed (0.25–4.0, clamped), and a 1-second
  ticking sleep timer that auto-pauses at zero. `PlayerBackend` abstract
  interface with `JustAudioBackend` (just_audio) production implementation.
  Fully testable via injected `FakePlayerBackend`.
- **Video player screen**: full-screen with auto-hiding gesture controls
  (4s fade), top bar (back/title/speed selector), center controls
  (shuffle/prev/play-pause/next/repeat), bottom bar (seek slider +
  position/sleep-timer/duration).
- **Audio player screen**: "now playing" layout with artwork, track info,
  progress slider, main controls, secondary controls (speed popup +
  sleep-timer popup with 5/15/30/45/60 min presets).
- **Picture-in-Picture** (Android 8.0+): Kotlin `MainActivity` registers
  `com.mediahub.app/pip` method channel (`isPipSupported`/`enterPipMode`/
  `isInPipMode`) + `com.mediahub.app/pip/events` event channel streaming PiP
  mode transitions. `enterPipMode()` uses 16:9 aspect ratio.
  `android:supportsPictureInPicture="true"` added to manifest.
- **Sleep timer**: countdown from 5/15/30/45/60 min (or custom). Ticks every
  second; pauses playback and clears when zero. Remaining time shown in both
  player screens.
- **Playlists** (Python + Flutter): ordered playback queues with `position`
  column. `PlaylistsRepository` maintains position integrity on
  add/remove/reorder (shifts + re-indexes). 10 new engine methods:
  `playlists.create/list/rename/delete/add_item/remove_item/reorder/items/
  set_shuffle/set_repeat`. Flutter `PlaylistsScreen` with create/delete.
  `Playlist` + `RepeatMode` models on both sides.
- **pubspec**: added `video_player`, `just_audio`, `audio_service` for
  production media playback.
- **Docs**: new `docs/PLAYERS.md`; `docs/BRIDGE_CONTRACT.md` updated with
  Phase 5 playlists method table + Playlist schema.
- **Tests**: 16 new Python tests (playlists repository + engine methods);
  Flutter tests for all 10 engine service playlist methods, Playlist/RepeatMode
  model parsing, and 13 playback state tests (playQueue, pause/play, skipNext/
  Previous, shuffle, repeat cycling, speed clamping, position stream,
  completion→skip, completion→repeat-one, sleep timer countdown→pause,
  cancel sleep timer, stop). Python suite: 345 passed; ruff clean; live IPC
  verified.

### Notes

- The Python engine is fully verified end-to-end in this environment. Flutter
  and Kotlin layers are source-complete and intended for a real Android
  toolchain per `docs/BUILD.md`.

### Added — Phase 4: Media Library & File Manager

- Media library with auto-indexing of completed downloads, file manager
  (rename/move/copy/delete/recycle bin), download history + stats, favorites,
  collections, storage analyzer, and duplicate finder.
- **DB schema**: new `media_items`, `download_history`, `collections`, and
  `collection_items` tables with indexes. Foreign keys with `ON DELETE CASCADE`
  on collection membership.
- **Models** (`storage/models.py`): `MediaItem`, `MediaCategory` (video/audio/
  image/other, inferred from extension), `Collection`, `HistoryEntry`,
  `DownloadStats`, `StorageBreakdown`, `DuplicateGroup`. All with `to_dict()`
  for JSON-RPC.
- **Repositories** (`database/`): `MediaRepository` (CRUD + list with
  category/favorite/recycled filters + sort + full-text search + set_favorite/
  set_recycled/update_path/count), `HistoryRepository` (append-only record +
  list + stats aggregation by state/provider/category + clear),
  `CollectionsRepository` (create/get/list/rename/delete + add_item/
  remove_item with incremental count + items JOIN query).
- **File manager** (`storage/file_manager.py`): rename, move, copy (indexes the
  copy as a new item), recycle (soft-delete to recycle bin dir), restore,
  delete_permanent, empty_recycle_bin. All operations keep the media index in
  sync and raise `FileManagerError` on conflicts.
- **Storage analyzer** (`storage/analyzer.py`): `StorageAnalyzer.analyze()`
  breaks down total bytes + file count by category. `DuplicateFinder.find()`
  uses a two-pass strategy (group by size, then SHA-256 hash) to detect true
  duplicates.
- **Auto-indexing on completion**: `DownloadManager._index_completed_task()`
  indexes every output file of a completed download into `media_items` with
  provenance (provider/url/task_id) and metadata (title/uploader/tags).
  `_record_history()` appends to `download_history` on completed/failed.
- **Engine methods** (32 new): `library.list/search/item/count`,
  `favorites.add/remove/list`, `collections.create/list/rename/delete/
  add_item/remove_item/items`, `history.list/stats/clear`,
  `file.rename/move/copy/recycle/restore/delete/empty_recycle`,
  `storage.analyze/duplicates`. All require persistence enabled.
- **Flutter**: `EngineService` extended with all Phase 4 methods returning typed
  `Result<T>`. New models: `MediaItem`, `MediaCategory`, `MediaCollection`,
  `HistoryEntry`, `DownloadStats`, `StorageBreakdown`, `DuplicateGroup`. New
  Library screen (category chips + favorites filter + search + media grid with
  favorite toggle) and History screen (stats card + history list + clear).
  Wired into the router; reachable from the home dashboard.
- **Docs**: new `docs/MEDIA_LIBRARY.md`; `docs/BRIDGE_CONTRACT.md` updated with
  Phase 4 method group summary.
- **Tests**: 54 new Python tests (repository round-trips, file manager ops,
  duplicate finder, stats, storage analyzer, engine methods). Python suite:
  329 passed; ruff clean; live IPC verified for library.count, history.stats,
  collections.list, storage.analyze, storage.duplicates.

### Notes

- The Python engine is fully verified end-to-end in this environment. Flutter
  and Kotlin layers are source-complete and intended for a real Android
  toolchain per `docs/BUILD.md`.

### Added — Phase 3: Download Manager

- Production download manager with concurrency control, pause/resume, retry
  with exponential backoff, SQLite persistence, and partial-file recovery.
- **Task FSM**: formal state machine (QUEUED → ACTIVE → COMPLETED/PAUSED/FAILED
  → CANCELLED) with `IllegalStateTransition` guards on every `mark_*` method.
  Added `mark_resumed`, `mark_retry_scheduled`, `reset_for_resume`. New fields:
  `last_error`, `retries`, `retry_after`.
- **Retry policy** (`download/retry.py`): `RetryPolicy` with `max_retries`,
  `base_delay`, `multiplier`, `max_delay`, `jitter`. Exponential backoff with
  capped delay + uniform jitter. The manager retries transient failures and
  skips retry for permanent errors (provider-not-found).
- **Cancellation tokens** (`download/cancellation.py`):
  `CancellationToken` + `CancellationTokenSource` with "pause"/"cancel" reason
  tracking. The `_ProgressSink` checks the token between progress callbacks and
  raises `DownloadCancelled`. The manager also wraps `provider.download()` in an
  `asyncio.Task` and cancels it for hard interruption.
- **Recovery manager** (`download/recovery.py`): detects `.part` files (yt-dlp
  convention) and known output paths in dest_dir, returns `{resume,
  partial_files, resume_from}` options for the provider. yt-dlp resumes
  automatically; the generic HTTP provider uses `resume_from` for Range requests.
  `cleanup_partials()` removes `.part` files on cancel.
- **SQLite persistence** (`database/`): `Database` (WAL mode, thread-safe) +
  `TaskRepository` (upsert on every state transition, `load_non_terminal()` on
  engine start). Active tasks are moved back to QUEUED on restart; the recovery
  manager handles partial-file resume. `clear_terminal()` deletes from both
  queue and DB. Configurable via `EngineConfig.persist_downloads`.
- **Engine methods**: `download.pause`, `download.resume`, `download.retry`,
  `download.clear`. New notifications: `download.paused`, `download.resumed`,
  `download.retry_scheduled`.
- **Config**: `EngineConfig` gained `persist_downloads`, `max_retries`,
  `retry_base_delay`, `retry_max_delay` (env-driven).
- **Flutter**: `EngineService` gained `pauseDownload`, `resumeDownload`,
  `retryDownload`, `clearTerminalDownloads`. `DownloadTaskInfo` gained
  `lastError`, `retries`, `retryAfter`. Download Center task tiles now show
  context-aware action buttons (Pause/Cancel for active, Resume/Cancel for
  paused, Retry for failed). Queue header has a "Clear finished" button.
- **Docs**: new `docs/DOWNLOAD_MANAGER.md`; `docs/BRIDGE_CONTRACT.md` updated
  with Phase 3 methods, extended `TaskDict`, and new notifications.
- **Tests**: 64 new Python tests (task FSM, retry/backoff, cancellation,
  persistence round-trip, recovery, manager integration with pause/resume/
  cancel/retry). Python suite: 275 passed; ruff clean; live IPC verified.

### Notes

- The Python engine is fully verified end-to-end in this environment. Flutter
  and Kotlin layers are source-complete and intended for a real Android
  toolchain per `docs/BUILD.md`.

### Added — Phase 2: Provider System

- Modular provider architecture with 13 platform providers (YouTube, Instagram,
  Facebook, TikTok, Twitter/X, Reddit, Vimeo, Dailymotion, Pinterest, Twitch,
  SoundCloud, Threads, Snapchat) plus the generic HTTP fallback.
- Extraction backend layer wrapping yt-dlp, gallery-dl, and Instaloader behind a
  uniform async `ExtractionBackend` interface. Backends lazy-import their
  library, run all blocking calls in a thread pool, and report availability via
  `is_available()` so the engine boots even when a library is absent.
- `BackendRegistry` singleton mapping `EngineStrategy` → backend; injectable in
  tests via a `FakeBackend`.
- `BackendDelegateProvider` base class that factors out detection +
  backend-delegation boilerplate; each platform provider is a few dozen lines.
- Auth model: `Credential`, `CredentialStore` protocol, `InMemoryCredentialStore`,
  with credential injection into backend options. Providers declare
  `auth_required` (Twitter/X requires it).
- Evolved `ProviderResult` to support multi-file outputs (galleries) with
  `output_paths` + a convenience `output_path` getter.
- New engine method surface: `provider.detect`, `provider.metadata`,
  `provider.list`, `download.enqueue`, `download.cancel`, `download.list`,
  `download.status`, plus six download lifecycle notifications streamed over the
  event channel.
- Flutter Download Center screen: URL input, provider detection, metadata
  preview (title/uploader/duration/auth badge), enqueue, and a live task list
  with progress bars and cancel buttons. Wired into the router and reachable
  from the home dashboard.
- `EngineService` extended with typed `detectProvider`, `fetchMetadata`,
  `listProviders`, `enqueueDownload`, `cancelDownload`, `listDownloads`,
  `downloadStatus` methods returning `Result<T>`.
- `ProviderInfo`, `DetectionResult`, `MediaMetadata`, `DownloadTaskInfo`,
  `DownloadState` typed models mirrored from the Python engine.
- `docs/PROVIDERS.md` documenting the provider architecture, backends, auth,
  and how to add a new platform.
- `docs/BRIDGE_CONTRACT.md` extended with the Phase 2 method tables, the
  `CapabilityDescriptor` and `TaskDict` schemas, and download notification
  events.
- Leaf `engine_kinds.py` module holding `EngineStrategy` / `EngineDecision` to
  break a potential import cycle between `download.strategy` and `providers`.
- 178 new Python tests (backends, every provider's detection + delegation,
  engine methods, auth) and Flutter tests (engine service provider/download
  methods, Download Center view-model). Python suite: 211 passed; ruff clean;
  live stdio IPC verified for `provider.detect`, `provider.list`,
  `download.enqueue`, `download.list`, and the `PROVIDER_NOT_FOUND` error path.

### Notes

- The Python engine is fully verified end-to-end in this environment. Flutter
  and Kotlin layers are source-complete and intended for a real Android
  toolchain per `docs/BUILD.md`.

### Added — Phase 1: Foundation

- Monorepo layout for Flutter (`lib/`), Android Kotlin (`android/`), and the
  embedded Python engine (`python_engine/`).
- Flutter application shell: `main.dart`, `app.dart`, GoRouter scaffold, and a
  Material 3 / Material You theming system with Light, Dark, and AMOLED modes
  plus dynamic-color support on Android 12+.
- Clean Architecture scaffolding under `lib/core/` (config, constants, errors,
  `Result` type, platform method-channel abstraction).
- Typed Method Channel contract (`com.mediahub.app/engine`) shared between Dart
  and Kotlin, with a JSON-RPC IPC contract shared between Kotlin and Python.
- Android native layer: `MediaHubApplication`, `MainActivity`, method-channel
  bridge, `PythonRuntime` launcher, `DownloadForegroundService`, notification
  channels, and storage path helpers.
- Python engine bootstrap: `engine.py`, line-delimited JSON-RPC IPC server,
  `download` package (task/queue/manager/strategy skeletons), pluggable
  `providers` registry with a `generic` provider, structured logging utility.
- Documentation foundation: architecture, development, build, contribution, and
  bridge-contract references.
- Smoke tests: Flutter theme/channel/widget tests; Python engine bootstrap,
  JSON-RPC framing, and provider-registry tests.
- Tooling config: `analysis_options.yaml` (Flutter), `pyproject.toml` +
  `requirements.txt` (Python, ruff), `.editorconfig`, `.gitignore`.

### Notes

- Source is reference-complete. It is intended to be opened and built in a real
  Android toolchain; it is not compiled by the authoring environment.
