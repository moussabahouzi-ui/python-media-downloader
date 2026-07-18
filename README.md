# MediaHub

> A premium, fully-local Android media downloader and media manager.
> Flutter UI · Kotlin native integration layer · Embedded Python media engine.

MediaHub is an offline-first Android application that combines a polished
Flutter interface with a powerful embedded Python media-processing engine.
The entire download stack runs on-device — there is **no external server**.

> ⚠️ **Verification status:** This repository is source-complete reference
> code. It is designed to be opened and built in a real Android development
> environment (Flutter SDK, Android Studio, Python toolchain). It is **not**
> compiled or executed by the authoring environment; see `docs/BUILD.md`.

---

## Architecture at a glance

```
┌──────────────────────────────────────────────┐
│  Flutter (Dart) — UI, state, navigation       │
│  Riverpod · GoRouter · Material 3 / Material You │
└───────────────────┬──────────────────────────┘
                    │ Method Channel (com.mediahub.app/engine)
┌───────────────────▼──────────────────────────┐
│  Android Native (Kotlin)                      │
│  Foreground Service · WorkManager · Storage   │
│  Notification Manager · Python Runtime Bridge │
└───────────────────┬──────────────────────────┘
                    │ stdin / stdout JSON-RPC (line-delimited)
┌───────────────────▼──────────────────────────┐
│  Embedded Python Engine                       │
│  yt-dlp · gallery-dl · Instaloader · FFmpeg   │
│  Provider Registry · Queue · Task Manager     │
└──────────────────────────────────────────────┘
```

## Repository layout

| Path          | Responsibility                                            |
|---------------|-----------------------------------------------------------|
| `lib/`        | Flutter application (Dart) — UI, state, domain, data      |
| `android/`    | Android native layer (Kotlin) — services, bridge, runtime |
| `python_engine/` | Embedded Python media engine                          |
| `docs/`       | Architecture, build, contribution, bridge contracts       |
| `test/`       | Flutter unit + widget tests                               |

## Key principles

1. **No external server.** Everything runs on-device.
2. **Modular providers.** Adding a platform = adding one provider module.
3. **Clean Architecture + MVVM.** Presentation / Domain / Data separation.
4. **Typed bridges.** Dart ↔ Kotlin ↔ Python contracts are versioned.
5. **Offline-first.** All state persists locally (SQLite/Hive).

## Phased build

MediaHub is built in phases. See `CHANGELOG.md` and `docs/ARCHITECTURE.md`.

- **Phase 1** — Foundation: project skeleton, bridges, theming, docs, smoke tests.

## License

Proprietary — see `LICENSE`.
