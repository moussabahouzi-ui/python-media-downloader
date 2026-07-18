import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../models/media_library_models.dart';
import '../providers/player_provider.dart';

/// Video player screen: full-screen video with gesture controls, playback
/// speed, sleep timer, and queue navigation.
class VideoPlayerScreen extends ConsumerStatefulWidget {
  const VideoPlayerScreen({super.key});

  @override
  ConsumerState<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends ConsumerState<VideoPlayerScreen> {
  bool _controlsVisible = true;

  @override
  void initState() {
    super.initState();
    _hideControlsAfterDelay();
  }

  void _hideControlsAfterDelay() {
    Future.delayed(const Duration(seconds: 4), () {
      if (mounted && ref.read(playerProvider).isPlaying) {
        setState(() => _controlsVisible = false);
      }
    });
  }

  void _toggleControls() {
    setState(() => _controlsVisible = !_controlsVisible);
    if (_controlsVisible) {
      _hideControlsAfterDelay();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(playerProvider);
    final track = state.currentTrack;

    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        onTap: _toggleControls,
        child: Stack(
          fit: StackFit.expand,
          children: <Widget>[
            // Video surface — in production this wraps a `VideoPlayer` widget.
            // Here we show a placeholder with the track title.
            Container(
              color: Colors.black,
              child: Center(
                child: track == null
                    ? const Text('No media',
                        style: TextStyle(color: Colors.white54))
                    : Column(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Icon(track.category.icon,
                              size: 64, color: Colors.white54),
                          const SizedBox(height: 16),
                          Text(
                            track.displayTitle,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
              ),
            ),

            // Controls overlay
            AnimatedOpacity(
              opacity: _controlsVisible ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 300),
              child: IgnorePointer(
                ignoring: !_controlsVisible,
                child: _ControlsOverlay(
                  state: state,
                  onBack: () => context.go(AppRoutes.home),
                  onPlayPause: () => ref
                      .read(playerProvider.notifier)
                      .togglePlayPause(),
                  onPrev: () =>
                      ref.read(playerProvider.notifier).skipPrevious(),
                  onNext: () => ref.read(playerProvider.notifier).skipNext(),
                  onSeek: (pos) =>
                      ref.read(playerProvider.notifier).seek(pos),
                  onSpeed: (s) =>
                      ref.read(playerProvider.notifier).setSpeed(s),
                  onShuffle: () =>
                      ref.read(playerProvider.notifier).toggleShuffle(),
                  onRepeat: () =>
                      ref.read(playerProvider.notifier).cycleRepeatMode(),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ControlsOverlay extends StatelessWidget {
  const _ControlsOverlay({
    required this.state,
    required this.onBack,
    required this.onPlayPause,
    required this.onPrev,
    required this.onNext,
    required this.onSeek,
    required this.onSpeed,
    required this.onShuffle,
    required this.onRepeat,
  });

  final PlayerState state;
  final VoidCallback onBack;
  final VoidCallback onPlayPause;
  final VoidCallback onPrev;
  final VoidCallback onNext;
  final void Function(Duration) onSeek;
  final void Function(double) onSpeed;
  final VoidCallback onShuffle;
  final VoidCallback onRepeat;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: <Color>[Colors.black54, Colors.transparent, Colors.black54],
          stops: <double>[0, 0.3, 1],
        ),
      ),
      child: SafeArea(
        child: Column(
          children: <Widget>[
            _topBar(),
            const Spacer(),
            _centerControls(),
            const Spacer(),
            _bottomBar(),
          ],
        ),
      ),
    );
  }

  Widget _topBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Row(
        children: <Widget>[
          IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: onBack,
          ),
          Expanded(
            child: Text(
              state.currentTrack?.displayTitle ?? '',
              style: const TextStyle(color: Colors.white, fontSize: 16),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          PopupMenuButton<double>(
            icon: const Icon(Icons.speed, color: Colors.white),
            onSelected: onSpeed,
            itemBuilder: (_) => const <PopupMenuEntry<double>>[
              PopupMenuItem(value: 0.25, child: Text('0.25x')),
              PopupMenuItem(value: 0.5, child: Text('0.5x')),
              PopupMenuItem(value: 0.75, child: Text('0.75x')),
              PopupMenuItem(value: 1.0, child: Text('1.0x (Normal)')),
              PopupMenuItem(value: 1.25, child: Text('1.25x')),
              PopupMenuItem(value: 1.5, child: Text('1.5x')),
              PopupMenuItem(value: 2.0, child: Text('2.0x')),
            ],
          ),
        ],
      ),
    );
  }

  Widget _centerControls() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: <Widget>[
        IconButton(
          icon: Icon(
            Icons.shuffle,
            color: state.shuffle ? Colors.white : Colors.white54,
          ),
          iconSize: 28,
          onPressed: onShuffle,
        ),
        IconButton(
          icon: const Icon(Icons.skip_previous, color: Colors.white),
          iconSize: 48,
          onPressed: onPrev,
        ),
        Container(
          width: 72,
          height: 72,
          decoration: const BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
          ),
          child: IconButton(
            icon: Icon(
              state.isPlaying ? Icons.pause : Icons.play_arrow,
              color: Colors.black,
              size: 36,
            ),
            onPressed: onPlayPause,
          ),
        ),
        IconButton(
          icon: const Icon(Icons.skip_next, color: Colors.white),
          iconSize: 48,
          onPressed: onNext,
        ),
        IconButton(
          icon: Icon(
            _repeatIcon(),
            color: state.repeatMode != RepeatMode.off
                ? Colors.white
                : Colors.white54,
          ),
          iconSize: 28,
          onPressed: onRepeat,
        ),
      ],
    );
  }

  Widget _bottomBar() {
    final duration = state.duration.inMilliseconds.toDouble();
    final position = state.position.inMilliseconds.toDouble().clamp(
          0,
          duration > 0 ? duration : 0,
        );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        children: <Widget>[
          Slider(
            value: position,
            max: duration > 0 ? duration : 1,
            onChanged: duration > 0
                ? (v) => onSeek(Duration(milliseconds: v.toInt()))
                : null,
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: <Widget>[
              Text(
                _formatDuration(state.position),
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
              if (state.sleepTimerRemaining != null)
                Text(
                  'Sleep: ${_formatDuration(state.sleepTimerRemaining!)}',
                  style: const TextStyle(color: Colors.amber, fontSize: 12),
                ),
              Text(
                _formatDuration(state.duration),
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ],
          ),
        ],
      ),
    );
  }

  IconData _repeatIcon() {
    return switch (state.repeatMode) {
      RepeatMode.off => Icons.repeat,
      RepeatMode.all => Icons.repeat,
      RepeatMode.one => Icons.repeat_one,
    };
  }

  String _formatDuration(Duration d) {
    final h = d.inHours;
    final m = d.inMinutes.remainder(60);
    final s = d.inSeconds.remainder(60);
    if (h > 0) {
      return '$h:${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
    }
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }
}
