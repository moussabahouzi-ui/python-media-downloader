import 'dart:async';

import 'package:just_audio/just_audio.dart';

import '../providers/player_provider.dart';

/// Production [PlayerBackend] backed by `just_audio`.
///
/// `just_audio` handles both audio-only files and video file soundtracks
/// uniformly. For full video rendering (Phase 5+), a separate `VideoPlayer`
/// widget is used in the [VideoPlayerScreen]; this backend drives the audio
/// path and position/duration streams for both.
class JustAudioBackend implements PlayerBackend {
  JustAudioBackend() : _player = AudioPlayer();

  final AudioPlayer _player;
  StreamSubscription<Duration>? _posSub;
  StreamSubscription<Duration?>? _durSub;
  StreamSubscription<void>? _compSub;

  final _positionController = StreamController<Duration>.broadcast();
  final _durationController = StreamController<Duration>.broadcast();
  final _completionController = StreamController<void>.broadcast();

  @override
  Future<void> load(String path, {double speed = 1.0}) async {
    await _player.setFilePath(path);
    await _player.setSpeed(speed);
    _posSub ??= _player.positionStream.listen(_positionController.add);
    _durSub ??= _player.durationStream.listen((d) {
      if (d != null) _durationController.add(d);
    });
    _compSub ??= _player.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        _completionController.add(null);
      }
    });
  }

  @override
  Future<void> play() async => _player.play();

  @override
  Future<void> pause() async => _player.pause();

  @override
  Future<void> seek(Duration position) async => _player.seek(position);

  @override
  Future<void> setSpeed(double speed) async => _player.setSpeed(speed);

  @override
  Future<void> dispose() async {
    await _posSub?.cancel();
    await _durSub?.cancel();
    await _compSub?.cancel();
    await _player.dispose();
    await _positionController.close();
    await _durationController.close();
    await _completionController.close();
  }

  @override
  Stream<Duration> get positionStream => _positionController.stream;

  @override
  Stream<Duration> get durationStream => _durationController.stream;

  @override
  Stream<void> get completionStream => _completionController.stream;
}
