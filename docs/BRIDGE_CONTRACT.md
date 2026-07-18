# Bridge Contract

MediaHub has two typed bridges. This document is the authoritative contract for
both. **Any change here is a breaking change unless additive.**

| Bridge | Direction | Transport | Versioned by |
|--------|-----------|-----------|--------------|
| Method Channel | Flutter ↔ Kotlin | `MethodChannel` (`com.mediahub.app/engine`) | `bridgeVersion` |
| JSON-RPC | Kotlin ↔ Python | line-delimited JSON-RPC 2.0 over stdio | `jsonrpc` field in payloads |

## 1. Method Channel — Flutter ↔ Kotlin

### 1.1 Channel

```
name: com.mediahub.app/engine
codec: StandardMethodCodec
```

### 1.2 Envelope

Every method call carries a single `Map<String, Object?>` argument:

```json
{
  "bridgeVersion": 1,
  "callId": "uuid-v4",
  "method": "<method.name>",
  "params": { ... }
}
```

Every success result is a `Map`:

```json
{
  "bridgeVersion": 1,
  "callId": "<same>",
  "ok": true,
  "data": { ... }
}
```

Every error result is a `Map` (also returned via `error` codec path):

```json
{
  "bridgeVersion": 1,
  "callId": "<same>",
  "ok": false,
  "error": {
    "code": "ENGINE_NOT_READY",
    "message": "Python runtime is not running",
    "details": { ... }
  }
}
```

### 1.3 Event stream

A separate `EventChannel` `com.mediahub.app/engine/events` streams engine
notifications (progress, state changes) as the same envelope map with no
`callId`:

```json
{
  "bridgeVersion": 1,
  "event": "download.progress",
  "data": { "taskId": "...", "percent": 42.0, "bytes": 12345 }
}
```

### 1.4 Methods

#### engine.* (Phase 1)

| Method | Params | Returns | Notes |
|--------|--------|---------|-------|
| `engine.ping` | `{}` | `{ "pong": true, "version": "0.1.0" }` | Health check; starts runtime if needed. |
| `engine.version` | `{}` | `{ "app": "0.1.0", "engine": "0.1.0", "bridgeVersion": 1 }` | Versions across layers. |
| `engine.shutdown` | `{}` | `{ "stopped": true }` | Graceful engine stop. |

#### provider.* (Phase 2)

| Method | Params | Returns | Notes |
|--------|--------|---------|-------|
| `provider.detect` | `{ url }` | `{ provider, displayName, engine, authRequired, maxBatch }` | Detects the platform; returns `PROVIDER_NOT_FOUND` if none matches. |
| `provider.metadata` | `{ url }` | `{ title, uploader, durationSeconds, thumbnailUrl, categories, tags, extra, provider, engine }` | Fetches normalized metadata. |
| `provider.list` | `{}` | `{ providers: [CapabilityDescriptor] }` | Lists every registered provider. |

`CapabilityDescriptor`:
```json
{
  "name": "youtube",
  "displayName": "YouTube",
  "engine": "yt-dlp",
  "authRequired": false,
  "maxBatch": 50,
  "features": ["SINGLE", "BATCH", "SUBTITLES", ...],
  "urlPatterns": ["youtube.com/watch", "youtu.be/", ...]
}
```

#### download.* (Phase 2)

| Method | Params | Returns | Notes |
|--------|--------|---------|-------|
| `download.enqueue` | `{ url, options?, priority?, destDir? }` | `{ taskId, state }` | Enqueues a download. `priority` is a `TaskPriority` int. |
| `download.pause` | `{ taskId }` | `{ taskId, paused }` | Pauses an active or queued task. |
| `download.resume` | `{ taskId }` | `{ taskId, resumed }` | Resumes a paused task. |
| `download.retry` | `{ taskId }` | `{ taskId, retried }` | Manually retries a failed task (resets retry budget). |
| `download.cancel` | `{ taskId }` | `{ taskId, cancelled }` | `cancelled` is `false` if the task was already terminal. |
| `download.list` | `{}` | `{ tasks: [TaskDict] }` | All tasks (active + terminal). |
| `download.status` | `{ taskId }` | `TaskDict` | Single task snapshot. |
| `download.clear` | `{}` | `{ cleared: int }` | Removes all terminal tasks from the queue and database. |

`TaskDict`:
```json
{
  "taskId": "...",
  "url": "...",
  "state": "queued|active|paused|completed|failed|cancelled",
  "priority": 5,
  "percent": 42.0,
  "bytes": 12345,
  "total": 98765,
  "outputPath": "/path/primary.mp4",
  "outputPaths": ["/path/primary.mp4", "/path/subtitle.srt"],
  "provider": "youtube",
  "engine": "yt-dlp",
  "metadata": { "title": "...", "uploader": "..." },
  "error": null,
  "lastError": null,
  "retries": 0,
  "retryAfter": null,
  "elapsed": 3.21
}
```

#### Download notifications (Phase 2 + 3, streamed via the event channel)

| Event | Data |
|-------|------|
| `download.enqueued` | `{ taskId, url }` |
| `download.started` | `{ taskId, provider, engine }` |
| `download.progress` | `{ taskId, percent, bytes, total }` |
| `download.completed` | `{ taskId, paths, path, bytes }` |
| `download.failed` | `{ taskId, error }` |
| `download.cancelled` | `{ taskId }` |
| `download.paused` | `{ taskId }` |
| `download.resumed` | `{ taskId }` |
| `download.retry_scheduled` | `{ taskId, attempt, delaySeconds }` |

#### library.* / favorites.* / collections.* / history.* / file.* / storage.* (Phase 4)

See `docs/MEDIA_LIBRARY.md` for the full Phase 4 method tables. Summary:

- **library.** — `list`, `search`, `item`, `count` (browse/filter/search media)
- **favorites.** — `add`, `remove`, `list` (toggle + browse favorites)
- **collections.** — `create`, `list`, `rename`, `delete`, `add_item`,
  `remove_item`, `items` (user-defined groups)
- **history.** — `list`, `stats`, `clear` (append-only log + aggregate stats)
- **file.** — `rename`, `move`, `copy`, `recycle`, `restore`, `delete`,
  `empty_recycle` (file manager + recycle bin)
- **storage.** — `analyze`, `duplicates` (storage analyzer + duplicate finder)

All Phase 4 methods require persistence enabled (`persist_downloads=True`).

#### playlists.* (Phase 5)

| Method | Params | Returns | Notes |
|--------|--------|---------|-------|
| `playlists.create` | `name, description?` | `Playlist` | Creates a new playlist. |
| `playlists.list` | `{}` | `{playlists: [Playlist]}` | Lists all playlists. |
| `playlists.rename` | `playlistId, name, description?` | `{renamed}` | Renames a playlist. |
| `playlists.delete` | `playlistId` | `{deleted}` | Deletes a playlist (cascades items). |
| `playlists.add_item` | `playlistId, itemId, position?` | `{added}` | Adds an item at position (or appends). |
| `playlists.remove_item` | `playlistId, itemId` | `{removed}` | Removes + re-indexes positions. |
| `playlists.reorder` | `playlistId, itemId, position` | `{reordered}` | Moves an item to a new position. |
| `playlists.items` | `playlistId` | `{items: [MediaItem]}` | Returns items in playback order. |
| `playlists.set_shuffle` | `playlistId, shuffle` | `{updated}` | Toggles shuffle. |
| `playlists.set_repeat` | `playlistId, repeatMode` | `{updated}` | Sets repeat mode (off/all/one). |

`Playlist`:
```json
{
  "playlistId": "...",
  "name": "...",
  "description": "",
  "itemCount": 0,
  "shuffle": false,
  "repeatMode": "off|all|one",
  "createdAt": 1.0,
  "updatedAt": 1.0
}
```

Future phases add `media.*` (FFmpeg processing) — see the phase roadmap.
Methods are namespaced `domain.action` to keep the contract flat and grep-able.

#### settings.* / scheduler.* / credentials.* (Phase 6)

##### settings.*

| Method | Params | Returns | Notes |
|--------|--------|---------|-------|
| `settings.get` | `key` | `{key, value}` | Returns default if unset. |
| `settings.get_all` | `{}` | `{settings: {key: value, ...}}` | Merged with defaults. |
| `settings.set` | `key, value` | `{key, updated}` | Upserts a setting. |
| `settings.set_many` | `settings: {k: v}` | `{updated: int}` | Batch upsert. |
| `settings.delete` | `key` | `{key, deleted}` | Removes a setting (reverts to default). |
| `settings.reset` | `{}` | `{reset}` | Clears all stored settings. |

##### scheduler.*

| Method | Params | Returns | Notes |
|--------|--------|---------|-------|
| `scheduler.create` | `url, scheduleType, scheduledAt?, intervalSeconds?, hour?, minute?, dayOfWeek?, priority?, options?, enabled?` | `ScheduledTask` | Creates a schedule. |
| `scheduler.list` | `enabledOnly?` | `{schedules: [ScheduledTask]}` | Lists schedules. |
| `scheduler.get` | `scheduleId` | `ScheduledTask` | Single schedule. |
| `scheduler.update` | `scheduleId, ...` | `ScheduledTask` | Updates fields. |
| `scheduler.set_enabled` | `scheduleId, enabled` | `{updated}` | Enable/disable. |
| `scheduler.delete` | `scheduleId` | `{deleted}` | Deletes a schedule. |
| `scheduler.due` | `{}` | `{schedules: [ScheduledTask]}` | Returns enabled schedules whose `nextRunAt` has elapsed. |
| `scheduler.mark_run` | `scheduleId` | `ScheduledTask` | Records a run; advances `nextRunAt` for recurring; disables one-time. |

`scheduleType`: `one_time | interval | daily | weekly`

##### credentials.*

| Method | Params | Returns | Notes |
|--------|--------|---------|-------|
| `credentials.set` | `provider, username?, password?, cookiesPath?, sessionPath?, token?` | `{provider, updated}` | Stores encrypted credentials. |
| `credentials.get` | `provider` | `{provider, credential: {username, cookiesPath, sessionPath, hasPassword, hasToken} | null}` | **Never** returns the password/token in plaintext. |
| `credentials.list` | `{}` | `{providers: [string]}` | Lists providers with stored credentials. |
| `credentials.delete` | `provider` | `{provider, deleted}` | Removes credentials. |
| `credentials.has` | `provider` | `{provider, has}` | Checks existence. |

Credentials (passwords, tokens) are encrypted at rest via Android Keystore
(production) or a DB-path-derived key (dev). The `credentials.get` method
intentionally omits the password — it returns only `hasPassword: true`.

### 1.5 Error codes

| Code | Meaning |
|------|---------|
| `BRIDGE_VERSION_MISMATCH` | `bridgeVersion` differs from the receiver's. |
| `UNKNOWN_METHOD` | Method not registered. |
| `INVALID_PARAMS` | Params failed validation. |
| `ENGINE_NOT_READY` | Python runtime not started / crashed. |
| `ENGINE_TIMEOUT` | No response within timeout. |
| `PROVIDER_NOT_FOUND` | No provider matched the URL. |
| `INTERNAL` | Unhandled internal error (details scrubbed in release). |

## 2. JSON-RPC — Kotlin ↔ Python

### 2.1 Framing

- One JSON object per line, UTF-8, terminated by `\n`.
- No embedded newlines in the JSON (they'd break framing); the encoder
  guarantees compact output with escaped control chars.

### 2.2 Request (Kotlin → Python)

```json
{"jsonrpc":"2.0","id":1,"method":"engine.ping","params":{}}
```

`id` is a monotonic integer per runtime session. The engine MUST respond with
the same `id`.

### 2.3 Response (Python → Kotlin)

```json
{"jsonrpc":"2.0","id":1,"result":{"pong":true,"version":"0.1.0"}}
```

Error:

```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32001,"message":"...","data":{}}}
```

JSON-RPC error codes in the `-32xxx` range are reserved by the spec. MediaHub
application codes start at `-1` and mirror the bridge error names:

| Code | Name |
|------|------|
| -1 | `UNKNOWN_METHOD` |
| -2 | `INVALID_PARAMS` |
| -3 | `PROVIDER_NOT_FOUND` |
| -4 | `ENGINE_TIMEOUT` |
| -5 | `INTERNAL` |

### 2.4 Notifications (Python → Kotlin, no `id`)

```json
{"jsonrpc":"2.0","method":"download.progress","params":{"taskId":"...","percent":42.0}}
```

Notifications are fire-and-forget; the engine MUST NOT expect an ack.

### 2.5 Logging

The engine writes structured logs to **stderr** only. stdout is reserved
exclusively for JSON-RPC. Kotlin captures stderr for diagnostics.

## 3. Versioning & compatibility

- `bridgeVersion` is bumped on **any** breaking change to the method-channel
  envelope or method set. Both sides reject mismatched versions loudly.
- The JSON-RPC method set is additive across phases; removals require a
  `bridgeVersion` bump.
- Additive changes (new methods, new optional params) do not require a bump.

## 4. Reference implementations

- Dart: `lib/core/platform/method_channels/engine_method_channel.dart`
- Kotlin: `android/app/src/main/kotlin/com/mediahub/app/bridge/MethodChannelContract.kt`
- Python: `python_engine/mediahub_engine/ipc/jsonrpc.py`
