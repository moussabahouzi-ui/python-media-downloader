import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../models/media_library_models.dart';
import '../providers/player_provider.dart';

/// Audio player screen: "now playing" UI with artwork, title, controls,
/// playback speed, sleep timer, and queue preview.
class AudioPlayerScreen extends ConsumerWidget {
  const AudioPlayerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final state = ref.watch(playerProvider);
    final track = state.currentTrack;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: <Widget>[
            _topBar(theme, context),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: <Widget>[
                    const Spacer(),
                    _artwork(theme, track),
                    const SizedBox(height: 32),
                    _trackInfo(theme, track),
                    const SizedBox(height: 24),
                    _progressBar(theme, state, ref),
                    const SizedBox(height: 16),
                    _mainControls(theme, state, ref),
                    const SizedBox(height: 24),
                    _secondaryControls(theme, state, ref),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _topBar(ThemeData theme, BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(8),
      child: Row(
        children: <Widget>[
          IconButton(
            icon: const Icon(Icons.arrow_back_rounded),
            onPressed: () => context.go(AppRoutes.home),
          ),
          const Spacer(),
          Text('Now Playing', style: theme.textTheme.titleMedium),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.queue_music_rounded),
            onPressed: () {}, // Phase 5+: open queue sheet
          ),
        ],
      ),
    );
  }

  Widget _artwork(ThemeData theme, MediaItem? track) {
    return Container(
      width: 240,
      height: 240,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        color: theme.colorScheme.primaryContainer,
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: theme.colorScheme.shadow.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: track?.thumbnailPath != null
          ? ClipRRect(
              borderRadius: BorderRadius.circular(24),
              child: Image.network(
                track!.thumbnailPath!,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) =>
                    Icon(Icons.music_note, size: 80, color: theme.colorScheme.onPrimaryContainer),
              ),
            )
          : Icon(
              Icons.music_note,
              size: 80,
              color: theme.colorScheme.onPrimaryContainer,
            ),
    );
  }

  Widget _trackInfo(ThemeData theme, MediaItem? track) {
    return Column(
      children: <Widget>[
        Text(
          track?.displayTitle ?? 'No track',
          style: theme.textTheme.headlineSmall,
          textAlign: TextAlign.center,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 4),
        Text(
          track?.uploader ?? '',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }

  Widget _progressBar(ThemeData theme, PlayerState state, WidgetRef ref) {
    final duration = state.duration.inMilliseconds.toDouble();
    final position = state.position.inMilliseconds.toDouble().clamp(
          0,
          duration > 0 ? duration : 0,
        );
    return Column(
      children: <Widget>[
        Slider(
          value: position,
          max: duration > 0 ? duration : 1,
          onChanged: duration > 0
              ? (v) =>
                  ref.read(playerProvider.notifier).seek(Duration(milliseconds: v.toInt()))
              : null,
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: <Widget>[
              Text(_fmt(state.position), style: theme.textTheme.labelSmall),
              if (state.sleepTimerRemaining != null)
                Text(
                  'Sleep ${_fmt(state.sleepTimerRemaining!)}',
                  style: theme.textTheme.labelSmall?.copyWith(color: Colors.amber),
                ),
              Text(_fmt(state.duration), style: theme.textTheme.labelSmall),
            ],
          ),
        ),
      ],
    );
  }

  Widget _mainControls(ThemeData theme, PlayerState state, WidgetRef ref) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: <Widget>[
        IconButton(
          icon: Icon(
            Icons.shuffle_rounded,
            color: state.shuffle ? theme.colorScheme.primary : null,
          ),
          iconSize: 28,
          onPressed: () => ref.read(playerProvider.notifier).toggleShuffle(),
        ),
        IconButton(
          icon: const Icon(Icons.skip_previous_rounded),
          iconSize: 48,
          onPressed: () => ref.read(playerProvider.notifier).skipPrevious(),
        ),
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            color: theme.colorScheme.primary,
            shape: BoxShape.circle,
          ),
          child: IconButton(
            icon: Icon(
              state.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
              color: theme.colorScheme.onPrimary,
            ),
            iconSize: 40,
            onPressed: () =>
                ref.read(playerProvider.notifier).togglePlayPause(),
          ),
        ),
        IconButton(
          icon: const Icon(Icons.skip_next_rounded),
          iconSize: 48,
          onPressed: () => ref.read(playerProvider.notifier).skipNext(),
        ),
        IconButton(
          icon: Icon(
            _repeatIcon(state),
            color: state.repeatMode != RepeatMode.off
                ? theme.colorScheme.primary
                : null,
          ),
          iconSize: 28,
          onPressed: () => ref.read(playerProvider.notifier).cycleRepeatMode(),
        ),
      ],
    );
  }

  Widget _secondaryControls(ThemeData theme, PlayerState state, WidgetRef ref) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: <Widget>[
        PopupMenuButton<double>(
          icon: Icon(Icons.speed_rounded, color: theme.colorScheme.onSurfaceVariant),
          onSelected: (s) => ref.read(playerProvider.notifier).setSpeed(s),
          itemBuilder: (_) => const <PopupMenuEntry<double>>[
            PopupMenuItem(value: 0.75, child: Text('0.75x')),
            PopupMenuItem(value: 1.0, child: Text('1.0x')),
            PopupMenuItem(value: 1.25, child: Text('1.25x')),
            PopupMenuItem(value: 1.5, child: Text('1.5x')),
            PopupMenuItem(value: 2.0, child: Text('2.0x')),
          ],
        ),
        if (state.sleepTimerRemaining != null)
          TextButton.icon(
            onPressed: () => ref.read(playerProvider.notifier).cancelSleepTimer(),
            icon: const Icon(Icons.bedtime_rounded, size: 18),
            label: Text(_fmt(state.sleepTimerRemaining!)),
          )
        else
          PopupMenuButton<Duration>(
            icon: const Icon(Icons.bedtime_outlined),
            onSelected: (d) =>
                ref.read(playerProvider.notifier).startSleepTimer(d),
            itemBuilder: (_) => const <PopupMenuEntry<Duration>>[
              PopupMenuItem(value: Duration(minutes: 5), child: Text('5 min')),
              PopupMenuItem(value: Duration(minutes: 15), child: Text('15 min')),
              PopupMenuItem(value: Duration(minutes: 30), child: Text('30 min')),
              PopupMenuItem(value: Duration(minutes: 45), child: Text('45 min')),
              PopupMenuItem(value: Duration(hours: 1), child: Text('1 hour')),
            ],
          ),
      ],
    );
  }

  IconData _repeatIcon(PlayerState state) {
    return switch (state.repeatMode) {
      RepeatMode.off => Icons.repeat_rounded,
      RepeatMode.all => Icons.repeat_rounded,
      RepeatMode.one => Icons.repeat_one_rounded,
    };
  }

  String _fmt(Duration d) {
    final m = d.inMinutes.remainder(60);
    final s = d.inSeconds.remainder(60);
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }
}
