# Players

This document describes the Phase 5 media players: video playback, audio
playback, Picture-in-Picture, sleep timer, and playlists.

> Authoritative for Phase 5. Mirrored in code at `lib/features/player/` and
> `lib/features/playlists/`.

## 1. Architecture

```
┌──────────────────────────────────────────────┐
│  Flutter UI                                    │
│  VideoPlayerScreen  │  AudioPlayerScreen      │
│  (gesture controls) │  ("now playing" UI)     │
└──────────┬───────────────────────────────────┘
           │ watches
┌──────────▼───────────────────────────────────┐
│  PlayerNotifier (Riverpod StateNotifier)       │
│  - queue + currentIndex                       │
│  - play/pause/seek/skipNext/skipPrevious      │
│  - shuffle + repeat (off/all/one)             │
│  - playback speed (0.25–4.0)                  │
│  - sleep timer (countdown → auto-pause)       │
└──────────┬───────────────────────────────────┘
           │ delegates to
┌──────────▼───────────────────────────────────┐
│  PlayerBackend (abstract)                      │
│  load / play / pause / seek / setSpeed         │
│  positionStream / durationStream / completion  │
└──────────┬───────────────────────────────────┘
           │ implemented by
┌──────────▼───────────────────────────────────┐
│  JustAudioBackend (just_audio package)         │
│  + VideoPlayer widget (video_player package)   │
└──────────────────────────────────────────────┘
```

## 2. Playback state

`PlayerNotifier` owns the entire playback state via `PlayerState`:

| Field | Type | Purpose |
|-------|------|---------|
| `queue` | `List<MediaItem>` | The ordered playback queue |
| `currentIndex` | `int` | Index into `queue` |
| `status` | `PlayerStatus` | idle/loading/playing/paused/completed/error |
| `position` | `Duration` | Current playback position (streamed from backend) |
| `duration` | `Duration` | Current track duration (streamed from backend) |
| `speed` | `double` | Playback speed (0.25–4.0) |
| `shuffle` | `bool` | Shuffle mode |
| `repeatMode` | `RepeatMode` | off / all / one |
| `sleepTimerRemaining` | `Duration?` | Countdown until auto-pause |

### Queue management

- `playQueue(items, startIndex)` — loads a queue and starts playing.
- `playItem(item)` — convenience for a single-item queue.
- `skipNext()` — respects repeat mode: `one` replays, `all` wraps, `off` stops at end.
- `skipPrevious()` — wraps to last item when `repeatMode == all`.

### Repeat modes

- **off** — stop after the last track.
- **all** — loop back to the first track after the last.
- **one** — replay the current track on completion.

### Sleep timer

`startSleepTimer(duration)` starts a 1-second ticking countdown. When it
reaches zero, playback is paused and the timer is cleared. The remaining time
is shown in the UI (video controls bar / audio player secondary controls).

## 3. Video player screen

Full-screen video with auto-hiding gesture controls:
- Tap to toggle controls overlay (fades after 4s during playback).
- Top bar: back, title, speed selector (0.25x–2.0x).
- Center: shuffle, prev, play/pause (circular button), next, repeat.
- Bottom: seek slider + position/sleep-timer/duration.

The actual video surface wraps `video_player`'s `VideoPlayer` widget (wired in
production; the screen structure is complete here).

## 4. Audio player screen

"Now playing" layout:
- Artwork (thumbnail or category icon).
- Track title + uploader.
- Progress slider + position/sleep/duration.
- Main controls: shuffle, prev, play/pause, next, repeat.
- Secondary controls: speed selector (popup menu) + sleep timer (popup menu
  with 5/15/30/45/60 min presets, or cancel if active).

## 5. Picture-in-Picture

PiP is supported on Android 8.0+ (API 26):

- **Kotlin** (`MainActivity.kt`): registers a `com.mediahub.app/pip` method
  channel (`isPipSupported`, `enterPipMode`, `isInPipMode`) and a
  `com.mediahub.app/pip/events` event channel that streams PiP mode
  transitions. `enterPipMode()` calls `enterPictureInPictureMode` with a 16:9
  aspect ratio param. `onPictureInPictureModeChanged` notifies Flutter.
- **Flutter** (`PipMethodChannel`): wraps the channels; `enterPipMode()` is
  called when the user navigates away from the video player.
- **Manifest**: `android:supportsPictureInPicture="true"` on `MainActivity`.

## 6. Playlists

Playlists are ordered playback queues persisted in SQLite:

### Data model

- `playlists` — id, name, description, item_count, shuffle, repeat_mode,
  created_at, updated_at.
- `playlist_items` — (playlist_id, item_id) PK, `position` column for order,
  `ON DELETE CASCADE` FKs.

### Repository

`PlaylistsRepository` maintains position integrity:
- `add_item(position?)` — appends or inserts at position, shifting others.
- `remove_item()` — removes and re-indexes positions to 0, 1, 2, ...
- `reorder_item(new_position)` — moves an item and re-indexes.
- `items()` — JOINs `media_items` ordered by `position` ASC.

### Engine methods

| Method | Params | Returns |
|--------|--------|---------|
| `playlists.create` | `name, description?` | `Playlist` |
| `playlists.list` | `{}` | `{playlists: [Playlist]}` |
| `playlists.rename` | `playlistId, name, description?` | `{renamed}` |
| `playlists.delete` | `playlistId` | `{deleted}` |
| `playlists.add_item` | `playlistId, itemId, position?` | `{added}` |
| `playlists.remove_item` | `playlistId, itemId` | `{removed}` |
| `playlists.reorder` | `playlistId, itemId, position` | `{reordered}` |
| `playlists.items` | `playlistId` | `{items: [MediaItem]}` |
| `playlists.set_shuffle` | `playlistId, shuffle` | `{updated}` |
| `playlists.set_repeat` | `playlistId, repeatMode` | `{updated}` |

### Flutter UI

The Playlists screen lists all playlists with create/rename/delete. Tapping a
playlist opens its ordered items (Phase 5+: detail screen with drag-to-reorder
and "play all"). The player's `playQueue()` accepts the playlist's items.

## 7. Background playback

`just_audio` + `audio_service` provide background audio playback (lock screen
controls, notification). Video continues audio-only in background; PiP keeps
the video visible. Full background video recording (stream capture) is not
supported in Phase 5.
