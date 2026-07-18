# Provider System

This document describes the MediaHub provider architecture: how platforms are
detected, how extraction is delegated to backends, and how to add a new
platform.

> Authoritative for Phase 2. Mirrored in code at `python_engine/mediahub_engine/providers/`.

## 1. Overview

```
URL  ──►  ProviderRegistry.find(url)  ──►  Provider (platform-specific)
                                              │
                                              ▼
                                      BackendDelegateProvider
                                              │ delegates to
                                              ▼
                                      ExtractionBackend
                                        (yt-dlp | gallery-dl | instaloader)
                                              │
                                              ▼
                                      ProviderResult (files + metadata)
```

- **Provider** — declares a `Capability` (name, engine, URL patterns, features,
  auth requirement) and implements `matches()`, `extract_metadata()`,
  `download()`.
- **BackendDelegateProvider** — a base class that delegates `extract_metadata`
  and `download` to a backend chosen by `backend_strategy`. Most providers
  subclass this; the generic HTTP provider subclasses `Provider` directly.
- **ExtractionBackend** — wraps a concrete engine library (yt-dlp,
  gallery-dl, instaloader). Lazy-imports its library so the engine boots even
  when the library is absent.
- **BackendRegistry** — maps `EngineStrategy` → backend instance.
- **ProviderRegistry** — ordered list of providers; `find(url)` returns the
  first whose `matches()` returns `True`. The generic provider is always last.

## 2. Built-in providers (Phase 2)

| Provider | Engine | Auth | Batch | Notes |
|----------|--------|------|-------|-------|
| youtube | yt-dlp | no | 50 | videos, shorts, playlists, music |
| instagram | gallery-dl | optional | 20 | posts, reels, stories |
| facebook | yt-dlp | optional | 1 | videos, reels, watch links |
| tiktok | yt-dlp | no | 30 | watermark-free when available |
| twitter_x | yt-dlp | **required** | 20 | videos, GIFs |
| reddit | yt-dlp | no | 1 | videos, GIFs |
| vimeo | yt-dlp | optional | 1 | videos |
| dailymotion | yt-dlp | no | 1 | videos |
| pinterest | gallery-dl | no | 50 | pins, boards |
| twitch | yt-dlp | no | 1 | clips, VODs (no live in Phase 2) |
| soundcloud | yt-dlp | no | 50 | tracks, playlists |
| threads | gallery-dl | no | 20 | posts |
| snapchat | gallery-dl | no | 1 | spotlights, stories |
| generic | http | no | 1 | fallback for direct media URLs |

## 3. Detection

Each provider declares `url_patterns` — substrings matched against the URL.
The registry walks providers in registration order (specialized first, generic
last) and returns the first match. A test (`test_no_provider_overlap_on_sample_urls`)
guards against two providers claiming the same URL.

Providers may override `matches()` for custom logic (the generic provider does
this to require a media file extension).

## 4. Backends

### 4.1 yt-dlp (`YtDlpBackend`)

- Lazy-imports `yt_dlp`.
- `extract_metadata` → `YoutubeDL.extract_info(url, download=False)`.
- `download` → `YoutubeDL.extract_info(url, download=True)` with progress hooks
  that forward to the `DownloadSink`.
- All blocking calls run in a `ThreadPoolExecutor` (2 workers) so the asyncio
  loop stays responsive.
- Normalizes the yt-dlp info dict into `MediaMetadata` + a list of `FormatOption`s
  (resolution, codecs, filesize, audio-only flag).

### 4.2 gallery-dl (`GalleryDlBackend`)

- Lazy-imports `gallery_dl`.
- Runs a `UrlJob` (metadata) or `DownloadJob` (download) in a thread.
- Collects per-item metadata into `ExtractionResult.metadata` with `item_count`
  for galleries.
- Supports `cookiefile` for authenticated extraction.

### 4.3 Instaloader (`InstaloaderBackend`)

- Lazy-imports `instaloader`.
- Extracts the shortcode from the URL, loads the `Post`, and downloads via
  `Instaloader.download_post`.
- Supports `username`/`password` login or a saved `sessionfile`.

### 4.4 Availability

Every backend reports `is_available()` (True iff its library imports). The
`BackendDelegateProvider` raises `BackendNotAvailableError` when a backend is
unavailable, which surfaces to the user as a clear error rather than a crash.

## 5. Authentication

- `Credential` — username, password, cookies_path, session_path, token.
- `CredentialStore` (Protocol) — `get(provider_name) -> Credential | None`.
- `InMemoryCredentialStore` — default; Phase 6 wires an encrypted persistent
  store backed by Android Keystore.
- `BackendDelegateProvider` injects credentials into backend options
  (`username`, `password`, `cookiefile`, `sessionfile`).
- Providers declare `auth_required` in their `Capability`; the UI shows an
  "auth" badge and (Phase 6) prompts for credentials.

## 6. Adding a new platform

1. Create `providers/<platform>/__init__.py` and `providers/<platform>/provider.py`.
2. Subclass `BackendDelegateProvider`, set `capability` and `backend_strategy`.
3. Register it in `providers/registry.py::_bootstrap` (before the generic
   provider).
4. Add detection + delegation tests in `tests/test_providers.py`.

That's it. No core download logic changes. Example:

```python
class MyPlatformProvider(BackendDelegateProvider):
    capability = Capability(
        name="myplatform",
        engine="yt-dlp",
        display_name="MyPlatform",
        url_patterns=("myplatform.com/watch", "mp.watch/"),
        features=ProviderFeature.SINGLE | ProviderFeature.METADATA,
        auth_required=False,
        max_batch=1,
    )
    backend_strategy = EngineStrategy.YTDLP
```

## 7. Engine method surface (Phase 2)

| Method | Params | Returns |
|--------|--------|---------|
| `provider.detect` | `{url}` | `{provider, displayName, engine, authRequired, maxBatch}` |
| `provider.metadata` | `{url}` | `{title, uploader, durationSeconds, thumbnailUrl, ...}` |
| `provider.list` | `{}` | `{providers: [CapabilityDescriptor]}` |
| `download.enqueue` | `{url, options?, priority?, destDir?}` | `{taskId, state}` |
| `download.cancel` | `{taskId}` | `{taskId, cancelled}` |
| `download.list` | `{}` | `{tasks: [TaskDict]}` |
| `download.status` | `{taskId}` | `TaskDict` |

Notifications (no `id`): `download.enqueued`, `download.started`,
`download.progress`, `download.completed`, `download.failed`,
`download.cancelled`.

See `docs/BRIDGE_CONTRACT.md` for the full wire format.
