import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/media_library_models.dart';
import '../../../services/engine_service.dart';

/// The playback status of the current track.
enum PlayerStatus { idle, loading, playing, paused, completed, error }

/// [RepeatMode] is imported from [media_library_models.dart] to avoid a
/// duplicate definition. Both the player and the playlist system share it.

/// Immutable playback state.
@immutable
class PlayerState {
  const PlayerState({
    this.queue = const [],
    this.currentIndex = 0,
    this.status = PlayerStatus.idle,
    this.position = Duration.zero,
    this.duration = Duration.zero,
    this.speed = 1.0,
    this.shuffle = false,
    this.repeatMode = RepeatMode.off,
    this.sleepTimerRemaining,
    this.error,
  });

  final List<MediaItem> queue;
  final int currentIndex;
  final PlayerStatus status;
  final Duration position;
  final Duration duration;
  final double speed;
  final bool shuffle;
  final RepeatMode repeatMode;
  final Duration? sleepTimerRemaining;
  final String? error;

  MediaItem? get currentTrack =>
      queue.isNotEmpty && currentIndex < queue.length ? queue[currentIndex] : null;

  bool get isPlaying => status == PlayerStatus.playing;
  bool get hasQueue => queue.isNotEmpty;

  PlayerState copyWith({
    List<MediaItem>? queue,
    int? currentIndex,
    PlayerStatus? status,
    Duration? position,
    Duration? duration,
    double? speed,
    bool? shuffle,
    RepeatMode? repeatMode,
    Duration? sleepTimerRemaining,
    bool clearSleepTimer = false,
    String? error,
    bool clearError = false,
  }) {
    return PlayerState(
      queue: queue ?? this.queue,
      currentIndex: currentIndex ?? this.currentIndex,
      status: status ?? this.status,
      position: position ?? this.position,
      duration: duration ?? this.duration,
      speed: speed ?? this.speed,
      shuffle: shuffle ?? this.shuffle,
      repeatMode: repeatMode ?? this.repeatMode,
      sleepTimerRemaining:
          clearSleepTimer ? null : (sleepTimerRemaining ?? this.sleepTimerRemaining),
      error: clearError ? null : (error ?? this.error),
    );
  }
}

/// The playback engine: manages the queue, current track, play/pause/seek/
/// skip, repeat/shuffle, playback speed, and sleep timer.
///
/// The actual media playback is delegated to a [PlayerBackend] which wraps
/// the platform video/audio player. In production this uses `video_player`
/// (video) or `just_audio` (audio). In tests, a [FakePlayerBackend] is
/// injected.
abstract class PlayerBackend {
  /// Loads [path] and prepares for playback at [speed].
  Future<void> load(String path, {double speed = 1.0});

  /// Starts playback.
  Future<void> play();

  /// Pauses playback.
  Future<void> pause();

  /// Seeks to [position].
  Future<void> seek(Duration position);

  /// Sets the playback speed (0.25–4.0).
  Future<void> setSpeed(double speed);

  /// Releases resources.
  Future<void> dispose();

  /// Stream of position updates.
  Stream<Duration> get positionStream;

  /// Stream of duration updates.
  Stream<Duration> get durationStream;

  /// Stream of completion events.
  Stream<void> get completionStream;
}

/// Riverpod provider for the [PlayerBackend]. Overridden in tests.
final Provider<PlayerBackend> playerBackendProvider =
    Provider<PlayerBackend>(
  (ref) => throw UnimplementedError(
    'playerBackendProvider must be overridden with a real or fake backend',
  ),
  name: 'playerBackendProvider',
);

/// The playback notifier — the heart of the player.
class PlayerNotifier extends StateNotifier<PlayerState> {
  PlayerNotifier(this._backend) : super(const PlayerState()) {
    _positionSub = _backend.positionStream.listen((pos) {
      state = state.copyWith(position: pos);
    });
    _durationSub = _backend.durationStream.listen((dur) {
      state = state.copyWith(duration: dur);
    });
    _completionSub = _backend.completionStream.listen((_) {
      _onTrackComplete();
    });
  }

  final PlayerBackend _backend;
  late final StreamSubscription<Duration> _positionSub;
  late final StreamSubscription<Duration> _durationSub;
  late final StreamSubscription<void> _completionSub;
  Timer? _sleepTimer;

  /// Loads a queue of media items and starts playback at [startIndex].
  Future<void> playQueue(List<MediaItem> items, {int startIndex = 0}) async {
    if (items.isEmpty) return;
    state = state.copyWith(
      queue: items,
      currentIndex: startIndex,
      status: PlayerStatus.loading,
      clearError: true,
      position: Duration.zero,
      duration: Duration.zero,
    );
    await _loadCurrent();
    await _backend.play();
    state = state.copyWith(status: PlayerStatus.playing);
  }

  /// Plays a single media item.
  Future<void> playItem(MediaItem item) async {
    await playQueue([item]);
  }

  /// Resumes playback.
  Future<void> play() async {
    if (state.status == PlayerStatus.playing) return;
    await _backend.play();
    state = state.copyWith(status: PlayerStatus.playing);
  }

  /// Pauses playback.
  Future<void> pause() async {
    await _backend.pause();
    state = state.copyWith(status: PlayerStatus.paused);
  }

  /// Toggles play/pause.
  Future<void> togglePlayPause() async {
    if (state.isPlaying) {
      await pause();
    } else {
      await play();
    }
  }

  /// Seeks to [position].
  Future<void> seek(Duration position) async {
    await _backend.seek(position);
    state = state.copyWith(position: position);
  }

  /// Skips to the next track (respecting repeat mode).
  Future<void> skipNext() async {
    if (state.queue.isEmpty) return;
    int nextIndex;
    if (state.repeatMode == RepeatMode.one) {
      nextIndex = state.currentIndex;
    } else if (state.shuffle) {
      nextIndex = _randomIndex();
    } else {
      nextIndex = state.currentIndex + 1;
      if (nextIndex >= state.queue.length) {
        if (state.repeatMode == RepeatMode.all) {
          nextIndex = 0;
        } else {
          state = state.copyWith(status: PlayerStatus.completed);
          return;
        }
      }
    }
    state = state.copyWith(
      currentIndex: nextIndex,
      status: PlayerStatus.loading,
      position: Duration.zero,
      duration: Duration.zero,
    );
    await _loadCurrent();
    await _backend.play();
    state = state.copyWith(status: PlayerStatus.playing);
  }

  /// Skips to the previous track.
  Future<void> skipPrevious() async {
    if (state.queue.isEmpty) return;
    int prevIndex;
    if (state.shuffle) {
      prevIndex = _randomIndex();
    } else {
      prevIndex = state.currentIndex - 1;
      if (prevIndex < 0) {
        if (state.repeatMode == RepeatMode.all) {
          prevIndex = state.queue.length - 1;
        } else {
          prevIndex = 0;
        }
      }
    }
    state = state.copyWith(
      currentIndex: prevIndex,
      status: PlayerStatus.loading,
      position: Duration.zero,
      duration: Duration.zero,
    );
    await _loadCurrent();
    await _backend.play();
    state = state.copyWith(status: PlayerStatus.playing);
  }

  /// Sets the playback speed (0.25–4.0).
  Future<void> setSpeed(double speed) async {
    final clamped = speed.clamp(0.25, 4.0);
    await _backend.setSpeed(clamped);
    state = state.copyWith(speed: clamped);
  }

  /// Toggles shuffle mode.
  void toggleShuffle() {
    state = state.copyWith(shuffle: !state.shuffle);
  }

  /// Cycles repeat mode: off → all → one → off.
  void cycleRepeatMode() {
    final next = switch (state.repeatMode) {
      RepeatMode.off => RepeatMode.all,
      RepeatMode.all => RepeatMode.one,
      RepeatMode.one => RepeatMode.off,
    };
    state = state.copyWith(repeatMode: next);
  }

  /// Starts a sleep timer that pauses playback after [duration].
  void startSleepTimer(Duration duration) {
    _sleepTimer?.cancel();
    state = state.copyWith(sleepTimerRemaining: duration);
    var remaining = duration;
    _sleepTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      remaining -= const Duration(seconds: 1);
      if (remaining <= Duration.zero) {
        timer.cancel();
        pause();
        state = state.copyWith(clearSleepTimer: true);
      } else {
        state = state.copyWith(sleepTimerRemaining: remaining);
      }
    });
  }

  /// Cancels the active sleep timer.
  void cancelSleepTimer() {
    _sleepTimer?.cancel();
    _sleepTimer = null;
    state = state.copyWith(clearSleepTimer: true);
  }

  /// Stops playback and clears the queue.
  Future<void> stop() async {
    await _backend.pause();
    _sleepTimer?.cancel();
    state = const PlayerState();
  }

  void _onTrackComplete() {
    if (state.repeatMode == RepeatMode.one) {
      seek(Duration.zero);
      play();
    } else {
      skipNext();
    }
  }

  Future<void> _loadCurrent() async {
    final track = state.currentTrack;
    if (track == null) {
      state = state.copyWith(status: PlayerStatus.error, error: 'No track');
      return;
    }
    try {
      await _backend.load(track.path, speed: state.speed);
    } catch (e) {
      state = state.copyWith(status: PlayerStatus.error, error: e.toString());
    }
  }

  int _randomIndex() {
    if (state.queue.length <= 1) return state.currentIndex;
    final rng = DateTime.now().millisecondsSinceEpoch;
    var idx = rng % state.queue.length;
    if (idx == state.currentIndex) {
      idx = (idx + 1) % state.queue.length;
    }
    return idx;
  }

  @override
  void dispose() {
    _sleepTimer?.cancel();
    _positionSub.cancel();
    _durationSub.cancel();
    _completionSub.cancel();
    _backend.dispose();
    super.dispose();
  }
}

final StateNotifierProvider<PlayerNotifier, PlayerState> playerProvider =
    StateNotifierProvider<PlayerNotifier, PlayerState>(
  (ref) => PlayerNotifier(ref.watch(playerBackendProvider)),
  name: 'playerProvider',
);
