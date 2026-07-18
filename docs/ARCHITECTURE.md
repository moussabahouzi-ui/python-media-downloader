# Architecture

This document describes the end-to-end architecture of MediaHub. It is the
authoritative reference for every phase of development.

## 1. Goals & constraints

| Goal | Constraint |
|------|------------|
| Fully local operation | No external server. The entire engine runs on-device. |
| Modular platforms | Adding a provider must not touch core download logic. |
| Premium UX | Material 3 / Material You, 60fps, dark/light/AMOLED. |
| Reliability | ANR-free, crash-safe, resumable, recoverable downloads. |
| Maintainability | Clean Architecture + MVVM, typed bridges, strict lint. |

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Flutter (Dart)                                               │
│  presentation (widgets + viewmodels + riverpod providers)    │
│  domain (entities · usecases · repository interfaces)        │
│  data (repository impls · datasources · models)              │
└────────────────────────────┬────────────────────────────────┘
                             │ MethodChannel  com.mediahub.app/engine
┌────────────────────────────▼────────────────────────────────┐
│ Android Native (Kotlin)                                      │
│  MainActivity · MediaHubApplication                          │
│  DownloadForegroundService (long-lived host)                 │
│  WorkManager (scheduled / background)                        │
│  NotificationManager · StorageManager · PythonRuntime        │
└────────────────────────────┬────────────────────────────────┘
                             │ stdin/stdout JSON-RPC (line-delimited)
┌────────────────────────────▼────────────────────────────────┐
│ Embedded Python Engine                                       │
│  engine (asyncio loop)                                       │
│  ipc/jsonrpc (framing + dispatch)                            │
│  download (queue · task · manager · strategy)                │
│  providers (registry + per-platform modules)                 │
│  media (ffmpeg) · storage · database · utils                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Why three layers?

- **Flutter** gives a premium cross-UI toolkit with Material 3 fidelity and a
  rich animation system, with a single codebase for phone/tablet/foldable.
- **Kotlin native** owns the things Flutter cannot do alone: foreground
  services, WorkManager, notifications, fine-grained storage, and hosting a
  long-lived child process (the Python runtime) whose lifecycle is bound to
  the foreground service.
- **Python** owns the media domain: `yt-dlp`, `gallery-dl`, `Instaloader`, and
  `FFmpeg` are mature, actively-maintained, and battle-tested. Reimplementing
  their extraction logic in Dart/Kotlin would be wasteful and fragile.

### 2.2 Why a child process instead of embedding Python in-process?

An out-of-process Python runtime (`python -m mediahub_engine`) gives:

1. **Crash isolation.** A provider bug cannot ANR or crash the UI.
2. **Independent lifecycle.** The engine survives Activity recreation and can
   be restarted on demand.
3. **Deterministic IPC.** JSON-RPC over stdio is platform-agnostic and easy to
   test in isolation.
4. **Memory budgeting.** The OS can page the heavy media process independently.

## 3. Flutter layer — Clean Architecture + MVVM

```
lib/
├── app/                       # Application shell
│   ├── app.dart               # MaterialApp.router entry
│   ├── router.dart            # GoRouter configuration
│   └── theme/                 # Material 3 theming
├── core/                      # Cross-cutting concerns
│   ├── config/                # AppConfig, build flags
│   ├── constants/             # AppConstants
│   ├── errors/                # Failure / Exception taxonomy
│   ├── result/                # Result<T> sealed type
│   ├── platform/              # Method-channel abstraction
│   └── utils/                 # Pure helpers
├── features/                  # Feature modules (slices)
│   └── <feature>/
│       ├── domain/            # entities, usecases, repo interfaces
│       ├── data/              # repo impls, datasources, DTOs
│       └── presentation/      # screens, widgets, viewmodels
├── services/                  # App-wide services (engine, storage)
├── repositories/              # Cross-feature repository impls
├── providers/                 # Global Riverpod providers
├── models/                    # Shared domain models
└── shared/                    # Reusable widgets, extensions
```

### 3.1 Dependency rule

`presentation → domain ← data`. Dependencies point inward toward the domain.
The domain layer has zero Flutter imports except `meta`/`equatable`-style
pure-Dart packages. `data` implements `domain` interfaces; `presentation`
consumes `domain` usecases through Riverpod providers.

### 3.2 State management

Riverpod 2.x with code generation (`riverpod_generator`). Each feature exposes:

- A **Notifier** (view-model) owning UI state.
- A **Provider** exposing the notifier.
- **Repository providers** injected into notifiers for testability.

### 3.3 Routing

GoRouter with a single `GoRouter` instance, declarative redirect guards for
first-run / permissions, and shell routes for the bottom-nav scaffold.

## 4. Android native layer (Kotlin)

```
android/app/src/main/kotlin/com/mediahub/app/
├── MediaHubApplication.kt     # DI bootstrap, channel registration
├── MainActivity.kt            # FlutterActivity + engine wiring
├── bridge/                    # Method channel contract + handlers
│   ├── MethodChannelContract.kt
│   └── EngineMethodChannel.kt
├── runtime/                   # Python child-process lifecycle
│   ├── PythonRuntime.kt
│   └── PythonRuntimeConfig.kt
├── services/                  # Foreground + scheduled work
│   ├── DownloadForegroundService.kt
│   └── ServiceActions.kt
├── storage/                   # StoragePaths, SAF helpers
└── notifications/             # NotificationChannels, builders
```

### 4.1 Foreground service as engine host

`DownloadForegroundService` is the only long-lived component. It:

1. Acquires a foreground notification (required for background execution on
   Android 14+).
2. Starts the `PythonRuntime` child process on first command.
3. Routes method-channel calls to the engine via JSON-RPC.
4. Survives Activity recreation and app swiping-away (until the user stops it).

### 4.2 Method channel contract

A single channel `com.mediahub.app/engine` carries typed, versioned calls. The
contract is mirrored in Dart (`EngineMethodChannel`) and Kotlin
(`MethodChannelContract`). Every call carries a `bridgeVersion` field so
mismatched layers fail loudly. See `docs/BRIDGE_CONTRACT.md`.

## 5. Python engine

```
python_engine/mediahub_engine/
├── __init__.py
├── __main__.py                # entry: asyncio.run(engine.main())
├── engine.py                  # Engine: owns loop, dispatch, providers
├── engine_kinds.py            # leaf module: EngineStrategy + EngineDecision
├── config.py                  # frozen dataclass config
├── contracts.py               # pydantic request/response models
├── ipc/
│   └── jsonrpc.py             # line-delimited JSON-RPC framing + dispatch
├── download/
│   ├── task.py                # DownloadTask model + lifecycle FSM
│   ├── queue.py               # priority queue + concurrency limiter
│   ├── manager.py             # DownloadManager: orchestrates tasks + backends
│   └── strategy.py            # engine-selection strategy (pick_engine)
├── providers/
│   ├── base.py                # Provider ABC + Capability + auth types
│   ├── delegate.py            # BackendDelegateProvider base
│   ├── registry.py            # ProviderRegistry: detect + route + describe
│   ├── strategy.py            # re-exports engine kinds
│   ├── generic.py             # fallback direct-URL HTTP provider
│   ├── backends/              # extraction engine wrappers
│   │   ├── base.py            # ExtractionBackend ABC + ExtractionResult
│   │   ├── registry.py        # BackendRegistry singleton
│   │   ├── ytdlp.py           # yt-dlp wrapper (lazy-import + thread pool)
│   │   ├── gallerydl.py       # gallery-dl wrapper
│   │   └── instaloader.py     # Instaloader wrapper
│   ├── youtube/               # per-platform provider modules
│   ├── instagram/
│   ├── facebook/
│   ├── tiktok/
│   ├── twitter_x/
│   ├── reddit/
│   ├── vimeo/
│   ├── dailymotion/
│   ├── pinterest/
│   ├── twitch/
│   ├── soundcloud/
│   ├── threads/
│   └── snapchat/
├── media/                     # FFmpeg wrappers (Phase 3+)
├── storage/                   # file manager, conflict resolution (Phase 4+)
├── database/                  # SQLite history/stats (Phase 4+)
└── utils/
    └── logging.py             # structured stderr logging
```

### 5.1 IPC protocol

Line-delimited JSON-RPC 2.0 over stdio:

- Kotlin writes one JSON request object terminated by `\n` to the engine's
  stdin.
- The engine writes one JSON response/notification object terminated by `\n`
  to stdout.
- Progress events are JSON-RPC **notifications** (no `id`), enabling streaming
  progress back to Flutter.

### 5.2 Provider model

Each provider implements `Provider` (ABC) and declares a `Capability`
descriptor: which URL patterns it handles, which extraction engine it prefers,
whether it supports auth, batch, subtitles, etc. The `ProviderRegistry` walks
providers in priority order and returns the first that `matches(url)`.

Adding a platform = creating `providers/<platform>/__init__.py` exporting a
`Provider` subclass and registering it in `registry.py`. No core changes.

## 6. Data & persistence

- **SQLite** (via `sqflite` on Flutter side, `sqlite3` on Python side) for
  downloads, history, stats, favorites, collections.
- **Hive** for lightweight encrypted key/value preferences.
- **File system** under app-specific external storage, with a per-provider
  folder hierarchy and a recycle bin.

## 7. Security

- Encrypted local storage (Hive encrypted box / EncryptedSharedPreferences).
- No hardcoded secrets; all credentials live in Android Keystore-backed prefs.
- Strict input validation at every bridge boundary (pydantic on Python,
  typed DTOs + `Result` on Dart).
- R8 + resource shrinking + obfuscation in release builds.
- Scoped storage only; no `MANAGE_EXTERNAL_STORAGE` in the default flavor.

## 8. Performance

- Lazy-loaded feature screens; GoRouter keeps back-stack lean.
- Riverpod auto-dispose for screen-scoped state.
- Python engine uses `ThreadPoolExecutor` for blocking extraction (yt-dlp is
  sync) while the asyncio loop stays responsive for IPC.
- All progress events are coalesced (≤ 4 Hz) before crossing the bridge.
- Image thumbnails are cached and decoded off the UI thread.

## 9. Build flavors

Two product flavors:

- `standard` — public store build, scoped storage, no root.
- `full` — enables advanced storage modes for power users (opt-in).

(Phase 2+ configures flavors in `android/app/build.gradle.kts`.)

## 10. Phase roadmap

| Phase | Scope |
|-------|-------|
| 1 | Foundation: skeleton, bridges, theming, docs, smoke tests |
| 2 | Provider system: 13 platform providers + yt-dlp/gallery-dl/instaloader backends + provider/download engine methods + Download Center UI |
| 3 | Download manager: concurrency control, pause/resume via cancellation tokens, retry with exponential backoff, SQLite persistence, partial-file recovery |
| 4 | Media library, file manager (rename/move/copy/delete/recycle), history + stats, favorites, collections, storage analyzer, duplicate finder |
| 5 | Players: video/audio playback, PiP, sleep timer, playlists (ordered queues with shuffle/repeat) |
| 6 | Settings (key-value store), scheduler (WorkManager + 4 schedule types), encrypted credentials (Android Keystore), troubleshooting guide, release-ready |
